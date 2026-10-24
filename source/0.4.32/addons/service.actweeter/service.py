"""Kodi service lifecycle and background refresh coordinator."""

from __future__ import annotations

import os
import time
import sys
import json
import base64
import uuid
import threading

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs


ADDON = xbmcaddon.Addon()
ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo("path"))
LIB_PATH = os.path.join(ADDON_PATH, "resources", "lib")
if LIB_PATH not in sys.path:
    sys.path.insert(0, LIB_PATH)

# Read-only boot gate. An interrupted two-store restore must be recovered
# outside the running Kodi process before any subsequent restore is allowed.
def _check_trakt_restore_on_boot():
    try:
        from pathlib import Path
        resources_parent = os.path.join(ADDON_PATH, "resources")
        if resources_parent not in sys.path:
            sys.path.insert(0, resources_parent)
        from lib.trakt_restore_bootcheck import inspect_all_profiles
        profile = xbmcvfs.translatePath('special://profile/addon_data/plugin.video.xstream-pro')
        status = inspect_all_profiles(profile,
            lambda message: xbmc.log('[AcTweeteR] ' + message, xbmc.LOGWARNING))
        return status
    except Exception as exc:
        xbmc.log('[AcTweeteR] Trakt boot check unavailable: ' + type(exc).__name__, xbmc.LOGWARNING)
        return {'safe': False, 'reason': 'boot_check_failed'}


_check_trakt_restore_on_boot()

from search_background import (last_successful_sync, plugin_refresh_url,
                               refresh_interval, RefreshGate,
                               xstream_profile_number)  # noqa: E402
from slyguy_trailer_return import (  # noqa: E402
    capture_context, identity_matches, parse_identity, return_decision,
    manual_exit_requires_stop,
    marker_cleanup_allowed, TerminalEventGate,
)
from kodi_auto_preview import KodiAutoPreviewCoordinator  # noqa: E402
from playing_video_item import get_playing_video_item  # noqa: E402
from interface_layout import SpotlightRotation
from plugin_query_trace import begin as begin_plugin_trace, emit as emit_plugin_trace  # noqa: E402
from continue_widgets import invalidate_continue_widgets  # noqa: E402
from performance_metrics import PerformanceRecorder  # noqa: E402
from interaction_trace import player_started as trace_player_started  # noqa: E402
from interaction_trace import player_terminal as trace_player_terminal  # noqa: E402
from search_background import (COORDINATOR_PENDING_CHECK_SECONDS,
                               COORDINATOR_REFRESH_CHECK_SECONDS,
                               refresh_state_check_due)  # noqa: E402
from catalog_refresh import (SEARCH_REFRESH_TIMEOUT_SECONDS,
                             begin_search_operation, finish_search_operation,
                             recover_search_operations, search_operation,
                             read_retry_state, record_retry_result)  # noqa: E402
from trakt_sync_consent import enabled as trakt_sync_enabled  # noqa: E402
from trakt_sync_scheduler import Scheduler as TraktSyncScheduler  # noqa: E402


_MONITOR_BASE = getattr(xbmc, "Monitor", object)
if isinstance(_MONITOR_BASE, type):
    class AcTweeteRMonitor(_MONITOR_BASE):
        def __init__(self, preview):
            super().__init__()
            self.preview = preview

        def onNotification(self, sender, method, data):
            if (sender in ("service.actweeter.SIGNAL", "slyguy.trailers.SIGNAL") or
                    method == "actweeter_auto_preview"):
                kind = type(data).__name__
                shape = "none"
                try:
                    parsed = json.loads(data) if isinstance(data, str) else data
                    shape = ("list:%d" % len(parsed) if isinstance(parsed, list) else
                             "dict" if isinstance(parsed, dict) else type(parsed).__name__)
                except (TypeError, ValueError):
                    shape = "invalid_json"
                xbmc.log("[AcTweeteR] AUTO_PREVIEW_NOTIFICATION sender=%s method=%s data_type=%s data_shape=%s" %
                         (sender, method, kind, shape), xbmc.LOGINFO)
            self.preview.on_notification(sender, method, data)
else:  # lightweight import harnesses may expose a factory rather than a class
    class AcTweeteRMonitor:
        def __new__(cls, preview):
            return xbmc.Monitor()


class _InactivePlayer:
    """Only for isolated imports that do not provide Kodi's Player API."""
    def getPlayingItem(self):
        raise RuntimeError("no player API in test harness")

    def stop(self):
        return None


def _window_id(kodi):
    """Read Kodi's active window ID without relying on translated labels."""
    try:
        response = json.loads(kodi.executeJSONRPC(json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "GUI.GetProperties",
            "params": {"properties": ["currentwindow"]},
        })))
        current = response.get("result", {}).get("currentwindow", {})
        value = current.get("id") if isinstance(current, dict) else None
        return value if type(value) is int else None
    except (TypeError, ValueError, AttributeError):
        return None


