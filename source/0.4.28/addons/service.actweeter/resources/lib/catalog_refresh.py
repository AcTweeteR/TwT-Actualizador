"""Secret-free state machine for the private XStream catalog-refresh bridge."""
import json
import os
import time
import uuid
from pathlib import Path


BUSY_TTL_SECONDS = 1800
LOCK_TTL_SECONDS = 120


def new_request_id():
    return uuid.uuid4().hex


def _read(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            os.chmod(temporary, 0o600)
            json.dump(value, stream, ensure_ascii=True, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temporary), str(path))
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass


def begin_refresh(path, request_id, profile_number, *, now=None, trace=None):
    """Persist IN_PROGRESS once; refuse a second live request."""
    if (not isinstance(request_id, str) or len(request_id) != 32
            or any(char not in "0123456789abcdef" for char in request_id)):
        raise ValueError("invalid catalog refresh request id")
    if type(profile_number) is not int or not 1 <= profile_number <= 10:
        raise ValueError("invalid XStream profile number")
    now = float(time.time() if now is None else now)
    path = Path(path)
    lock = path.with_name(path.name + ".lock")
    try:
        descriptor = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        try:
            if now - lock.stat().st_mtime <= LOCK_TTL_SECONDS:
                return False
            lock.unlink()
            descriptor = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except (FileNotFoundError, FileExistsError, OSError):
            return False
    try:
        os.close(descriptor)
        current = _read(path)
        if (current.get("status") == "IN_PROGRESS"
                and now - float(current.get("started_at", now)) < BUSY_TTL_SECONDS):
            return False
        value = {"schema": 1, "status": "IN_PROGRESS",
                 "request_id": request_id, "profile_number": profile_number,
                 "started_at": now}
        if trace:
            # Keep only the privacy-filtered trace tuple, never the plugin URI.
            value["trace"] = {key: trace[key] for key in
                               ("route", "source", "started_monotonic")}
        _write(path, value)
        return True
    finally:
        try:
            lock.unlink()
        except OSError:
            pass


def finish_refresh(path, request_id, success, *, now=None):
    """Accept only the matching callback for the current in-flight request."""
    if type(success) is not bool:
        return False
    state = _read(path)
    if (state.get("status") != "IN_PROGRESS"
            or state.get("request_id") != request_id):
        return False
    state["status"] = "COMPLETED" if success else "ERROR"
    state["finished_at"] = float(time.time() if now is None else now)
    _write(path, state)
    return True


def refresh_trace(path, request_id):
    """Return a sanitized trace record for one pending callback, if present."""
    state = _read(path)
    if state.get("request_id") != request_id or state.get("status") != "IN_PROGRESS":
        return None
    trace = state.get("trace")
    if not isinstance(trace, dict):
        return None
    if (not isinstance(trace.get("route"), str)
            or not isinstance(trace.get("source"), str)
            or type(trace.get("started_monotonic")) not in (int, float)):
        return None
    return {"correlation_id": request_id, **trace}


def read_refresh(path):
    state = _read(path)
    # Expose only state needed by the UI/diagnostics, never request internals.
    return {key: state[key] for key in ("status", "started_at", "finished_at")
            if key in state}
