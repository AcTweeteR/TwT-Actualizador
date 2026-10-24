"""Crash-safe, process-coordinated generations for the four Xtream catalogs."""
import contextlib
import hashlib
import json
import os
import shutil
import tempfile
import threading
import time
import uuid
from pathlib import Path

try:
    import fcntl
except ImportError:
    fcntl = None


KEYS = ("xtream_streams_movie", "xtream_cats_movie",
        "xtream_streams_series", "xtream_cats_series")
COUNT_KEYS = ("xtream_counts_movie", "xtream_counts_series")
FILES = {key: key + ".json" for key in KEYS + COUNT_KEYS}
_PINS = threading.local()
_VALIDATED = {}


def _pins():
    if not hasattr(_PINS, "generations"):
        _PINS.generations = {}
    return _PINS.generations


class RefreshCancelled(Exception):
    pass


def provider_fingerprint(source):
    return hashlib.sha256(str(source).encode("utf-8")).hexdigest()


def source_matches(value, source):
    """Read hashed generations and legacy raw-source caches without writing secrets."""
    return (isinstance(value, dict)
            and value.get("_src") in (str(source), provider_fingerprint(source)))


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"),
                      sort_keys=True).encode("utf-8")


def _atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix="." + path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, str(path))
        _fsync_dir(path.parent)
    finally:
        try:
            os.unlink(temp)
        except OSError:
            pass


