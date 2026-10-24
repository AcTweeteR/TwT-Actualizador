"""Coordinate XStream's JSON history stores across addon instances."""
from contextlib import contextmanager
from copy import deepcopy
import json
import os
import threading
import time


_thread_lock = threading.RLock()
_MISSING = object()


@contextmanager
def _locked(path):
    """Use an OS lock so independent Kodi Python addon contexts serialize writes."""
    lock_path = path + ".actweeter-lock"
    with _thread_lock:
        flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(lock_path, flags, 0o600)
        acquired = False
        try:
            if os.name == "nt":
                import msvcrt
                if os.fstat(fd).st_size == 0:
                    os.write(fd, b"0")
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX)
            acquired = True
            yield
        finally:
            if acquired:
                if os.name == "nt":
                    import msvcrt
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)


def _read(path, expected, empty):
    try:
        with open(path, "r", encoding="utf-8") as stream:
            value = json.load(stream)
    except FileNotFoundError:
        return empty
    if not isinstance(value, expected):
        raise ValueError("XStream history store has an unexpected JSON shape")
    return value


def _merge_map(base, changed, latest, timestamped=False):
    merged = deepcopy(latest)
    for key in set(base) | set(changed):
        old, new = base.get(key, _MISSING), changed.get(key, _MISSING)
        if old == new:
            continue
        disk = merged.get(key, _MISSING)
        if new is _MISSING:
            # A stale instance may not delete a newer value written elsewhere.
            if disk == old:
                merged.pop(key, None)
            continue
        if timestamped and disk is not _MISSING:
            disk_time = disk.get("timestamp") if isinstance(disk, dict) else None
            new_time = new.get("timestamp") if isinstance(new, dict) else None
            if (type(disk_time) not in (int, float)
                    or type(new_time) not in (int, float)
                    or disk_time >= new_time):
                continue
        merged[key] = deepcopy(new)
    return merged


def _episode_set(value):
    if not isinstance(value, dict):
        raise ValueError("XStream episode store has an unexpected JSON shape")
    result = set()
    for series, seasons in value.items():
        if not isinstance(seasons, dict):
            raise ValueError("XStream episode store has an unexpected season shape")
        for season, episodes in seasons.items():
            if not isinstance(episodes, list):
                raise ValueError("XStream episode store has an unexpected episode shape")
            result.update((str(series), str(season), str(episode)) for episode in episodes)
    return result


def _merge_episodes(base, changed, latest):
    baseline, current, result = _episode_set(base), _episode_set(changed), _episode_set(latest)
    result.update(current - baseline)
    result.difference_update(baseline - current)
    merged = {}
    for series, season, episode in sorted(result):
        merged.setdefault(series, {}).setdefault(season, []).append(episode)
    return merged


def _install_store(store, attribute, empty, merge):
    if getattr(store, "_actweeter_coordinated", False):
        return
    original_init, original_save = store.__init__, store._save

    def init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        setattr(self, "_actweeter_base", deepcopy(getattr(self, attribute)))

    def save(self):
        with _locked(self._path):
            latest = _read(self._path, dict, empty)
            base = getattr(self, "_actweeter_base", empty)
            current = getattr(self, attribute)
            if store.__name__ == "ResumePoints":
                source_time = getattr(self, "_actweeter_source_timestamp", None)
                if source_time is not None:
                    for key in set(base) | set(current):
                        if base.get(key, _MISSING) != current.get(key, _MISSING):
                            if key in current and isinstance(current[key], dict):
                                current[key]["timestamp"] = source_time
                            break
            merged = merge(base, current, latest)
            if merged != latest:
                setattr(self, attribute, merged)
                original_save(self)
            setattr(self, attribute, merged)
            self._actweeter_base = deepcopy(merged)

    store.__init__, store._save = init, save
    store._actweeter_coordinated = True


def install(history):
    """Patch existing XStream stores in place; retain their public APIs."""
    _install_store(history.WatchedMovies, "_data", {}, _merge_map)
    _install_store(history.WatchedEpisodes, "_data", {}, _merge_episodes)
    _install_store(history.ResumePoints, "_data", {},
                   lambda base, changed, latest: _merge_map(
                       base, changed, latest, timestamped=True))

    store = history.ResumePoints
    original = store.save_position

    def save_position(self, name, url, position, duration, extra=None,
                      force=False, timestamp=None):
        key = self._key(name, url)
        if (type(position) not in (int, float) or type(duration) not in (int, float)
                or position < 60 or duration < 120):
            return False
        previous = self._data.get(key)
        if (not force and isinstance(previous, dict)
                and type(position) in (int, float)
                and type(duration) in (int, float)
                and type(previous.get("position")) in (int, float)
                and position <= duration * 0.93
                and abs(position - previous.get("position", position)) < 60):
            return False
        if timestamp is not None and (type(timestamp) not in (int, float)
                                      or timestamp <= 0):
            raise ValueError("invalid source timestamp")
        self._actweeter_source_timestamp = timestamp
        try:
            original(self, name, url, position, duration, extra)
        finally:
            self._actweeter_source_timestamp = None
        return True

    store.save_position = save_position
