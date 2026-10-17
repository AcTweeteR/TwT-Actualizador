"""Lightweight invalidation for provider-backed Continue Watching widgets."""
from __future__ import annotations

import uuid


def invalidate_continue_widgets(kodi, event, *, token_factory=None):
    """Change the widget route token and refresh the active AcTweeteR surface.

    XStream owns resume-point persistence and the listing route. This helper
    only tells Kodi's skin containers that their existing route may have new
    results after playback has ended. It never queries the provider itself.
    """
    token = (token_factory or (lambda: uuid.uuid4().hex))()
    try:
        kodi.executebuiltin(
            "SetProperty(Premium.ContinueRefresh,%s,Home)" % token, False)
    except Exception as exc:
        kodi.log("[AcTweeteR] CONTINUE_WIDGET_REFRESH status=property_error "
                 "event=%s error_type=%s" % (event, type(exc).__name__),
                 getattr(kodi, "LOGWARNING", 2))
        return {"status": "property_error", "scheduled": False}

    active = False
    try:
        active = bool(kodi.getCondVisibility("Window.IsActive(Home)")) or bool(
            kodi.getCondVisibility("Window.IsActive(1111)"))
    except Exception:
        # The route token remains valid and will be consumed when the user
        # next opens Home or the Movies hub; do not guess at another window.
        pass

    if active:
        try:
            kodi.executebuiltin(
                "CancelAlarm(AcTweeteRContinueRefresh,silent)", False)
            kodi.executebuiltin(
                "AlarmClock(AcTweeteRContinueRefresh,Container.Refresh,"
                "00:00:02,silent)", False)
        except Exception as exc:
            kodi.log("[AcTweeteR] CONTINUE_WIDGET_REFRESH status=alarm_error "
                     "event=%s error_type=%s" % (event, type(exc).__name__),
                     getattr(kodi, "LOGWARNING", 2))
            return {"status": "alarm_error", "scheduled": False}

    kodi.log("[AcTweeteR] CONTINUE_WIDGET_REFRESH status=invalidated "
             "event=%s scheduled=%d" % (event, active),
             getattr(kodi, "LOGINFO", 1))
    return {"status": "invalidated", "scheduled": active}