def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _trailer_identity_values(kodi, spotlight=False):
    item = "Container(1508).ListItem." if spotlight else "ListItem."
    return {
        "imdb": kodi.getInfoLabel(item + "UniqueID(imdb)"),
        "tmdb": kodi.getInfoLabel(item + "UniqueID(tmdb)"),
        "dbid": kodi.getInfoLabel(item + "DBID"),
    }


_PLAYER_BASE = getattr(xbmc, "Player", object)


class SlyGuyTrailerReturnPlayer(_PLAYER_BASE):
    """Observe explicitly armed SlyGuy trailers from supported skin surfaces."""

    def __init__(self, kodi, monitor, auto_preview=None):
        super().__init__()
        self.kodi = kodi
        self.monitor = monitor
        window_factory = getattr(xbmcgui, "Window", None)
        self.trace_window = window_factory(10000) if window_factory else None
        self.lock = threading.Lock()
        self.context = None
        self.terminal_gate = TerminalEventGate()
        self.auto_preview = auto_preview
        self.auto_request_identity = ""
        self.auto_request_generation = ""
        self.auto_request_id = ""
        self.intro_playback_active = False

    def _is_actweeter_intro(self):
        if self.kodi.getInfoLabel(
                "Window(Home).Property(AcTweeteRIntroPlayback)") != "1":
            return False
        try:
            playing_file = self.getPlayingFile()
        except Exception:
            return False
        return os.path.basename(str(playing_file).split("?", 1)[0]).casefold() == \
            "actweeter_intro_kodi.mp4"

    def _finish_intro(self, event):
        if not self.intro_playback_active and not self._is_actweeter_intro():
            return False
        self.intro_playback_active = False
        self.kodi.log("[AcTweeteR] INTRO_PLAYBACK_TERMINAL event=%s" % event,
                      self.kodi.LOGINFO)
        self.kodi.executebuiltin("ClearProperty(AcTweeteRIntroPlayback,Home)", False)
        self.kodi.executebuiltin("ClearProperty(StartupMask,Home)", False)
        self.kodi.executebuiltin("Dialog.Close(1103,true)", False)
        return True

    def _capture(self, *, allow_inactive=False):
        pending = self.kodi.getInfoLabel(
            "Window(Home).Property(SLYGUY_TRAILER_RETURN_PENDING)") == "1"
        explicit = self.kodi.getInfoLabel(
            "Window(Home).Property(SLYGUY_TRAILER_RETURN_REQUEST)") == "1"
        origin = self.kodi.getInfoLabel(
            "Window(Home).Property(SLYGUY_TRAILER_RETURN_ORIGIN)") or "VIDEO_INFO"
        source_window_id = _safe_int(self.kodi.getInfoLabel(
            "Window(Home).Property(SLYGUY_TRAILER_RETURN_WINDOW)"))
        return_control_id = _safe_int(self.kodi.getInfoLabel(
            "Window(Home).Property(SLYGUY_TRAILER_RETURN_CONTROL)"))
        vod_pending = bool(self.kodi.getInfoLabel(
            "Window(Home).Property(VOD_RETURN_PENDING)"))
        if not allow_inactive and not self.kodi.getCondVisibility("Player.HasVideo"):
            return None
        identity = self.kodi.getInfoLabel(
            "Window(Home).Property(SLYGUY_TRAILER_RETURN_ID)")
        identity_values = _trailer_identity_values(
            self.kodi, spotlight=origin.upper() == "SPOTLIGHT")
        if origin.upper() == "SPOTLIGHT":
            parsed = parse_identity(identity)
            # The stable identity was captured from Container(1508) before
            # SlyGuy took over the window. Revalidate it against the list on
            # return; the current playback window has no ListItem context.
            identity_values = ({parsed[0]: parsed[1]} if parsed else {})
        return capture_context(
            pending=pending, explicit_request=explicit, vod_pending=vod_pending,
            window_id=_window_id(self.kodi),
            item_type=(self.kodi.getInfoLabel(
                           "Window(Home).Property(SLYGUY_TRAILER_RETURN_TYPE)")
                       if origin.upper() == "SPOTLIGHT" else
                       self.kodi.getInfoLabel("ListItem.DBType")),
            identity=identity,
            current_values=identity_values,
            origin=origin,
            source_window_id=source_window_id,
            return_control_id=return_control_id,
        )

    def onAVStarted(self):
        trace_player_started(
            self.trace_window,
            log=lambda message: self.kodi.log(message, self.kodi.LOGINFO),
        )
        if self._is_actweeter_intro():
            self.intro_playback_active = True
            self.kodi.log("[AcTweeteR] INTRO_PLAYBACK_STARTED", self.kodi.LOGINFO)
            return
        if self.auto_preview is not None:
            try:
                item = self.getPlayingItem()
                owner = item.getProperty("AcTweeteR.PreviewOwner")
            except Exception:
                item = None
                owner = ""
            if owner == "AUTO_PREVIEW":
                self.auto_request_generation = item.getProperty(
                    "AcTweeteR.PreviewGeneration")
                self.auto_request_identity = item.getProperty(
                    "AcTweeteR.PreviewIdentity")
                self.auto_request_id = item.getProperty(
                    "AcTweeteR.PreviewRequestId")
                status = self.auto_preview.av_started(item)
                if status == "STALE_OWNED":
                    self.auto_preview.stop_stale_item(item)
                elif status == "ACCEPTED":
                    self.kodi.log("[AcTweeteR] AUTO_PREVIEW_AV_STARTED generation=%s" %
                                  self.auto_request_generation, self.kodi.LOGINFO)
                return
            manual_owner = self.kodi.getInfoLabel(
                "Window(Home).Property(SLYGUY_TRAILER_RETURN_ORIGIN)")
            if manual_owner in ("VIDEO_INFO", "SPOTLIGHT") and self.kodi.getInfoLabel(
                    "Window(Home).Property(SLYGUY_TRAILER_RETURN_PENDING)") == "1":
                self.auto_preview.external_playback_started(
                    "MANUAL_SPOTLIGHT" if manual_owner == "SPOTLIGHT" else "MANUAL_DETAIL")
            else:
                self.auto_preview.external_playback_started("OTHER")
            # Keep the displaced preview token until Kodi delivers its stop
            # callback; that callback owns its manifest cleanup even though a
            # manual/VOD item is now the active player.
        context = self._capture()
        if context is None:
            return
        with self.lock:
            if self.context is None:
                context["correlation_id"] = uuid.uuid4().hex[:12]
                context["playing_file"] = self.getPlayingFile()
                try:
                    source_window = xbmcgui.getCurrentWindowId()
                    source_control = xbmcgui.Window(source_window).getFocusId()
                    # Container labels belong to the active dialog until it
                    # closes; revalidate the source item on return, not here.
                    if source_window in (10000, 11110, 11111, 10025) and source_control > 0:
                        context["source_window_id"] = source_window
                        context["source_control_id"] = source_control
                except (RuntimeError, SystemError):
                    pass
                self.context = context
                self.terminal_gate = TerminalEventGate()
                # DialogVideoInfo may unload after natural EOF once Kodi has
                # already made Player.HasVideo false. Let its XML cleanup
                # distinguish that terminal transition from a pre-play cancel.
                self.kodi.executebuiltin(
                    "SetProperty(SLYGUY_TRAILER_RETURN_PLAYBACK_STARTED,1,Home)",
                    False)
                self.kodi.log(
                    "[AcTweeteR] SLYGUY_RETURN_CAPTURED correlation=%s origin=%s identity_kind=%s return_window=%s return_control=%s source_window=%s source_control=%s" %
                    (context["correlation_id"], context["origin"],
                     context["identity_kind"], context["return_window_id"],
                     context.get("return_control_id", "none"),
                     context.get("source_window_id", "none"),
                     context.get("source_control_id", "none")),
                    self.kodi.LOGINFO)

                threading.Thread(target=self._present_manual, args=(context,),
                                 name="AcTweeteR-ManualTrailer", daemon=True).start()

    def _present_manual(self, context):
        # SlyGuy must capture the detail ListItem before the dialog closes.
        if not self._request_is_current(context):
            return
        self.kodi.executebuiltin("Dialog.Close(movieinformation)", False)
        if not self._request_is_current(context) or not self.isPlayingVideo():
            return
        self.kodi.executebuiltin("ActivateWindow(fullscreenvideo)", False)
        fullscreen_seen = False
        while not self.monitor.waitForAbort(0.2):
            if not self.isPlayingVideo() or not self._request_is_current(context):
                return
            try:
                playing_file = self.getPlayingFile()
            except RuntimeError:
                return
            if playing_file != context["playing_file"]:
                return
            window_id = _window_id(self.kodi)
            fullscreen_seen = fullscreen_seen or window_id == 12005
            if manual_exit_requires_stop(
                    context, playing_file=playing_file, window_id=window_id,
                    fullscreen_seen=fullscreen_seen,
                    request_current=self._request_is_current(context)):
                self.kodi.log("[AcTweeteR] SLYGUY_MANUAL_EXIT owned_stop=1",
                              self.kodi.LOGINFO)
                self.stop()
                return

    def onPlayBackStopped(self):
        trace_player_terminal(
            self.trace_window, "stopped",
            log=lambda message: self.kodi.log(message, self.kodi.LOGINFO),
        )
        self._terminal("stopped")

    def onPlayBackEnded(self):
        trace_player_terminal(
            self.trace_window, "ended",
            log=lambda message: self.kodi.log(message, self.kodi.LOGINFO),
        )
        self._terminal("ended")

    def onPlayBackError(self):
        trace_player_terminal(
            self.trace_window, "error",
            log=lambda message: self.kodi.log(message, self.kodi.LOGINFO),
        )
        if self._finish_intro("error"):
            return
        # Errors may happen before AVStarted; accept only the same explicit
        # request marker and matching movie detail identity.
        with self.lock:
            missing_context = self.context is None
        if missing_context:
            context = self._capture(allow_inactive=True)
            if context is not None:
                with self.lock:
                    if self.context is None:
                        context["correlation_id"] = uuid.uuid4().hex[:12]
                        self.context = context
                        self.terminal_gate = TerminalEventGate()
        self._terminal("error")

    def _terminal(self, event):
        if self._finish_intro(event):
            return
        # Resume points are persisted by XStream. Invalidate only the skin's
        # route token; never query XStream or alter progress from this callback.
        # Previews and SlyGuy trailers do not create VOD resume entries.
        if (not self.auto_request_generation and
                self.kodi.getInfoLabel(
                    "Window(Home).Property(SLYGUY_TRAILER_RETURN_PENDING)") != "1"):
            invalidate_continue_widgets(self.kodi, event)
        if self.auto_preview is not None:
            # Timestamp Kodi's callback before touching Player APIs: those APIs
            # can wait on the playback lock and would obscure callback latency.
            self.auto_preview.player_terminal_event(event)
            item = get_playing_video_item(self)
            owner = item.getProperty("AcTweeteR.PreviewOwner") if item else ""
            if owner == "AUTO_PREVIEW" and self.auto_preview.terminal(item, event):
                self.kodi.log("[AcTweeteR] AUTO_PREVIEW_TERMINAL event=%s" % event,
                              self.kodi.LOGINFO)
                self.auto_request_generation = ""
                self.auto_request_identity = ""
                self.auto_request_id = ""
                return
            if self.auto_request_generation:
                try:
                    generation = int(self.auto_request_generation)
                except (TypeError, ValueError):
                    generation = -1
                if generation > 0 and self.auto_preview.terminal_by_identity(
                        generation, self.auto_request_identity,
                        self.auto_request_id, event):
                    self.kodi.log("[AcTweeteR] AUTO_PREVIEW_TERMINAL event=%s" % event,
                                  self.kodi.LOGINFO)
                    self.auto_request_generation = ""
                    self.auto_request_identity = ""
                    self.auto_request_id = ""
                    return
            if not owner and not self.auto_request_generation:
                # Player.play() can be accepted without an AVStarted callback
                # (for example a resolver/player error). Release only the
                # exact AcTweeteR handoff previously acknowledged by the
                # provider; never Stop or claim this untagged playback.
                self.auto_preview.terminal_unowned_launch(event)
            self.auto_preview.external_playback_ended()
        with self.lock:
            if self.context is None or not self.terminal_gate.claim(event):
                return
            context = dict(self.context)
        correlation = context.get("correlation_id", "none")
        self.kodi.log(
            "[AcTweeteR] SLYGUY_RETURN_TERMINAL correlation=%s origin=%s event=%s" %
            (correlation, context.get("origin", "VIDEO_INFO"), event),
            self.kodi.LOGINFO)
        threading.Thread(target=self._restore, args=(context, event),
                         name="AcTweeteR-SlyGuyReturn", daemon=True).start()

    def _clear_markers(self, context, identity_verified=False):
        current = self.kodi.getInfoLabel(
            "Window(Home).Property(SLYGUY_TRAILER_RETURN_ID)")
        pending = self.kodi.getInfoLabel(
            "Window(Home).Property(SLYGUY_TRAILER_RETURN_PENDING)")
        request = self.kodi.getInfoLabel(
            "Window(Home).Property(SLYGUY_TRAILER_RETURN_REQUEST)")
        if not marker_cleanup_allowed(
                current, context["identity"],
                identity_verified=identity_verified,
                pending=pending == "1", explicit_request=request == "1"):
            return
        self.kodi.executebuiltin(
            "ClearProperty(SLYGUY_TRAILER_RETURN_PENDING,Home)", False)
        self.kodi.executebuiltin(
            "ClearProperty(SLYGUY_TRAILER_RETURN_ID,Home)", False)
        self.kodi.executebuiltin(
            "ClearProperty(SLYGUY_TRAILER_RETURN_REQUEST,Home)", False)
        self.kodi.executebuiltin(
            "ClearProperty(SLYGUY_TRAILER_RETURN_PLAYBACK_STARTED,Home)", False)
        self.kodi.executebuiltin(
            "ClearProperty(SLYGUY_TRAILER_RETURN_ORIGIN,Home)", False)
        self.kodi.executebuiltin(
            "ClearProperty(SLYGUY_TRAILER_RETURN_WINDOW,Home)", False)
        self.kodi.executebuiltin(
            "ClearProperty(SLYGUY_TRAILER_RETURN_CONTROL,Home)", False)
        self.kodi.executebuiltin(
            "ClearProperty(SLYGUY_TRAILER_RETURN_TYPE,Home)", False)
        if context.get("origin") == "SPOTLIGHT":
            self.kodi.executebuiltin("ClearProperty(KeepPlayingPreview,Home)", False)

    def _request_is_current(self, context):
        return (
            self.kodi.getInfoLabel(
                "Window(Home).Property(SLYGUY_TRAILER_RETURN_PENDING)") == "1" and
            self.kodi.getInfoLabel(
                "Window(Home).Property(SLYGUY_TRAILER_RETURN_REQUEST)") == "1" and
            self.kodi.getInfoLabel(
                "Window(Home).Property(SLYGUY_TRAILER_RETURN_ID)") == context["identity"] and
            (self.kodi.getInfoLabel(
                "Window(Home).Property(SLYGUY_TRAILER_RETURN_ORIGIN)") or
             "VIDEO_INFO").upper() == context.get("origin", "VIDEO_INFO")
        )

    def _current_identity_values(self, context):
        control = context.get("source_control_id")
        if control and _window_id(self.kodi) == context.get("source_window_id"):
            prefix = "Container(%d).ListItem." % control
            return {kind: self.kodi.getInfoLabel(prefix + label)
                    for kind, label in (("imdb", "UniqueID(imdb)"),
                                        ("tmdb", "UniqueID(tmdb)"),
                                        ("dbid", "DBID"))}
        return _trailer_identity_values(
            self.kodi, spotlight=context.get("origin") == "SPOTLIGHT")

    def _restore(self, context, event):
        try:
            self._restore_context(context, event)
        except Exception as exc:
            self.kodi.log(
                "[AcTweeteR] SLYGUY_RETURN_RESULT=ERROR error_type=%s correlation=%s" %
                (type(exc).__name__, context.get("correlation_id", "none")),
                self.kodi.LOGERROR)
            try:
                self._clear_markers(context)
            except Exception:
                pass
            with self.lock:
                self.context = None

    def _restore_context(self, context, event):
        deadline = time.monotonic() + 8.0
        while not self.monitor.abortRequested() and time.monotonic() < deadline:
            if not self._request_is_current(context):
                self.kodi.log(
                    "[AcTweeteR] SLYGUY_RETURN_RESULT=REQUEST_NO_LONGER_CURRENT correlation=%s" %
                    context.get("correlation_id", "none"),
                    self.kodi.LOGINFO)
                with self.lock:
                    self.context = None
                return
            active = bool(self.kodi.getCondVisibility("Player.HasVideo"))
            window_id = _window_id(self.kodi)
            decision = return_decision(
                context, event=event, player_active=active,
                window_id=window_id,
                current_values=self._current_identity_values(context),
                control_focused=(
                    self.kodi.getCondVisibility("Control.HasFocus(1508)")
                    if context.get("origin") == "SPOTLIGHT" else False),
            )
            if decision == "preserve":
                self._clear_markers(context)
                with self.lock:
                    self.context = None
                self.kodi.log(
                    "[AcTweeteR] SLYGUY_RETURN_RESULT=DETAIL_PRESERVED correlation=%s" %
                    context.get("correlation_id", "none"), self.kodi.LOGINFO)
                return
            if decision == "focus_spotlight":
                # This guarded focus repair is limited to Home and only occurs
                # after the selected spotlight movie identity has matched.
                self.kodi.executebuiltin("SetFocus(1508)", False)
                deadline = time.monotonic() + 3.0
                while (not self.monitor.abortRequested() and
                       time.monotonic() < deadline):
                    if (self._request_is_current(context) and
                            _window_id(self.kodi) == 10000 and
                            self.kodi.getCondVisibility("Control.HasFocus(1508)") and
                            identity_matches(
                                context["identity"],
                                self._current_identity_values(context))):
                        self._clear_markers(context)
                        with self.lock:
                            self.context = None
                        self.kodi.log(
                            "[AcTweeteR] SLYGUY_RETURN_RESULT=SPOTLIGHT_RESTORED correlation=%s" %
                            context.get("correlation_id", "none"), self.kodi.LOGINFO)
                        return
                    time.sleep(0.1)
                break
            if decision == "restore":
                # Action(Info) is issued only after Kodi reports the Movies Hub
                # and the selected item's stable identity matches the capture.
                source_control = context.get("source_control_id")
                if not source_control:
                    # Detail dialogs normally hide their originating list
                    # control at AV start. Recover only the *currently focused*
                    # list control, and only when its own container item has
                    # the exact captured identity; never guess a control ID.
                    try:
                        candidate = xbmcgui.Window(window_id).getFocusId()
                        values = {kind: self.kodi.getInfoLabel(
                            "Container(%d).ListItem.%s" % (candidate, label))
                            for kind, label in (("imdb", "UniqueID(imdb)"),
                                                ("tmdb", "UniqueID(tmdb)"),
                                                ("dbid", "DBID"))}
                        if (window_id in (10000, 11110, 11111, 10025) and
                                candidate > 0 and
                                self.kodi.getCondVisibility(
                                    "Control.HasFocus(%d)" % candidate) and
                                identity_matches(context["identity"], values)):
                            source_control = candidate
                            context["source_window_id"] = window_id
                            context["source_control_id"] = candidate
                    except (RuntimeError, SystemError, ValueError, TypeError):
                        pass
                if not source_control or context.get("source_window_id") != window_id:
                    self.kodi.log(
                        "[AcTweeteR] SLYGUY_RETURN_RESULT=SOURCE_CONTROL_UNKNOWN correlation=%s" %
                        context.get("correlation_id", "none"), self.kodi.LOGWARNING)
                    break
                if source_control:
                    self.kodi.executebuiltin("SetFocus(%d)" % source_control, False)
                    # Kodi processes SetFocus asynchronously. Do not issue
                    # Action(Info) against a different selected control.
                    focus_deadline = min(deadline, time.monotonic() + 1.0)
                    while (not self.monitor.abortRequested() and
                           time.monotonic() < focus_deadline):
                        if (_window_id(self.kodi) == window_id and
                                self.kodi.getCondVisibility(
                                    "Control.HasFocus(%d)" % source_control) and
                                identity_matches(
                                    context["identity"],
                                    self._current_identity_values(context))):
                            break
                        time.sleep(0.05)
                    else:
                        self.kodi.log(
                            "[AcTweeteR] SLYGUY_RETURN_RESULT=FOCUS_NOT_CONFIRMED correlation=%s" %
                            context.get("correlation_id", "none"), self.kodi.LOGWARNING)
                        break
                if (not self._request_is_current(context) or
                        _window_id(self.kodi) != window_id or
                        not self.kodi.getCondVisibility(
                            "Control.HasFocus(%d)" % source_control) or
                        not identity_matches(context["identity"],
                                             self._current_identity_values(context))):
                    self.kodi.log(
                        "[AcTweeteR] SLYGUY_RETURN_RESULT=FOCUS_CHANGED_BEFORE_INFO correlation=%s" %
                        context.get("correlation_id", "none"), self.kodi.LOGWARNING)
                    break
                self.kodi.executebuiltin("Action(Info)", False)
                self.kodi.log(
                    "[AcTweeteR] SLYGUY_RETURN_INFO_ACTION=1 correlation=%s" %
                    context.get("correlation_id", "none"), self.kodi.LOGINFO)
                deadline = time.monotonic() + 8.0
                while (not self.monitor.abortRequested() and
                       time.monotonic() < deadline):
                    if (self._request_is_current(context) and
                            _window_id(self.kodi) == 12003 and
                            identity_matches(
                                context["identity"],
                                self._current_identity_values(context))):
                        self._clear_markers(context, identity_verified=True)
                        with self.lock:
                            self.context = None
                        self.kodi.log(
                            "[AcTweeteR] SLYGUY_RETURN_RESULT=DETAIL_RESTORED correlation=%s" %
                            context.get("correlation_id", "none"), self.kodi.LOGINFO)
                        return
                    time.sleep(0.1)
                break
            if decision == "abandon":
                self.kodi.log(
                    "[AcTweeteR] SLYGUY_RETURN_RESULT=IDENTITY_MISMATCH correlation=%s" %
                    context.get("correlation_id", "none"),
                    self.kodi.LOGWARNING)
                self._clear_markers(context)
                with self.lock:
                    self.context = None
                return
            time.sleep(0.1)

        self.kodi.log(
            "[AcTweeteR] SLYGUY_RETURN_RESULT=STATE_NOT_CONFIRMED correlation=%s" %
            context.get("correlation_id", "none"), self.kodi.LOGWARNING)
        self._clear_markers(context)
        with self.lock:
            self.context = None


