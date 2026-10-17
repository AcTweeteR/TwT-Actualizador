"""Interruptible, injectable hourly background task scheduler."""

from __future__ import annotations

import time


DEFAULT_INTERVAL_SECONDS = 3600


def is_due(last_success: float, now: float | None = None,
           interval: int = DEFAULT_INTERVAL_SECONDS) -> bool:
    now = time.time() if now is None else now
    return last_success <= 0 or now - last_success >= interval


def run_once(monitor, callback, *, last_success: float,
             interval: int = DEFAULT_INTERVAL_SECONDS) -> tuple[bool, float]:
    """Run a cooperative callback only when due; false means skipped/aborted."""
    if monitor.abortRequested() or not is_due(last_success, interval=interval):
        return False, last_success
    result = callback(monitor)
    if monitor.abortRequested() or result is not True:
        return False, last_success
    return True, time.time()