def _fsync_dir(path):
    try:
        directory = os.open(str(path), os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except OSError:
        pass


@contextlib.contextmanager
def provider_lock(profile_dir, profile_number, source, *, timeout=120,
                  cancel=None, poll_interval=.05):
    """A per-profile/provider OS lock shared by independent Kodi processes."""
    if type(profile_number) is not int or not 1 <= profile_number <= 10:
        raise ValueError("invalid profile number")
    base = Path(profile_dir) / "catalog_generations"
    fingerprint = provider_fingerprint(source)
    lock_path = base / ("p%d-%s.lock" % (profile_number, fingerprint))
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if fcntl is None:
        import msvcrt
    else:
        msvcrt = None
    deadline = time.monotonic() + max(0, timeout)
    lock_file = lock_path.open("a+b")
    acquired = False
    if fcntl is None and lock_file.seek(0, os.SEEK_END) == 0:
        lock_file.write(b"\0")
        lock_file.flush()
    try:
        while True:
            if cancel is not None and cancel.is_set():
                raise RefreshCancelled("catalog refresh cancelled while waiting for lock")
            try:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                else:
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                acquired = True
                break
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    raise TimeoutError("timed out waiting for catalog refresh lock")
                time.sleep(min(poll_interval, max(0, deadline - time.monotonic())))
        lock_file.seek(0)
        lock_file.truncate()
        lock_file.write(_json_bytes({"pid": os.getpid(), "created": time.time()}))
        lock_file.flush()
        os.fsync(lock_file.fileno())
        yield
    finally:
        try:
            if acquired:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                else:
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            lock_file.close()


def _pointer_paths(profile_dir, profile_number, source):
    root = Path(profile_dir) / "catalog_generations"
    fingerprint = provider_fingerprint(source)
    base = "p%d-%s" % (profile_number, fingerprint)
    return root / (base + ".json"), root / (base + ".previous.json"), root / base


def _read_pointer(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, TypeError):
        return None


def _valid_generation(directory, pointer):
    if not isinstance(pointer, dict) or pointer.get("schema") != 1:
        return False
    if not isinstance(pointer.get("generation"), str):
        return False
    manifest_path = Path(directory) / pointer["generation"] / "manifest.json"
    try:
        signature = tuple((path.stat().st_size, path.stat().st_mtime_ns)
                          for path in (manifest_path.parent / name
                                       for name in ("manifest.json",) + tuple(FILES.values())))
        validation_key = str(manifest_path)
        if _VALIDATED.get(validation_key) == signature:
            return True
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (manifest.get("schema") != 1
                or manifest.get("generation") != pointer["generation"]
                or set(manifest.get("files", {})) != set(FILES)):
            return False
        for key, filename in FILES.items():
            raw = (manifest_path.parent / filename).read_bytes()
            if hashlib.sha256(raw).hexdigest() != manifest["files"][key]:
                return False
            value = json.loads(raw.decode("utf-8"))
            if key in KEYS and (not isinstance(value, dict)
                                or not isinstance(value.get("_data"), list)):
                return False
            if key in COUNT_KEYS and not isinstance(value, dict):
                return False
        _VALIDATED[validation_key] = signature
    except (OSError, ValueError, TypeError, KeyError):
        return False
    return True


def current_generation(profile_dir, profile_number, source):
    pointer_path, previous_path, directory = _pointer_paths(
        profile_dir, profile_number, source)
    for path in (pointer_path, previous_path):
        pointer = _read_pointer(path)
        if _valid_generation(directory, pointer):
            return pointer["generation"]
    return None


def cache_path(profile_dir, profile_number, source, key, legacy_path=None):
    if key not in FILES:
        return str(legacy_path) if legacy_path is not None else None
    pointer_path, previous_path, directory = _pointer_paths(
        profile_dir, profile_number, source)
    pin_key = (str(profile_dir), profile_number, provider_fingerprint(source))
    pins = _pins()
    if pin_key not in pins:
        pins[pin_key] = current_generation(profile_dir, profile_number, source)
    generation = pins[pin_key]
    if generation:
        pointer = {"schema": 1, "generation": generation}
        if _valid_generation(directory, pointer):
            return str(directory / generation / FILES[key])
    return str(legacy_path) if legacy_path is not None else None


def pin_generation(profile_dir, profile_number, source, generation):
    _pins()[(str(profile_dir), profile_number, provider_fingerprint(source))] = generation


def reset_pins():
    _pins().clear()


def _validate_snapshot(values, previous):
    for key in KEYS:
        rows = values[key]
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError("invalid catalog component: " + key)
        old = previous.get(key, [])
        if old and not rows:
            raise ValueError("empty snapshot would erase non-empty catalog: " + key)
    for kind in ("movie", "series"):
        streams = values["xtream_streams_" + kind]
        categories = values["xtream_cats_" + kind]
        if streams and not categories:
            raise ValueError("catalog has streams but no categories: " + kind)


def refresh(profile_dir, profile_number, source, fetchers, *, force=False,
            timeout=120, cancel=None):
    """Fetch, validate, stage, then atomically publish one complete generation."""
    if set(fetchers) - {"_legacy"} != set(KEYS):
        raise ValueError("fetchers must provide all four catalog components")
    pointer_path, previous_path, directory = _pointer_paths(
        profile_dir, profile_number, source)
    requested_at = time.time()
    observed = current_generation(profile_dir, profile_number, source)
    with provider_lock(profile_dir, profile_number, source, timeout=timeout,
                       cancel=cancel):
        existing = current_generation(profile_dir, profile_number, source)
        pointer = _read_pointer(pointer_path)
        if existing and (not force or existing != observed
                         or (pointer or {}).get("updated_at", 0) >= requested_at):
            return {"generation": existing, "refreshed": False}
        previous = {}
        if existing:
            gen_dir = directory / existing
            for key in KEYS:
                filename = FILES[key]
                value = json.loads((gen_dir / filename).read_text(encoding="utf-8"))
                previous[key] = value.get("_data", [])
        elif callable(fetchers.get("_legacy")):
            previous = fetchers["_legacy"]()
        values = {}
        for key in KEYS:
            if cancel is not None and cancel.is_set():
                raise RefreshCancelled("catalog refresh cancelled during fetch")
            values[key] = fetchers[key]()
        _validate_snapshot(values, previous)
        generation = uuid.uuid4().hex
        stage_parent = directory
        stage_parent.mkdir(parents=True, exist_ok=True)
        for stale in stage_parent.glob(".stage-*"):
            if stale.is_dir():
                shutil.rmtree(stale, ignore_errors=True)
        stage = Path(tempfile.mkdtemp(prefix=".stage-", dir=str(stage_parent)))
        try:
            hashes = {}
            for key in KEYS:
                if cancel is not None and cancel.is_set():
                    raise RefreshCancelled("catalog refresh cancelled while staging")
                raw = _json_bytes({"_src": provider_fingerprint(source),
                                   "_data": values[key]})
                path = stage / FILES[key]
                with path.open("wb") as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
                hashes[key] = hashlib.sha256(raw).hexdigest()
            for kind in ("movie", "series"):
                counts = {}
                for item in values["xtream_streams_" + kind]:
                    category = str(item.get("category_id", ""))
                    counts[category] = counts.get(category, 0) + 1
                key = "xtream_counts_" + kind
                raw = _json_bytes(counts)
                with (stage / FILES[key]).open("wb") as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
                hashes[key] = hashlib.sha256(raw).hexdigest()
            manifest = {"schema": 1, "generation": generation,
                        "profile": profile_number,
                        "provider": provider_fingerprint(source), "files": hashes}
            _atomic_write(stage / "manifest.json", _json_bytes(manifest))
            if (set(hashes) != set(FILES)
                    or any(hashlib.sha256((stage / FILES[k]).read_bytes()).hexdigest()
                           != hashes[k] for k in FILES)):
                raise ValueError("staged catalog generation failed verification")
            _fsync_dir(stage)
            final_dir = stage_parent / generation
            os.replace(str(stage), str(final_dir))
            _fsync_dir(stage_parent)
            old_pointer = _read_pointer(pointer_path)
            if old_pointer and _valid_generation(directory, old_pointer):
                _atomic_write(previous_path, _json_bytes(old_pointer))
            pointer = {"schema": 1, "generation": generation,
                       "previous_generation": (old_pointer or {}).get("generation"),
                       "updated_at": time.time()}
            _atomic_write(pointer_path, _json_bytes(pointer))
            if not _valid_generation(directory, pointer):
                raise ValueError("published catalog generation failed verification")
            pin_generation(profile_dir, profile_number, source, generation)
            # shortcut: keep immutable generations; pruning needs cross-process reader leases.
            return {"generation": generation, "refreshed": True}
        finally:
            if stage.exists():
                shutil.rmtree(stage, ignore_errors=True)
