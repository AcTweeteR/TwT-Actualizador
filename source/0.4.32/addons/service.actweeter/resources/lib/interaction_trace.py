"""Opt-in, content-free correlation for detail-action touch experiments.

The skin calls ``arm`` only when its temporary interaction-trace setting is
enabled. This module records the action category, not the media title, URL,
provider, account, or playback metadata.
"""

from __future__ import annotations

import time
import uuid


PENDING_ID = "AcTweeteRInteractionPendingId"
PENDING_CONTROL = "AcTweeteRInteractionPendingControl"
PENDING_TIME = "AcTweeteRInteractionPendingTime"
ACTIVE_ID = "AcTweeteRInteractionActiveId"
ACTIVE_CONTROL = "AcTweeteRInteractionActiveControl"
TRACE_TTL_SECONDS = 120.0
_CONTROLS = frozenset(("play", "resume", "trailer"))
_VARIANTS = frozenset(("button", "radiobutton"))


def arm(window, control, variant, *, log, clock=time.time, correlation_factory=None,
        dialog_id=None, focus_id=None):
    """Record a user action dispatch; return its opaque correlation id."""
    if window is None:
        return None
    control = str(control).strip().casefold()
    variant = str(variant).strip().casefold()
    if control not in _CONTROLS or variant not in _VARIANTS:
        return None
    correlation_id = (correlation_factory or (lambda: uuid.uuid4().hex[:12]))()
    window.setProperty(PENDING_ID, correlation_id)
    window.setProperty(PENDING_CONTROL, control)
    window.setProperty(PENDING_TIME, str(float(clock())))
    safe_dialog_id = dialog_id if type(dialog_id) is int else "unknown"
    safe_focus_id = focus_id if type(focus_id) is int else "unknown"
    log("[AcTweeteR] INTERACTION_ACTION_DISPATCH correlation=%s control=%s variant=%s dialog=%s focus=%s" %
        (correlation_id, control, variant, safe_dialog_id, safe_focus_id))
    return correlation_id


def player_started(window, *, log, clock=time.time):
    """Correlate the next AV-start callback with a recent action dispatch."""
    if window is None:
        return False
    # A new playback supersedes any prior experiment correlation. Otherwise a
    # later stop from an unrelated item could be attributed to the old click.
    window.clearProperty(ACTIVE_ID)
    window.clearProperty(ACTIVE_CONTROL)
    correlation_id = window.getProperty(PENDING_ID)
    if not correlation_id:
        return False
    control = window.getProperty(PENDING_CONTROL)
    try:
        age = float(clock()) - float(window.getProperty(PENDING_TIME))
    except (TypeError, ValueError):
        age = TRACE_TTL_SECONDS + 1
    window.clearProperty(PENDING_ID)
    window.clearProperty(PENDING_CONTROL)
    window.clearProperty(PENDING_TIME)
    if control not in _CONTROLS or age < 0 or age > TRACE_TTL_SECONDS:
        log("[AcTweeteR] INTERACTION_PLAYBACK_UNCORRELATED reason=expired")
        return False
    window.setProperty(ACTIVE_ID, correlation_id)
    window.setProperty(ACTIVE_CONTROL, control)
    log("[AcTweeteR] INTERACTION_AV_STARTED correlation=%s control=%s" %
        (correlation_id, control))
    return True


def player_terminal(window, event, *, log):
    """Record an AV terminal callback for the last correlated action."""
    if window is None:
        return False
    if event not in ("stopped", "ended", "error"):
        return False
    correlation_id = window.getProperty(ACTIVE_ID)
    control = window.getProperty(ACTIVE_CONTROL)
    if not correlation_id or control not in _CONTROLS:
        return False
    window.clearProperty(ACTIVE_ID)
    window.clearProperty(ACTIVE_CONTROL)
    log("[AcTweeteR] INTERACTION_AV_TERMINAL correlation=%s control=%s event=%s" %
        (correlation_id, control, event))
    return True
