"""Low-frequency, non-overlapping dispatch gate for XStream-owned sync work."""
import json
import os
import tempfile
import threading
from pathlib import Path

DEFAULT_INTERVAL = 300
MAX_BACKOFF = 3600


def _read(path):
    target = Path(path)
    if target.is_symlink() or not target.is_file() or target.stat().st_size > 4096:
        return {'failures': 0, 'next_at': 0.0}
    try:
        data = json.loads(target.read_text('utf-8'))
        return data if isinstance(data, dict) else {'failures': 0, 'next_at': 0.0}
    except (OSError, ValueError, UnicodeError):
        return {'failures': 0, 'next_at': 0.0}


def _write(path, data):
    target = Path(path)
    if target.is_symlink() or target.parent.is_symlink():
        raise ValueError('unsafe scheduler state path')
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if target.parent.stat().st_mode & 0o077:
        raise PermissionError('scheduler directory must be private')
    fd, temporary = tempfile.mkstemp(prefix='.scheduler-', dir=str(target.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, sort_keys=True, separators=(',', ':'))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def record_result(path, *, success, now, interval=DEFAULT_INTERVAL):
    state = _read(path)
    if success:
        state = {'failures': 0, 'next_at': float(now) + max(DEFAULT_INTERVAL, int(interval))}
    else:
        failures = min(10, int(state.get('failures', 0) or 0) + 1)
        delay = min(MAX_BACKOFF, max(DEFAULT_INTERVAL, int(interval)) * (2 ** (failures - 1)))
        state = {'failures': failures, 'next_at': float(now) + delay}
    _write(path, state)
    return state


class Scheduler:
    """Persist dispatch timing and serialize calls within this service process."""
    def __init__(self, path, *, interval=DEFAULT_INTERVAL, clock=None):
        import time
        self.path = Path(path)
        self.interval = max(DEFAULT_INTERVAL, int(interval))
        self.clock = clock or time.time
        self._lock = threading.Lock()
        self._running = False

    def dispatch_if_due(self, dispatch, *, authorized, playing=False):
        if not authorized or playing or not self._lock.acquire(False):
            return False
        try:
            if self._running:
                return False
            now = self.clock()
            state = _read(self.path)
            if now < float(state.get('next_at', 0) or 0):
                return False
            self._running = True
            try:
                dispatch()
            except Exception:
                failures = min(10, int(state.get('failures', 0) or 0) + 1)
                delay = min(MAX_BACKOFF, self.interval * (2 ** (failures - 1)))
                _write(self.path, {'failures': failures, 'next_at': now + delay})
                return False
            _write(self.path, {'failures': 0, 'next_at': now + self.interval})
            return True
        finally:
            self._running = False
            self._lock.release()
