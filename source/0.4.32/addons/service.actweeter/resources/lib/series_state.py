"""Fail-closed, read-only series progress derived from XStream state."""

import time


INVENTORY_MAX_AGE_SECONDS = 14 * 24 * 60 * 60


def _positive_int(value, allow_zero=False):
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if number < 0 or (number == 0 and not allow_zero):
        return None
    return number


def normalize_inventory(episodes_by_season):
    """Normalize an Xtream get_series_info response; malformed means incomplete."""
    if not isinstance(episodes_by_season, dict):
        return [], False
    complete = bool(episodes_by_season)
    by_number = {}
    for season_raw, episodes in episodes_by_season.items():
        season = _positive_int(season_raw, allow_zero=True)
        if season is None or not isinstance(episodes, list):
            complete = False
            continue
        for episode_data in episodes:
            if not isinstance(episode_data, dict):
                complete = False
                continue
            episode = _positive_int(episode_data.get("episode_num", episode_data.get("num")))
            provider_id = str(episode_data.get("id") or episode_data.get("episode_id") or "").strip()
            if episode is None or not provider_id:
                complete = False
                continue
            key = (season, episode)
            entry = {"season": season, "episode": episode, "provider_id": provider_id}
            previous = by_number.get(key)
            if previous and previous["provider_id"] != provider_id:
                complete = False
                continue
            by_number[key] = entry
    inventory = sorted(by_number.values(), key=lambda row: (row["season"], row["episode"], row["provider_id"]))
    if not inventory:
        complete = False
    return inventory, complete


def _valid_stored_inventory(entries):
    if not isinstance(entries, list):
        return [], False
    by_number = {}
    complete = bool(entries)
    for entry in entries:
        if not isinstance(entry, dict):
            complete = False
            continue
        season = _positive_int(entry.get("season"), allow_zero=True)
        episode = _positive_int(entry.get("episode"))
        provider_id = str(entry.get("provider_id") or "").strip()
        if season is None or episode is None or not provider_id:
            complete = False
            continue
        key = (season, episode)
        previous = by_number.get(key)
        if previous and previous["provider_id"] != provider_id:
            complete = False
            continue
        by_number[key] = {"season": season, "episode": episode, "provider_id": provider_id}
    rows = sorted(by_number.values(), key=lambda row: (row["season"], row["episode"], row["provider_id"]))
    if not rows:
        complete = False
    return rows, complete


def _resume_episode(entries, series_id, inventory):
    inventory_by_provider_id = {row["provider_id"]: row for row in inventory}
    candidates = []
    for entry in entries or []:
        if not isinstance(entry, dict) or str(entry.get("series_id") or "") != str(series_id):
            continue
        provider_id = str(entry.get("ep_id") or "")
        episode = inventory_by_provider_id.get(provider_id)
        resume_season = _positive_int(entry.get("season_num"), allow_zero=True)
        if not episode or resume_season != episode["season"]:
            continue
        try:
            position = float(entry.get("position", 0) or 0)
            duration = float(entry.get("duration", 0) or 0)
            timestamp = float(entry.get("timestamp", 0) or 0)
        except (TypeError, ValueError, OverflowError):
            continue
        if 0 < position < duration:
            candidates.append((timestamp, episode))
    return max(candidates, key=lambda pair: pair[0])[1] if candidates else None


def resolve_tmdb_id(inventory_record, stream_item, cached_tmdb_id=""):
    """Use an already-resolved local identity; never perform catalog discovery."""
    inventory_record = inventory_record if isinstance(inventory_record, dict) else {}
    stream_item = stream_item if isinstance(stream_item, dict) else {}
    identities = {str(value).strip() for value in (
        inventory_record.get("tmdb_id"), inventory_record.get("tmdb"),
        stream_item.get("tmdb_id"), stream_item.get("tmdb"), cached_tmdb_id)
        if str(value or "").strip()}
    return identities.pop() if len(identities) == 1 else ""


