"""Secret-free state machine for the private XStream catalog-refresh bridge."""
import json
import os
import time
import uuid
import contextlib
from pathlib import Path


BUSY_TTL_SECONDS = 1800
LOCK_TTL_SECONDS = 120
SEARCH_REFRESH_TIMEOUT_SECONDS = 30 * 60
TERMINAL_SEARCH_STATES = frozenset(("COMPLETED", "ERROR", "TIMEOUT",
                                   "CANCELLED", "INTERRUPTED"))


@contextlib.contextmanager
def _operation_guard(path):
    lock_path = Path(str(path) + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    stream = lock_path.open("a+b")
    try:
        try:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            unlock = lambda: fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        except ImportError:
            import msvcrt
            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b"\0")
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
            unlock = lambda: (stream.seek(0), msvcrt.locking(
                stream.fileno(), msvcrt.LK_UNLCK, 1))
        try:
            yield
        finally:
            unlock()
    finally:
        stream.close()


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


def _search_operation_path(profile_dir, request_id):
    if (not isinstance(request_id, str) or len(request_id) != 32
            or any(char not in "0123456789abcdef" for char in request_id)):
        raise ValueError("invalid search refresh request id")
    return Path(profile_dir) / "search_refresh_operations" / (request_id + ".json")


def begin_search_operation(profile_dir, request_id, profile_number, *, now=None):
    """Persist a cross-runtime automatic refresh lifecycle before dispatch."""
    if type(profile_number) is not int or not 1 <= profile_number <= 10:
        raise ValueError("invalid XStream profile number")
    path = _search_operation_path(profile_dir, request_id)
    now = float(time.time() if now is None else now)
    _write(path, {"schema": 1, "request_id": request_id,
                  "profile_number": profile_number, "status": "IN_PROGRESS",
                  "started_at": now})
    return str(path)


def finish_search_operation(profile_dir, request_id, outcome, *, now=None):
    """Accept one callback and persist an unambiguous terminal operation state."""
    states = {"success": "COMPLETED", "error": "ERROR", "timeout": "TIMEOUT",
              "cancelled": "CANCELLED", "interrupted": "INTERRUPTED"}
    status = states.get(str(outcome).casefold())
    if status is None:
        return False
    path = _search_operation_path(profile_dir, request_id)
    with _operation_guard(path):
        state = _read(path)
        if state.get("request_id") != request_id or state.get("status") != "IN_PROGRESS":
            return False
        state.update(status=status, finished_at=float(time.time() if now is None else now))
        _write(path, state)
        return True


def search_operation(profile_dir, request_id):
    """Read lifecycle fields only; operation files contain no provider data."""
    state = _read(_search_operation_path(profile_dir, request_id))
    return {key: state[key] for key in
            ("status", "started_at", "finished_at", "profile_number")
            if key in state}


def _retry_state_path(profile_dir, profile_number):
    if type(profile_number) is not int or not 1 <= profile_number <= 10:
        raise ValueError("invalid XStream profile number")
    return Path(profile_dir) / ("search_refresh_retry_p%d.json" % profile_number)


def read_retry_state(profile_dir, profile_number):
    state = _read(_retry_state_path(profile_dir, profile_number))
    return {"failures": max(0, int(state.get("failures", 0) or 0)),
            "category": state.get("category", ""),
            "retry_at": max(0.0, float(state.get("retry_at", 0) or 0)),
            "automatic_blocked": state.get("automatic_blocked") is True}


def record_retry_result(profile_dir, profile_number, outcome, *, category="incomplete",
                        retry_after=0, now=None, jitter=None):
    """Persist bounded failure backoff independently of Kodi process lifetime."""
    path = _retry_state_path(profile_dir, profile_number)
    now = float(time.time() if now is None else now)
    with _operation_guard(path):
        previous = _read(path)
        if str(outcome).casefold() == "success":
            state = {"schema": 1, "profile_number": profile_number, "failures": 0,
                     "category": "", "retry_at": 0, "automatic_blocked": False}
        else:
            from search_background import retry_delay
            failures = min(1000000, max(0, int(previous.get("failures", 0) or 0)) + 1)
            delay = retry_delay(category, failures, retry_after=retry_after, jitter=jitter)
            state = {"schema": 1, "profile_number": profile_number,
                     "failures": failures, "category": category,
                     "retry_at": 0 if delay is None else now + delay,
                     "automatic_blocked": delay is None}
        _write(path, state)
        return {key: state[key] for key in
                ("failures", "category", "retry_at", "automatic_blocked")}


def recover_search_operations(profile_dir, *, now=None):
    """Close operations left in progress by a Kodi Service restart."""
    root = Path(profile_dir) / "search_refresh_operations"
    if not root.is_dir():
        return 0
    recovered = 0
    for path in root.glob("[0-9a-f]" * 32 + ".json"):
        with _operation_guard(path):
            state = _read(path)
            if state.get("status") != "IN_PROGRESS":
                continue
            state.update(status="INTERRUPTED",
                         finished_at=float(time.time() if now is None else now))
            _write(path, state)
            recovered += 1
            if type(state.get("profile_number")) is int:
                record_retry_result(profile_dir, state["profile_number"], "error",
                                    category="timeout", now=now, jitter=0)
    return recovered


def read_refresh(path):
    state = _read(path)
    # Expose only state needed by the UI/diagnostics, never request internals.
    return {key: state[key] for key in
            ("status", "started_at", "finished_at", "profile_number")
            if key in state}