def _run_coordinator(kodi, addon_factory, vfs, clock=time.time, monitor=None,
                     performance=None):
    """Run one Kodi-owned coordinator loop; all provider I/O stays in XStream."""
    monitor = monitor or kodi.Monitor()
    refresh_gate = RefreshGate()
    spotlight_rotation = SpotlightRotation()
    service_started_at = clock()
    last_missing_addon_log = 0.0
    pending_refresh = None
    next_refresh_check = service_started_at
    cached_profile_path = ""
    cached_profile_number = 1
    service_profile = vfs.translatePath(ADDON.getAddonInfo("profile"))
    recovered = recover_search_operations(service_profile, now=service_started_at)
    if recovered:
        kodi.log("[AcTweeteR] SEARCH_REFRESH_RECOVERY status=interrupted count=%d" % recovered,
                 kodi.LOGWARNING)
    trakt_scheduler = TraktSyncScheduler(
        os.path.join(service_profile, "trakt_live", "scheduler.json"))
    while not monitor.abortRequested():
        now = clock()
        spotlight_rotation.tick(kodi, now, active_window=_window_id(kodi))
        # The XStream plugin owns OAuth and network access. This loop only
        # schedules an opt-in cycle and never reads or stores Trakt tokens.
        try:
            consent_path = os.path.join(service_profile, "trakt_live", "consent.json")
            player = getattr(kodi, "Player", lambda: None)()
            playing = bool(player and player.isPlaying())
            if trakt_sync_enabled(consent_path):
                trakt_scheduler.dispatch_if_due(
                    lambda: kodi.executebuiltin(
                        "RunPlugin(plugin://plugin.video.xstream-pro/?mode=xstream_trakt_sync_cycle)",
                        False),
                    authorized=True, playing=playing)
        except Exception as exc:
            if now - last_missing_addon_log >= 3600:
                kodi.log("[AcTweeteR] TRAKT_SYNC_SCHEDULER unavailable error_type=%s" %
                         type(exc).__name__, kodi.LOGINFO)
                last_missing_addon_log = now
        has_pending_refresh = pending_refresh is not None
        if not refresh_state_check_due(now, next_refresh_check,
                                       pending=has_pending_refresh):
            if performance is not None:
                performance.count("coordinator.refresh_cache_hit")
            if monitor.waitForAbort(60):
                break
            continue
        phase = "pending_status"
        try:
            if has_pending_refresh:
                operation = search_operation(
                    service_profile, pending_refresh["trace"]["correlation_id"])
                terminal = operation.get("status")
                if terminal in ("COMPLETED", "ERROR", "TIMEOUT", "CANCELLED", "INTERRUPTED"):
                    trace_state = {"COMPLETED": "finished", "ERROR": "error",
                                   "TIMEOUT": "timeout", "CANCELLED": "cancelled",
                                   "INTERRUPTED": "interrupted"}[terminal]
                    emit_plugin_trace(
                        pending_refresh["trace"], trace_state,
                        error_type="XStreamRefreshError" if terminal != "COMPLETED" else "",
                        log=lambda message: kodi.log(
                            message, kodi.LOGINFO if terminal == "COMPLETED" else kodi.LOGWARNING))
                    pending_refresh = None
                    next_refresh_check = now + COORDINATOR_REFRESH_CHECK_SECONDS
                elif now - pending_refresh["requested_at"] >= SEARCH_REFRESH_TIMEOUT_SECONDS:
                    finish_search_operation(
                        service_profile, pending_refresh["trace"]["correlation_id"],
                        "timeout", now=now)
                    record_retry_result(
                        service_profile, cached_profile_number, "error",
                        category="timeout", now=now, jitter=0)
                    emit_plugin_trace(
                        pending_refresh["trace"], "timeout", error_type="TimeoutError",
                        log=lambda message: kodi.log(message, kodi.LOGWARNING))
                    pending_refresh = None
                    next_refresh_check = now + COORDINATOR_REFRESH_CHECK_SECONDS
                else:
                    next_refresh_check = now + COORDINATOR_PENDING_CHECK_SECONDS
                    if monitor.waitForAbort(COORDINATOR_PENDING_CHECK_SECONDS):
                        break
                    continue
            if not pending_refresh:
                phase = "read_refresh_state"
                with (performance.measure("coordinator.refresh_state_read")
                      if performance is not None else _null_measure()):
                    xstream = addon_factory("plugin.video.xstream-pro")
                    xstream_profile = vfs.translatePath(xstream.getAddonInfo("profile"))
                    profile_number = xstream_profile_number(
                        xstream.getSetting("active_pvr_profile"))
                    last_sync = last_successful_sync(xstream_profile, profile_number)
                cached_profile_path = xstream_profile
                cached_profile_number = profile_number
                refresh_gate.interval = refresh_interval(xstream_profile, profile_number)
                if performance is not None:
                    performance.count("coordinator.refresh_state_check")
            # XStream builds a new profile's initial index during its own
            # startup. Give that bootstrap time to finish before this hourly
            # coordinator can request a stale/missing-index refresh.
            if last_sync <= 0 and now - service_started_at < 120:
                next_refresh_check = now + COORDINATOR_PENDING_CHECK_SECONDS
                if monitor.waitForAbort(60):
                    break
                continue
            phase = "read_retry_state"
            retry = read_retry_state(service_profile, profile_number)
            retry_waiting = (retry["automatic_blocked"] or retry["retry_at"] > now)
            if (not retry_waiting
                    and refresh_gate.should_request(last_sync, now,
                                                    abort=monitor.abortRequested())):
                # RunPlugin executes in Kodi's plugin runtime; this service only
                # schedules it and never reads provider settings or credentials.
                if pending_refresh:
                    emit_plugin_trace(
                        pending_refresh["trace"], "unobserved",
                        log=lambda message: kodi.log(message, kodi.LOGWARNING))
                    pending_refresh = None
                trace = begin_plugin_trace(
                    plugin_refresh_url(profile_number), "service.search_refresh",
                    log=lambda message: kodi.log(message, kodi.LOGINFO))
                url = plugin_refresh_url(profile_number, trace["correlation_id"])
                phase = "persist_refresh_operation"
                begin_search_operation(service_profile, trace["correlation_id"],
                                       profile_number, now=now)
                try:
                    phase = "dispatch_refresh"
                    kodi.executebuiltin("RunPlugin(%s)" % url, False)
                except Exception as exc:
                    finish_search_operation(
                        service_profile, trace["correlation_id"], "error", now=now)
                    emit_plugin_trace(
                        trace, "error", error_type=type(exc).__name__,
                        log=lambda message: kodi.log(
                            message, getattr(kodi, "LOGWARNING", kodi.LOGINFO)))
                    raise
                emit_plugin_trace(trace, "dispatched",
                                  log=lambda message: kodi.log(message, kodi.LOGINFO))
                pending_refresh = {"trace": trace, "requested_at": now}
                if performance is not None:
                    performance.count("coordinator.refresh_dispatch")
                refresh_gate.mark_requested(now)
            next_refresh_check = now + (
                COORDINATOR_PENDING_CHECK_SECONDS if pending_refresh else
                COORDINATOR_REFRESH_CHECK_SECONDS)
        except Exception as exc:
            # Add-on may be absent on a clean install before private provisioning.
            if now - last_missing_addon_log >= 3600:
                kodi.log("[AcTweeteR] Search refresh unavailable phase=%s error_type=%s" %
                         (phase, type(exc).__name__), kodi.LOGINFO)
                last_missing_addon_log = now
            next_refresh_check = now + COORDINATOR_REFRESH_CHECK_SECONDS
        if monitor.waitForAbort(60):
            break
    if pending_refresh:
        emit_plugin_trace(
            pending_refresh["trace"], "cancel_requested",
            log=lambda message: kodi.log(
                message, getattr(kodi, "LOGWARNING", kodi.LOGINFO)))