def derive_series_state(tmdb_id, series_id, inventory_record, watched_store,
                        resume_entries=None, now=None, tmdb_watched_store=None):
    """Derive state without writes; unknown identity/inventory never means complete."""
    result = {"known": False, "total": 0, "watched": 0, "unwatched": 0,
              "complete": None, "next": None, "progress_label": ""}
    if not str(series_id or "").strip() or not isinstance(inventory_record, dict):
        return result
    inventory, structurally_complete = _valid_stored_inventory(inventory_record.get("episodes"))
    if not inventory:
        return result
    try:
        now = float(now if now is not None else time.time())
        checked = float(inventory_record.get("checked_at", 0) or 0)
        fresh = 0 <= now - checked <= INVENTORY_MAX_AGE_SECONDS
    except (TypeError, ValueError, OverflowError):
        fresh = False

    watched_rows = []
    try:
        for row in inventory:
            value = None
            if tmdb_id and tmdb_watched_store is not None:
                key = 'tmdb:episode:{0}:s{1}:e{2}'.format(
                    tmdb_id, int(row["season"]), int(row["episode"]))
                candidate = tmdb_watched_store._data.get(key)
                if type(candidate) is bool:
                    value = candidate
            if value is None:
                value = watched_store.is_watched(
                    str(series_id), str(row["season"]), str(row["provider_id"]))
            watched_rows.append(bool(value))
    except Exception:
        return result

    watched_count = sum(1 for value in watched_rows if value)
    unwatched_count = len(inventory) - watched_count
    inventory_complete = bool(inventory_record.get("complete")) and structurally_complete and fresh
    complete = bool(inventory_complete and inventory and unwatched_count == 0)
    resume = _resume_episode(resume_entries, series_id, inventory)
    next_row = None
    if not complete and resume:
        resume_index = inventory.index(resume)
        if not watched_rows[resume_index]:
            next_row = resume
    if not complete and next_row is None:
        next_row = next((row for row, watched in zip(inventory, watched_rows) if not watched), None)
    if next_row:
        next_label = "T{0} · E{1:02d}".format(next_row["season"], next_row["episode"])
        progress_label = "{0}  {1}/{2}".format(next_label, watched_count, len(inventory))
    elif not complete:
        progress_label = "{0}/{1}".format(watched_count, len(inventory))
    else:
        progress_label = "COMPLETA"
    result.update({"known": True, "total": len(inventory), "watched": watched_count,
                   "unwatched": unwatched_count, "complete": complete if inventory_complete else None,
                   "next": next_row, "progress_label": progress_label})
    return result


def apply_to_listitem(listitem, state):
    """Expose only derived display fields; do not mutate any source state."""
    # Unknown inventory must not erase a previously known watched overlay.
    if not state or not state.get("known"):
        return False
    # Incomplete inventory is not evidence that a series was unwatched.
    if state.get("complete") is not None:
        listitem.setProperty("XStream.SeriesComplete", "false")
    label = str(state.get("progress_label") or "")
    if label:
        listitem.setProperty("XStream.SeriesProgressLabel", label)
    next_row = state.get("next")
    if next_row:
        listitem.setProperty("XStream.SeriesNextSeason", str(next_row["season"]))
        listitem.setProperty("XStream.SeriesNextEpisode", str(next_row["episode"]))
    if state.get("complete") is True:
        listitem.setProperty("XStream.SeriesComplete", "true")
        listitem.getVideoInfoTag().setPlaycount(1)
    elif state.get("complete") is False:
        listitem.getVideoInfoTag().setPlaycount(0)
    return True


def inventory_diagnostics(episodes_by_season):
    """Describe rejected provider rows without retaining titles or private data."""
    counts = {"invalid_season": 0, "invalid_episode_list": 0,
              "invalid_episode_row": 0, "missing_episode_number": 0,
              "missing_provider_id": 0, "conflicting_episode_id": 0}
    if not isinstance(episodes_by_season, dict):
        return {"invalid_response": 1}
    seen = {}
    conflicting_coordinates = set()
    for season_raw, episodes in episodes_by_season.items():
        season = _positive_int(season_raw, allow_zero=True)
        if season is None:
            counts["invalid_season"] += 1
        if not isinstance(episodes, list):
            counts["invalid_episode_list"] += 1
            continue
        for row in episodes:
            if not isinstance(row, dict):
                counts["invalid_episode_row"] += 1
                continue
            episode = _positive_int(row.get("episode_num", row.get("num")))
            provider = str(row.get("id") or row.get("episode_id") or "").strip()
            if episode is None:
                counts["missing_episode_number"] += 1
            if not provider:
                counts["missing_provider_id"] += 1
            if season is None or episode is None or not provider:
                continue
            key = (season, episode)
            if key in seen and seen[key] != provider:
                counts["conflicting_episode_id"] += 1
                conflicting_coordinates.add(key)
            seen[key] = provider
    report = {key: value for key, value in counts.items() if value}
    if conflicting_coordinates:
        report["conflicting_coordinates"] = [list(key) for key in sorted(conflicting_coordinates)]
    return report


