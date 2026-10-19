"""Kodi-native scheduling helpers for the XStream provider-only index."""

from __future__ import annotations

import os
import math
import re
import sqlite3
from pathlib import Path


DEFAULT_INTERVAL_SECONDS = 3600
COORDINATOR_REFRESH_CHECK_SECONDS = 300
COORDINATOR_PENDING_CHECK_SECONDS = 60


def xstream_profile_number(active_profile: str) -> int:
    value = active_profile or "Profile 1"
    if not isinstance(value, str):
        raise ValueError("invalid XStream profile type")
    match = re.fullmatch(r"Profile ([1-9]|10)", value.strip(), re.I)
    if not match:
        raise ValueError("invalid XStream active profile")
    return int(match.group(1))


def last_successful_sync(profile_path: str, profile_number: int) -> float:
    """Read one scalar timestamp, never returning any personal row/value."""
    if type(profile_number) is not int or not 1 <= profile_number <= 10:
        raise ValueError("unsupported XStream profile number")
    path = os.path.join(profile_path, "provider_search_%d.sqlite" % profile_number)
    if not os.path.exists(path) or os.path.islink(path) or not os.path.isfile(path):
        return 0.0
    try:
        uri = Path(path).absolute().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=2)
        try:
            row = conn.execute(
                "SELECT value FROM meta WHERE key='last_successful_sync'"
            ).fetchone()
            timestamp = float(row[0]) if row else 0.0
            return max(0.0, timestamp) if math.isfinite(timestamp) else 0.0
        finally:
            conn.close()
    except (OSError, ValueError, sqlite3.Error):
        return 0.0


def refresh_due(last_sync: float, now: float, interval: int = DEFAULT_INTERVAL_SECONDS) -> bool:
    return (math.isfinite(last_sync) and math.isfinite(now) and
            (last_sync <= 0 or last_sync > now + COORDINATOR_REFRESH_CHECK_SECONDS
             or now - last_sync >= interval))


def refresh_state_check_due(now: float, next_check: float, *, pending: bool = False) -> bool:
    """Check provider refresh state every five minutes, or every tick while pending."""
    return pending or float(now) >= float(next_check)


class RefreshGate:
    """Allow one background request per interval even if it is still running."""

    def __init__(self, interval: int = DEFAULT_INTERVAL_SECONDS):
        self.interval = interval
        self.last_request = None

    def should_request(self, last_sync: float, now: float, *, abort: bool = False) -> bool:
        return (not abort and refresh_due(last_sync, now, self.interval)
                and (self.last_request is None or
                     now < self.last_request - COORDINATOR_REFRESH_CHECK_SECONDS or
                     now - self.last_request >= self.interval))

    def mark_requested(self, now: float) -> None:
        self.last_request = now


def plugin_refresh_url(profile_number: int) -> str:
    if type(profile_number) is not int:
        raise ValueError("invalid XStream profile number")
    number = profile_number
    if not 1 <= number <= 10:
        raise ValueError("unsupported XStream profile")
    return ("plugin://plugin.video.xstream-pro/?mode=premium&view=search_sync"
            "&profile_num=%d" % number)
