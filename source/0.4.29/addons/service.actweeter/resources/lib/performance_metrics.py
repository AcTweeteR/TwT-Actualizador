"""Bounded, privacy-safe performance counters; disabled unless explicitly opted in."""

from __future__ import annotations

import re
import time
from contextlib import contextmanager


_METRIC = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
MAX_METRICS = 64


class PerformanceRecorder:
    """Aggregate counts and timings without retaining events or user data."""

    def __init__(self, enabled=False, *, log=None, clock=time.perf_counter):
        self.enabled = bool(enabled)
        self.log = log
        self.clock = clock
        self._values = {}
        self._usage_start = process_usage() if self.enabled else {}

    def _entry(self, name):
        name = str(name)
        if not _METRIC.fullmatch(name):
            raise ValueError("invalid performance metric name")
        if name not in self._values and len(self._values) >= MAX_METRICS:
            raise ValueError("performance metric limit reached")
        return self._values.setdefault(name, {"count": 0, "total_ms": 0.0, "max_ms": 0.0})

    def count(self, name, amount=1):
        if not self.enabled:
            return
        if type(amount) is not int or amount < 0:
            raise ValueError("performance counter amount must be a non-negative integer")
        self._entry(name)["count"] += amount

    def timing(self, name, elapsed_ms):
        if not self.enabled:
            return
        elapsed_ms = float(elapsed_ms)
        if elapsed_ms != elapsed_ms or elapsed_ms in (float("inf"), -float("inf")):
            raise ValueError("performance timing must be finite")
        elapsed_ms = max(0.0, elapsed_ms)
        entry = self._entry(name)
        entry["count"] += 1
        entry["total_ms"] += elapsed_ms
        entry["max_ms"] = max(entry["max_ms"], elapsed_ms)

    @contextmanager
    def measure(self, name):
        if not self.enabled:
            yield
            return
        started = self.clock()
        try:
            yield
        finally:
            self.timing(name, (self.clock() - started) * 1000.0)

    def snapshot(self):
        return {name: dict(value) for name, value in sorted(self._values.items())}

    def emit_summary(self):
        """Emit aggregate metric names/numbers only; no URI, title, or profile."""
        if not self.enabled or not callable(self.log):
            return False
        for name, value in self.snapshot().items():
            mean_ms = value["total_ms"] / value["count"] if value["count"] else 0.0
            self.log("[AcTweeteR] PERF metric=%s count=%d total_ms=%.3f mean_ms=%.3f max_ms=%.3f" % (
                name, value["count"], value["total_ms"], mean_ms, value["max_ms"]))
        usage = process_usage()
        if usage:
            start = self._usage_start
            cpu_user = usage.get("user_cpu_seconds", 0.0) - start.get("user_cpu_seconds", 0.0)
            cpu_system = usage.get("system_cpu_seconds", 0.0) - start.get("system_cpu_seconds", 0.0)
            rss = usage.get("peak_rss_bytes")
            self.log("[AcTweeteR] PERF process_usage user_cpu_delta_s=%.3f "
                     "system_cpu_delta_s=%.3f peak_rss_bytes=%s" % (
                         max(0.0, cpu_user), max(0.0, cpu_system),
                         str(rss) if rss is not None else "unavailable"))
        return True


def process_usage():
    """Return optional process CPU/RSS counters where Python exposes them.

    RSS is normalized to bytes on known Darwin and POSIX implementations;
    unavailable or unknown platform metrics are omitted, never guessed.
    """
    try:
        import resource
        import sys
        usage = resource.getrusage(resource.RUSAGE_SELF)
    except (ImportError, AttributeError, OSError):
        return {}
    result = {"user_cpu_seconds": float(usage.ru_utime),
              "system_cpu_seconds": float(usage.ru_stime)}
    rss = getattr(usage, "ru_maxrss", None)
    if type(rss) in (int, float) and rss >= 0:
        if sys.platform == "darwin":
            result["peak_rss_bytes"] = int(rss)
        elif sys.platform.startswith(("linux", "android")):
            result["peak_rss_bytes"] = int(rss * 1024)
    return result
