"""Provider-only, profile-scoped series change history used by XStream."""

import hashlib
import json
import os
import tempfile
import threading
import time
from datetime import datetime

import series_state
import xbmcvfs


WINDOW_SECONDS = 5 * 86400
CATALOG_INTERVAL = 6 * 3600
STATE_VERSION = 2
_LOCK = threading.RLock()


def _path(addon, profile_num):
    profile = xbmcvfs.translatePath(addon.getAddonInfo("profile"))
    return os.path.join(profile, "series_changes_p%d.json" % int(profile_num))


def _empty():
    return {"schema_version": STATE_VERSION, "events": [], "catalog_ids": None,
            "episode_ids": {}, "episode_inventory": {}}


def _read(addon, profile_num):
    path = _path(addon, profile_num)
    try:
        with open(path, "r", encoding="utf-8") as stream:
            data = json.load(stream)
    except FileNotFoundError:
        return _empty()
    except (OSError, ValueError, TypeError):
        # Preserve corrupt state; a silent empty baseline would erase news history.
        return None
    if not isinstance(data, dict):
        return None
    if (not isinstance(data.get("events", []), list)
            or any(not isinstance(event, dict) for event in data.get("events", []))):
        return None
    known = data.get("catalog_ids")
    if known is not None and not isinstance(known, list):
        return None
    for key in ("episode_ids", "episode_inventory"):
        if not isinstance(data.get(key, {}), dict):
            return None
    data.setdefault("events", [])
    data.setdefault("episode_ids", {})
    data.setdefault("episode_inventory", {})
    data["schema_version"] = STATE_VERSION
    return data


def _write(addon, profile_num, data):
    target = _path(addon, profile_num)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".series_changes_", dir=os.path.dirname(target))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        try:
            os.unlink(temporary)
        except OSError:
            pass


def _provider_key(provider):
    if not isinstance(provider, (tuple, list)) or len(provider) < 2:
        return ""
    host, user = (str(value or "").strip() for value in provider[:2])
    if not host or not user:
        return ""
    # The fingerprint scopes IDs without persisting the provider URL or username.
    return hashlib.sha256((host.casefold() + "\n" + user).encode("utf-8")).hexdigest()


def _scope_provider(data, provider):
    key = _provider_key(provider)
    previous = str(data.get("provider_key") or "")
    if key and previous and key != previous:
        data.update(catalog_ids=None, episode_ids={}, episode_inventory={}, events=[])
        data.pop("episode_added_at", None)
    if key:
        data["provider_key"] = key


def _provider_date(value, now):
    try:
        timestamp = float(value)
    except (TypeError, ValueError, OverflowError):
        try:
            stamp = str(value or "").strip().replace("Z", "+00:00")
            parsed = datetime.fromisoformat(stamp)
            if parsed.tzinfo is None:
                return 0
            timestamp = parsed.timestamp()
        except (TypeError, ValueError, OverflowError):
            return 0
    if timestamp > 100000000000:
        timestamp /= 1000.0
    if timestamp < 946684800 or timestamp > now + 300:
        return 0
    return int(timestamp)


def _event_time(event):
    try:
        return float(event.get("changed", 0) or 0)
    except (AttributeError, TypeError, ValueError, OverflowError):
        return 0


def _trim(data, now):
    cutoff = now - WINDOW_SECONDS
    data["events"] = [event for event in data.get("events", [])
                      if isinstance(event, dict)
                      and cutoff <= _event_time(event) <= now + 300]


def _add_event(data, series_id, title, status, changed, now):
    if changed < now - WINDOW_SECONDS:
        return
    events = data.setdefault("events", [])
    for index, event in enumerate(events):
        if str(event.get("series_id")) == str(series_id):
            previous_time = _event_time(event)
            if (event.get("status") == "NUEVA SERIE"
                    and now - WINDOW_SECONDS <= previous_time <= now + 300):
                return
            events[index] = {"series_id": str(series_id), "title": str(title or ""),
                             "status": status, "changed": changed}
            return
    events.append({"series_id": str(series_id), "title": str(title or ""),
                   "status": status, "changed": changed})


def _catalog_snapshot(items):
    if not isinstance(items, list) or not items:
        return None
    result = {}
    for item in items:
        if not isinstance(item, dict):
            return None
        series_id = str(item.get("series_id") or item.get("id") or "").strip()
        name = str(item.get("name") or "").strip()
        if not series_id or not name:
            return None
        result[series_id] = item
    return result or None


