"""Refresh watched state and AcTweeteR widgets after a confirmed local mutation.

RunPlugin is called from a Kodi context-menu dialog. Refresh immediately while
that modal closes can be ignored. The property changes the widget source URLs
and an idle one-shot delayed refresh lets Kodi rebuild the current directory.
No Trakt action, profile mutation or provider network call is made here.
"""
from __future__ import annotations

import time


def invalidate_after_watched_mutation(g, *, event):
    kodi = g['xbmc']
    try:
        window = g['xbmcgui'].Window(10000)
        stamp = str(time.time_ns())
        # These two tokens are already referenced by the generated skin routes.
        # Including both covers ordinary movie widgets and Continue Watching.
        for key in ('Premium.CollectionsRefresh', 'Premium.ContinueRefresh',
                    'AcTweeteR.WatchedRefresh'):
            window.setProperty(key, stamp)
    except (AttributeError, RuntimeError, TypeError) as exc:
        kodi.log('[AcTweeteR] WATCHED_UI_REFRESH status=property_error event=%s type=%s' %
                 (event, type(exc).__name__), getattr(kodi, 'LOGWARNING', 2))
        return {'status': 'property_error', 'scheduled': False}

    try:
        # Do not interrupt playback, even if the mark comes from a nested menu.
        playing = bool(kodi.getCondVisibility('Player.HasMedia'))
    except (AttributeError, RuntimeError):
        playing = False
    if not playing:
        try:
            kodi.executebuiltin('CancelAlarm(AcTweeteRWatchedRefresh,silent)')
            kodi.executebuiltin(
                'AlarmClock(AcTweeteRWatchedRefresh,Container.Refresh,00:00:02,silent)')
        except (AttributeError, RuntimeError, TypeError) as exc:
            kodi.log('[AcTweeteR] WATCHED_UI_REFRESH status=schedule_error event=%s type=%s' %
                     (event, type(exc).__name__), getattr(kodi, 'LOGWARNING', 2))
            return {'status': 'schedule_error', 'scheduled': False}
    kodi.log('[AcTweeteR] WATCHED_UI_REFRESH status=invalidated event=%s deferred=%d' %
             (event, not playing), getattr(kodi, 'LOGINFO', 1))
    return {'status': 'invalidated', 'scheduled': not playing}
