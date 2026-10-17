"""Privacy-safe tracing for AcTweeteR-owned Kodi plug-in dispatches.

Kodi does not expose a completion callback for every asynchronous RunPlugin
builtin. Callers must therefore distinguish dispatch from query completion.
This module deliberately records no full URI, query string, title, or provider
data; only a validated add-on ID and an allow-listed operation are emitted.
"""

from __future__ import annotations

import datetime
import re
import time
import uuid
from urllib.parse import parse_qs, urlsplit


_ADDON_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_SOURCE = re.compile(r"^[a-z0-9_.-]{1,64}$")
_OPERATIONS = frozenset({
    "actweeter_refresh_profile", "search_sync", "movies_menu", "series_menu",
    "recent_tv", "continue", "favorites", "pending_root", "search",
})


def normalized_route(uri: str) -> str:
    """Return a safe route identity, dropping credentials and all parameters."""
    try:
        parsed = urlsplit(str(uri))
        addon_id = parsed.netloc
        if parsed.scheme.casefold() != "plugin" or not _ADDON_ID.fullmatch(addon_id):
            return "plugin://unknown/unknown"
        operation = (parse_qs(parsed.query, keep_blank_values=False).get("mode") or [""])[0]
        if operation not in _OPERATIONS:
            view = (parse_qs(parsed.query, keep_blank_values=False).get("view") or [""])[0]
            operation = view if view in _OPERATIONS else "unknown"
        return "plugin://%s/%s" % (addon_id, operation)
    except (TypeError, ValueError):
        return "plugin://unknown/unknown"


def begin(uri: str, source: str, *, correlation_id: str | None = None,
          log, wall_clock=time.time, monotonic=time.monotonic):
    """Create one trace and log query start without retaining the supplied URI."""
    source = str(source)
    if not _SOURCE.fullmatch(source):
        raise ValueError("invalid trace source")
    correlation_id = correlation_id or uuid.uuid4().hex
    if not re.fullmatch(r"[0-9a-f]{32}", correlation_id):
        raise ValueError("invalid correlation id")
    trace = {
        "correlation_id": correlation_id,
        "route": normalized_route(uri),
        "source": source,
        "started_monotonic": float(monotonic()),
    }
    emit(trace, "start", log=log, wall_clock=wall_clock, monotonic=monotonic)
    return trace


def emit(trace, state: str, *, log, error_type: str = "", wall_clock=time.time,
         monotonic=time.monotonic):
    """Log one lifecycle event. Error text is never accepted, only its type."""
    if state not in {"start", "dispatched", "finished", "error", "cancel_requested",
                     "unobserved"}:
        raise ValueError("invalid trace state")
    elapsed_ms = max(0, int((float(monotonic()) - trace["started_monotonic"]) * 1000))
    error = ""
    if state == "error":
        error = str(error_type)
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", error):
            error = "UnknownError"
    timestamp = datetime.datetime.fromtimestamp(
        float(wall_clock()), datetime.timezone.utc).isoformat(timespec="milliseconds")
    log("[AcTweeteR] PLUGIN_QUERY timestamp=%s correlation=%s route=%s source=%s "
        "state=%s elapsed_ms=%d error=%s" % (
            timestamp, trace["correlation_id"], trace["route"], trace["source"],
            state, elapsed_ms, error or "none"))