def record_catalog(addon, profile_num, items, force=False, *, provider=None,
                   complete=True):
    """Baseline complete catalogs; use provider added timestamps when available."""
    if complete is not True:
        return False
    now = time.time()
    with _LOCK:
        data = _read(addon, profile_num)
        if data is None:
            return False
        _scope_provider(data, provider)
        if (not force and data.get("catalog_ids") is not None
                and now - float(data.get("catalog_checked", 0) or 0) < CATALOG_INTERVAL):
            return False
        snapshot = _catalog_snapshot(items)
        if snapshot is None:
            return False
        known = data.get("catalog_ids")
        if known == []:
            # Legacy empty snapshots are indistinguishable from an empty/partial fetch.
            known = None
            data["catalog_ids"] = None
        current = set(snapshot)
        if known is None:
            # A new device shows only objectively recent additions, never all its baseline.
            for series_id, item in snapshot.items():
                added = _provider_date(item.get("added"), now)
                if added and added >= now - WINDOW_SECONDS:
                    _add_event(data, series_id, item.get("name"), "NUEVA SERIE", added, now)
        else:
            known_ids = {str(value) for value in known}
            for series_id in current - known_ids:
                item = snapshot[series_id]
                changed = _provider_date(item.get("added"), now) or now
                _add_event(data, series_id, item.get("name"), "NUEVA SERIE", changed, now)
            current.update(known_ids)
        data["catalog_ids"] = sorted(current)
        data["catalog_checked"] = now
        _trim(data, now)
        _write(addon, profile_num, data)
    return True


def record_series_info(addon, profile_num, series_id, title, response, *, provider=None):
    """Compare only complete episode inventories; keep the last good snapshot."""
    if not isinstance(response, dict) or not isinstance(response.get("episodes"), dict):
        return False
    episodes = response["episodes"]
    inventory, complete = series_state.normalize_inventory(episodes)
    now = time.time()
    key = str(series_id)
    info = response.get("info")
    info = info if isinstance(info, dict) else {}
    diagnostics = series_state.inventory_diagnostics(episodes) if not complete else {}
    conflicts = diagnostics.pop("conflicting_coordinates", [])
    dates = {}
    for season_rows in episodes.values():
        if not isinstance(season_rows, list):
            continue
        for row in season_rows:
            if not isinstance(row, dict):
                continue
            episode_id = str(row.get("id") or row.get("episode_id") or "").strip()
            added = _provider_date(row.get("added"), now)
            if episode_id and added:
                dates[episode_id] = added
    with _LOCK:
        data = _read(addon, profile_num)
        if data is None:
            return False
        _scope_provider(data, provider)
        stored = data.setdefault("episode_inventory", {})
        previous = stored.get(key)
        previous_complete = isinstance(previous, dict) and previous.get("complete") is True
        if not complete:
            if not previous_complete:
                stored[key] = {"checked_at": now, "complete": False,
                               "diagnostics": diagnostics, "conflicting_coordinates": conflicts,
                               "tmdb_id": str(info.get("tmdb_id") or info.get("tmdb") or ""),
                               "episodes": []}
                _write(addon, profile_num, data)
            return False
        current_ids = {row["provider_id"] for row in inventory}
        previous_ids = {str(row.get("provider_id")) for row in previous.get("episodes", [])
                        if isinstance(row, dict) and row.get("provider_id")} if previous_complete else set()
        added_ids = current_ids - previous_ids
        eligible_ids = added_ids if previous_complete else current_ids
        dated_ids = [dates[item] for item in eligible_ids if item in dates]
        dated_recent = [value for value in dated_ids if value >= now - WINDOW_SECONDS]
        catalog_is_new = any(
            str(event.get("series_id")) == key and event.get("status") == "NUEVA SERIE"
            and now - WINDOW_SECONDS <= _event_time(event) <= now + 300
            for event in data.get("events", []) if isinstance(event, dict))
        if dated_recent and not catalog_is_new:
            _add_event(data, key, title, "NUEVOS CAPÍTULOS", max(dated_recent), now)
        elif not dated_ids and previous_complete and added_ids and not catalog_is_new:
            _add_event(data, key, title, "NUEVOS CAPÍTULOS", now, now)
        stored[key] = {"checked_at": now, "complete": True, "diagnostics": {},
                       "conflicting_coordinates": [],
                       "tmdb_id": str(info.get("tmdb_id") or info.get("tmdb") or ""),
                       "episodes": inventory}
        data.setdefault("episode_ids", {})[key] = sorted(current_ids)
        _trim(data, now)
        _write(addon, profile_num, data)
    return True


def inventory_map(addon, profile_num):
    data = _read(addon, profile_num)
    inventories = data.get("episode_inventory", {}) if data else {}
    return inventories if isinstance(inventories, dict) else {}


def status(addon, profile_num, series_id):
    data = _read(addon, profile_num)
    if not data:
        return ""
    now = time.time()
    for event in data.get("events", []):
        changed = _event_time(event)
        if (str(event.get("series_id")) == str(series_id)
                and now - WINDOW_SECONDS <= changed <= now + 300):
            return str(event.get("status") or "")
    return ""


def recent(addon, profile_num, limit=24):
    data = _read(addon, profile_num)
    if not data:
        return []
    now = time.time()
    events = [event for event in data.get("events", [])
              if isinstance(event, dict)
              and now - WINDOW_SECONDS <= _event_time(event) <= now + 300]
    return sorted(events, key=_event_time,
                  reverse=True)[:max(1, min(int(limit), 50))]
