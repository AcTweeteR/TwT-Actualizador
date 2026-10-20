"""Opt-in per-invocation XStream timing; aggregates numeric, privacy-safe data."""

from __future__ import annotations

import json
import math
import re
import threading
import time
import uuid
from contextlib import contextmanager


_NAME = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_ROUTES = frozenset({
    "catalog", "recent", "popular", "trending", "series_recent", "favorites",
    "pending", "continue", "year", "genre", "premiere", "search_input",
})
_MAX_PHASES = 48


class PerformanceTrace:
    """Collect timings and process counters for one XStream plugin process."""

    def __init__(self, *, log, clock=time.perf_counter):
        self.log = log
        self.clock = clock
        self.correlation_id = uuid.uuid4().hex
        self.route = "unknown"
        self.media = "other"
        self.phases = {}
        self.counts = {}
        self._lock = threading.Lock()
        self._started = clock()
        self._usage_start = _process_usage()
        self._io_start = _io_counters()

    def set_context(self, route, media):
        self.route = route if route in _ROUTES else "unknown"
        self.media = media if media in ("movie", "series") else "other"

    def timing(self, name, elapsed_ms):
        if not _NAME.fullmatch(name):
            raise ValueError("invalid performance phase")
        elapsed_ms = float(elapsed_ms)
        if not math.isfinite(elapsed_ms):
            raise ValueError("performance duration must be finite")
        elapsed_ms = max(0.0, elapsed_ms)
        with self._lock:
            if name not in self.phases and len(self.phases) >= _MAX_PHASES:
                raise ValueError("performance phase limit reached")
            entry = self.phases.setdefault(name, {"count": 0, "total_ms": 0.0, "max_ms": 0.0})
            entry["count"] += 1
            entry["total_ms"] += elapsed_ms
            entry["max_ms"] = max(entry["max_ms"], elapsed_ms)

    def count(self, name, amount=1):
        if not _NAME.fullmatch(name) or type(amount) is not int or amount < 0:
            raise ValueError("invalid performance counter")
        with self._lock:
            if name not in self.counts and len(self.counts) >= _MAX_PHASES:
                raise ValueError("performance counter limit reached")
            self.counts[name] = self.counts.get(name, 0) + amount

    @contextmanager
    def measure(self, name):
        started = self.clock()
        try:
            yield
        finally:
            self.timing(name, (self.clock() - started) * 1000.0)

    def call(self, name, function, *args, **kwargs):
        self.count(name + ".calls")
        try:
            with self.measure(name):
                return function(*args, **kwargs)
        except Exception:
            self.count(name + ".errors")
            raise

    def instrument_cache(self, namespace):
        """Time common JSON cache helpers without recording cache keys."""
        for helper, phase in (("_cache_load", "cache.json.read"),
                              ("_cache_save", "cache.json.write")):
            original = namespace.get(helper)
            if not callable(original):
                continue

            def measured(*args, _original=original, _phase=phase, **kwargs):
                try:
                    result = self.call(_phase, _original, *args, **kwargs)
                except Exception:
                    raise
                if _phase == "cache.json.read":
                    self.count("cache.read.hit" if result else "cache.read.miss")
                return result

            namespace[helper] = measured

    def instrument_provider(self, provider):
        """Time Xtream calls without logging any method arguments or URLs."""
        for method, phase in (("get_xtream_streams", "external.xtream.streams"),
                              ("get_xtream_categories", "external.xtream.categories"),
                              ("get_vod_info", "external.xtream.vod_info"),
                              ("get_xtream_series_info", "external.xtream.series_info")):
            original = getattr(provider, method, None)
            if not callable(original):
                continue

            def measured(*args, _original=original, _phase=phase, **kwargs):
                return self.call(_phase, _original, *args, **kwargs)

            setattr(provider, method, staticmethod(measured))

    def emit(self):
        usage = _process_usage()
        io = _io_counters()
        with self._lock:
            phases = {name: dict(value) for name, value in self.phases.items()}
            counts = dict(self.counts)
        payload = {
            "correlation": self.correlation_id,
            "route": self.route,
            "media": self.media,
            "elapsed_ms": round((self.clock() - self._started) * 1000.0, 3),
            "phases": phases,
            "counts": counts,
            "process": _usage_delta(self._usage_start, usage),
            "threads": threading.active_count(),
            "io_delta": _counter_delta(self._io_start, io),
        }
        try:
            self.log("[XStream] PERFORMANCE_DIAGNOSTICS " + json.dumps(
                payload, sort_keys=True, separators=(",", ":")))
        except Exception:
            pass


def _process_usage():
    try:
        import resource
        import sys
        usage = resource.getrusage(resource.RUSAGE_SELF)
        result = {
            "user_cpu_s": float(usage.ru_utime),
            "system_cpu_s": float(usage.ru_stime),
        }
        rss = getattr(usage, "ru_maxrss", None)
        if type(rss) in (int, float) and rss >= 0:
            result["peak_rss_bytes"] = int(rss if sys.platform == "darwin" else rss * 1024)
        for source, target in (("ru_inblock", "block_in"), ("ru_oublock", "block_out")):
            value = getattr(usage, source, None)
            if type(value) in (int, float) and value >= 0:
                result[target] = int(value)
        return result
    except (ImportError, AttributeError, OSError):
        return {}


def _io_counters():
    """Linux/Android process I/O counters; omit them where the OS has none."""
    try:
        with open("/proc/self/io", "r", encoding="ascii") as stream:
            return {key: int(value) for line in stream
                    for key, value in (line.split(":", 1),)
                    if key in ("read_bytes", "write_bytes")}
    except (OSError, ValueError):
        return {}


def _usage_delta(start, end):
    result = {}
    for key in ("user_cpu_s", "system_cpu_s"):
        if key in start and key in end:
            result[key] = round(max(0.0, end[key] - start[key]), 6)
    if "peak_rss_bytes" in end:
        result["peak_rss_bytes"] = end["peak_rss_bytes"]
    for key in ("block_in", "block_out"):
        if key in start and key in end:
            result[key] = max(0, end[key] - start[key])
    return result


def _counter_delta(start, end):
    return {key: max(0, end[key] - start.get(key, end[key]))
            for key in end if type(end[key]) is int}
