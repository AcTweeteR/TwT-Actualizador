"""Conservative PVR guide freshness gate.

An XMLTV file can be syntactically valid and have hundreds of thousands of
expired programmes. Only source data with actual programme coverage may replace
an existing guide. Never persist credentials or raw feed URLs in diagnostics.
"""
from __future__ import annotations

import os
import time


def should_refresh(path, *, now=None, max_age_hours=4):
    clock = time.time() if now is None else now
    try:
        stat = os.stat(path)
        return stat.st_size == 0 or (clock - stat.st_mtime) > max_age_hours * 3600
    except OSError:
        return True


def current_coverage(programs, *, now=None):
    """Count channels with a programme whose UTC interval contains now."""
    from epg import _parse_xmltv_time
    clock = time.time() if now is None else now
    valid = 0
    total = 0
    for rows in programs.values():
        if not rows:
            continue
        total += 1
        # Provider parses and sorts programmes in increasing start order.
        for row in reversed(rows):
            try:
                stop = _parse_xmltv_time(row.get("stop", ""))
                if stop <= clock:
                    break
                start = _parse_xmltv_time(row.get("start", ""))
            except (ValueError, TypeError, OverflowError):
                continue
            if start <= clock < stop:
                valid += 1
                break
    return valid, total


def acceptable(programs, *, now=None):
    if not isinstance(programs, dict) or not programs:
        return False
    current, channels = current_coverage(programs, now=now)
    # A small, genuinely narrow provider may have only one programme-bearing
    # channel. For a 1000-channel provider, 5 active channels is not a usable EPG.
    required = max(1, min(8, channels // 50))
    return current >= required
