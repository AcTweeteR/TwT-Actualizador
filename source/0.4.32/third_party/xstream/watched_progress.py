"""Explicit, monotonic progress marking for a single verified provider series.

No title-based matching. Never infer missing episodes or toggle already watched
episodes. Episode and season identifiers must be present in a fresh, complete
provider inventory before any local history is changed.
"""
from __future__ import annotations

import copy
import time


class IncompleteSeriesInventory(ValueError):
    pass


MAX_AGE = 14 * 86400


def prior_episodes(inventory_record, season, episode, *, now=None):
    from series_state import _valid_stored_inventory

    if not isinstance(inventory_record, dict) or inventory_record.get("complete") is not True:
        raise IncompleteSeriesInventory("complete provider series inventory required")
    checked = inventory_record.get("checked_at")
    clock = time.time() if now is None else now
    try:
        age = clock - float(checked)
    except (TypeError, ValueError, OverflowError):
        raise IncompleteSeriesInventory("missing inventory timestamp") from None
    if not 0 <= age <= MAX_AGE:
        raise IncompleteSeriesInventory("provider inventory expired")
    if not str(season).isdecimal() or not str(episode).isdecimal():
        raise IncompleteSeriesInventory("invalid target coordinates")
    target = (int(season), int(episode))
    if target[0] < 1 or target[1] < 1:
        raise IncompleteSeriesInventory("specials cannot set chronological progress")
    episodes, valid = _valid_stored_inventory(inventory_record.get("episodes"))
    if not valid or target not in {(e["season"], e["episode"]) for e in episodes}:
        raise IncompleteSeriesInventory("target is not in an unambiguous inventory")
    return [e for e in episodes
            if e["season"] >= 1 and (e["season"], e["episode"]) <= target]


def mark_progress(g, args):
    """Explicit action invoked from the episode context menu, never automatically."""
    value = lambda name: str((args.get(name) or [""])[0]).strip()
    pnum = str(getattr(g["pm"], "active", "") or "1")
    if value("profile_num") != pnum:
        raise IncompleteSeriesInventory("profile changed before confirmation")
    series_id, season, episode, supplied_tmdb = (
        value("series_id"), value("season"), value("episode"), value("tmdb_id"))
    if not series_id:
        raise IncompleteSeriesInventory("missing exact provider series ID")

    from series_changes import inventory_map
    record = inventory_map(g["addon"], pnum).get(series_id)
    episodes = prior_episodes(record, season, episode)
    inventory_tmdb = str(record.get("tmdb_id") or "").strip()
    if supplied_tmdb and inventory_tmdb and supplied_tmdb != inventory_tmdb:
        raise IncompleteSeriesInventory("series identity does not match provider inventory")
    tmdb_id = inventory_tmdb if inventory_tmdb.isdecimal() and int(inventory_tmdb) > 0 else ""

    # Update native provider episode marks so existing XStream views/Trakt
    # history hooks receive the same deltas as ordinary watched actions.
    native = g["WatchedEpisodes"](g["addon"], profile_num=int(pnum))
    current = copy.deepcopy(native._data)
    touched = 0
    for row in episodes:
        by_season = current.setdefault(series_id, {}).setdefault(str(row["season"]), [])
        key = str(row["provider_id"])
        if key not in by_season:
            by_season.append(key)
            touched += 1
    if touched:
        native._data = current
        native._save()

    # The namespaced exact TMDb mirror is necessary for fresh installations
    # and the dynamic watched eye. It is safe only when verified by provider.
    if tmdb_id:
        from watched_actions import tmdb_watch_key
        remote = g["WatchedMovies"](g["addon"], profile_num=int(pnum))
        mirror = copy.deepcopy(remote._data)
        updated = False
        for row in episodes:
            key = tmdb_watch_key("episode", tmdb_id, row["season"], row["episode"])
            if key and mirror.get(key) is not True:
                mirror[key] = True
                updated = True
        if updated:
            remote._data = mirror
            remote._save()

    g["xbmc"].executebuiltin("Container.Refresh")
    return {"episodes_up_to_target": len(episodes), "newly_marked": touched}