def _profile_kind(kodi):
    """Return a non-identifying profile class for lifecycle diagnostics."""
    try:
        response = json.loads(kodi.executeJSONRPC(json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "Profiles.GetCurrentProfile",
            "params": {},
        })))
        label = str(response.get("result", {}).get("label", "")).casefold()
        if label == "consumer":
            return "consumer"
        if label:
            return "master"
    except Exception:
        pass
    return "unknown"


def _dispatch_auto_preview(kodi, request):
    """Signal the SlyGuy-owned worker without running provider I/O on Kodi UI."""
    encoded = base64.b64encode(json.dumps(
        request, separators=(",", ":")
    ).encode("utf-8")).decode("ascii")
    response = json.loads(kodi.executeJSONRPC(json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "JSONRPC.NotifyAll",
        "params": {"sender": "service.actweeter.SIGNAL",
                   "message": "actweeter_auto_preview", "data": [encoded]},
    }, separators=(",", ":"))))
    if "error" in response:
        raise RuntimeError("Kodi notification transport rejected preview")


class _null_measure:
    """No-op context manager used when optional performance metrics are off."""
    def __enter__(self):
        return None

    def __exit__(self, *_exc):
        return False


def run_service(kodi, addon_factory, vfs, clock=time.time):
    """Log one opaque lifecycle identity around the sole coordinator loop."""
    instance_id = uuid.uuid4().hex
    profile = _profile_kind(kodi)
    kodi.log("[AcTweeteR] SERVICE_INSTANCE_START profile=%s instance=%s" %
             (profile, instance_id), kodi.LOGINFO)
    kodi.log("[AcTweeteR] COORDINATOR_START profile=%s instance=%s" %
             (profile, instance_id), kodi.LOGINFO)
    player_factory = getattr(kodi, "Player", None)
    preview_player = player_factory() if player_factory else _InactivePlayer()
    auto_preview = KodiAutoPreviewCoordinator(
        kodi, preview_player,
        lambda request, item_data=None: _dispatch_auto_preview(kodi, request),
        vfs=vfs)
    kodi.log("[AcTweeteR] AUTO_PREVIEW_COORDINATOR status=started",
             kodi.LOGINFO)
    try:
        metrics_enabled = str(ADDON.getSetting("performance_metrics_enabled")).casefold() == "true"
    except Exception:
        metrics_enabled = False
    performance = PerformanceRecorder(
        metrics_enabled,
        log=lambda message: kodi.log(message, getattr(kodi, "LOGINFO", 1)))
    return_monitor = AcTweeteRMonitor(auto_preview)
    trailer_return_player = SlyGuyTrailerReturnPlayer(kodi, return_monitor,
                                                      auto_preview=auto_preview)
    try:
        try:
            from addon_update_policy import review as review_updates
            review_updates(kodi, ADDON, vfs, xbmcgui.Dialog())
        except Exception as exc:
            kodi.log("[AcTweeteR] UPDATE_POLICY review_error=" + type(exc).__name__, kodi.LOGWARNING)
        return _run_coordinator(kodi, addon_factory, vfs, clock=clock,
                                monitor=return_monitor, performance=performance)
    finally:
        performance.emit_summary()
        auto_preview.close()
        kodi.log("[AcTweeteR] AUTO_PREVIEW_COORDINATOR status=stopped",
                 kodi.LOGINFO)
        kodi.log("[AcTweeteR] COORDINATOR_STOP profile=%s instance=%s" %
                 (profile, instance_id), kodi.LOGINFO)
        kodi.log("[AcTweeteR] SERVICE_INSTANCE_STOP profile=%s instance=%s" %
                 (profile, instance_id), kodi.LOGINFO)


run_service(xbmc, xbmcaddon.Addon, xbmcvfs)
