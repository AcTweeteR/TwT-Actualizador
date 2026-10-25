"""Kodi event and single-worker bridge for SlyGuy automatic movie previews."""

from __future__ import annotations

import base64
import binascii
import json
import math
import re
import threading
import time
import uuid

from automatic_preview import LatestPreviewScheduler


SENDER = "service.actweeter.SIGNAL"
PROVIDER_SENDER = "slyguy.trailers.SIGNAL"
MESSAGE = "actweeter_auto_preview"
_ANNOUNCEMENT_METHOD = "Other." + MESSAGE


def stable_identity(payload):
    for name in ("imdb", "tmdb", "dbid"):
        raw = payload.get(name)
        value = raw.strip() if isinstance(raw, str) else ""
        if value and value.isascii() and value.isalnum():
            return name + ":" + value
    return ""


def read_preview_metadata(kodi, prefix):
    data = {field: kodi.getInfoLabel(prefix + label) for field, label in (
        ("media_type", "DBType"), ("imdb", "UniqueID(imdb)"),
        ("tmdb", "UniqueID(tmdb)"), ("dbid", "DBID"),
        ("title", "Title"), ("year", "Year"), ("show_title", "TVShowTitle"),
        ("show_dbid", "TvShowDBID"))}
    data["media_type"] = data["media_type"].lower()
    # XStream premium resume cards inherit these properties from the series
    # before changing their media type to episode; UniqueIDs alone are ambiguous.
    if (data["media_type"] in ("season", "episode") and
            kodi.getInfoLabel(prefix + "Property(XStream.ProviderOnly)") == "true"):
        data["show_tmdb"] = kodi.getInfoLabel(prefix + "Property(tmdb_id)")
        data["show_imdb"] = kodi.getInfoLabel(prefix + "Property(imdb_id)")
        data["show_year"] = data["year"]
    return data


class KodiAutoPreviewCoordinator:
    """Latest-wins scheduler. Provider resolution always runs off the UI thread."""

    def __init__(self, kodi, player, run_script, *, vfs=None, clock=time.monotonic,
                 delay_parser=None):
        self.kodi = kodi
        self.player = player
        self.run_script = run_script
        self.vfs = vfs
        self.clock = clock
        self.delay_parser = delay_parser or (lambda value: float(value))
        self.session_id = uuid.uuid4().hex
        self.scheduler = LatestPreviewScheduler()
        self.requests = {}
        self.item_data = {}
        self.request_ids = {}
        # A provider may return from Player.play() before Kodi emits AVStarted.
        # Keep that handoff distinct from a confirmed player owner so a later
        # error/terminal callback can release only the exact unstarted slot.
        self.launch_pending = {}
        self.stale_owned = set()
        self.stop_lock = threading.Lock()
        self.stop_inflight = set()
        self.stop_timeline = {}
        self.last_terminal_at = None
        self.refocus_after_stop = None
        self.focus_context = None
        self.closed = False
        self.wake = self.scheduler.condition
        self.worker = threading.Thread(target=self._work,
                                       name="AcTweeteR-AutoPreview", daemon=True)
        self.worker.start()

    def _log(self, event, **fields):
        details = " ".join("%s=%s" % (key, value) for key, value in fields.items())
        suffix = (" " + details) if details else ""
        self.kodi.log("[AcTweeteR] AUTO_PREVIEW_%s%s" % (event, suffix),
                      getattr(self.kodi, "LOGINFO", 1))

    def _publish(self, key, value):
        self.kodi.executebuiltin("SetProperty(%s,%s,Home)" % (key, value), False)

    def _set_request_properties(self, request):
        request_id = self.request_ids[request.generation]
        self._publish("ACTWEETER_AUTO_PREVIEW_REQUEST", request_id)

    def _clear_current(self):
        self.kodi.executebuiltin("ClearProperty(ACTWEETER_AUTO_PREVIEW_REQUEST,Home)", False)
        self.kodi.executebuiltin("ClearProperty(ACTWEETER_AUTO_PREVIEW_OWNER,Home)", False)

    def _clear_generation(self, generation):
        if self.kodi.getInfoLabel(
                "Window(Home).Property(ACTWEETER_AUTO_PREVIEW_REQUEST)") == self.request_ids.get(generation):
            self._clear_current()

    @staticmethod
    def _decode_notification(data):
        """Decode Kodi JSONRPC.NotifyAll's AddonSignals-compatible payload."""
        try:
            envelope = json.loads(data) if isinstance(data, str) else data
            encoded = envelope[0] if isinstance(envelope, list) and envelope else None
            if not isinstance(encoded, str):
                return None
            decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
            payload = json.loads(decoded)
            return payload if isinstance(payload, dict) else None
        except (TypeError, ValueError, UnicodeError, binascii.Error):
            return None

    def _owned_item(self):
        try:
            item = self.player.getPlayingItem()
            generation = item.getProperty("AcTweeteR.PreviewGeneration")
            identity = item.getProperty("AcTweeteR.PreviewIdentity")
            request_id = item.getProperty("AcTweeteR.PreviewRequestId")
            return generation, identity, request_id
        except Exception:
            return "", "", ""

    def _stop_owned(self, request, *, require_active=True):
        if request is None:
            self._log("STOP_SKIPPED", reason="no_request")
            return False
        if require_active and self.scheduler.active != request:
            self._log("STOP_SKIPPED", generation=request.generation,
                      reason="request_not_active")
            return False
        # Player API reads and stop can both block behind Kodi's playback lock.
        # Keep them off Kodi's Monitor/notification thread, then verify exact
        # item ownership in the worker before issuing the only permitted Stop.
        with self.stop_lock:
            if request.generation in self.stop_inflight:
                self._log("STOP_ALREADY_SCHEDULED", generation=request.generation)
                return True
            self.stop_inflight.add(request.generation)
            self.stop_timeline[request.generation] = {
                "requested_at": self.clock(),
            }
            inflight = len(self.stop_inflight)
        self._log("STOP_REQUESTED", generation=request.generation,
                  workers_inflight=inflight)
        try:
            worker = threading.Thread(
                target=self._stop_owned_worker, args=(request, require_active),
                name="AcTweeteR-PreviewStop-%d" % request.generation,
                daemon=True)
            worker.start()
        except Exception as exc:
            with self.stop_lock:
                self.stop_inflight.discard(request.generation)
                self.stop_timeline.pop(request.generation, None)
            self._log("STOP_SCHEDULE_FAILED", generation=request.generation,
                      error=type(exc).__name__)
            with self.wake:
                self.wake.notify_all()
            return False
        self._log("STOP_SCHEDULED", generation=request.generation,
                  reason="ownership_verified")
        return True

    def _stop_owned_worker(self, request, require_active=True):
        command_accepted = False
        try:
            worker_started = self.clock()
            with self.stop_lock:
                timeline = self.stop_timeline.get(request.generation, {})
                requested_at = timeline.get("requested_at", worker_started)
                timeline["worker_started_at"] = worker_started
            self._log("STOP_WORKER_STARTED", generation=request.generation,
                      queue_delay_ms=int(max(0, worker_started - requested_at) * 1000))
            if require_active and self.scheduler.active != request:
                self._log("STOP_SKIPPED", generation=request.generation,
                          reason="request_not_active_in_worker")
                return
            ownership_read_started = self.clock()
            generation, identity, request_id = self._owned_item()
            ownership_read_ms = int(max(0, self.clock() - ownership_read_started) * 1000)
            if (generation != str(request.generation) or
                    identity != request.identity or
                    request_id != self.request_ids.get(request.generation)):
                self._log("STOP_SKIPPED", generation=request.generation,
                          reason="playing_item_ownership_mismatch")
                return
            # Re-read tags immediately before stop to reject a manual/VOD
            # handoff that raced the first worker-side ownership check.
            generation, identity, request_id = self._owned_item()
            if (generation != str(request.generation) or
                    identity != request.identity or
                    request_id != self.request_ids.get(request.generation)):
                self._log("STOP_SKIPPED", generation=request.generation,
                          reason="ownership_changed_before_stop")
                return
            stop_entered = self.clock()
            with self.stop_lock:
                timeline["stop_entered_at"] = stop_entered
            self._log("PLAYER_STOP_ENTER", generation=request.generation,
                      ownership_read_ms=ownership_read_ms,
                      method="JSONRPC.Player.Stop")
            response = self.kodi.executeJSONRPC(json.dumps({
                "jsonrpc": "2.0", "id": 1, "method": "Player.Stop",
                "params": {"playerid": 1},
            }, separators=(",", ":")))
            decoded = json.loads(response) if isinstance(response, str) else response
            if (not isinstance(decoded, dict) or "error" in decoded or
                    decoded.get("result") not in ("OK", True)):
                raise RuntimeError("Kodi did not accept the owned preview Stop")
            command_accepted = True
            stop_returned = self.clock()
            with self.stop_lock:
                timeline["stop_returned_at"] = stop_returned
            self._log("STOP_CALL_RETURNED", generation=request.generation,
                      reason="ownership_verified", method="JSONRPC.Player.Stop",
                      call_duration_ms=int(max(0, stop_returned - stop_entered) * 1000))
        except Exception as exc:
            self._log("STOP_FAILED", generation=request.generation,
                      error=type(exc).__name__)
        finally:
            with self.stop_lock:
                timeline = self.stop_timeline.get(request.generation)
                if timeline is not None:
                    timeline["worker_finished_at"] = self.clock()
                    released = "ownership_released_at" in timeline
                    if not command_accepted or released:
                        self.stop_inflight.discard(request.generation)
                    if (not command_accepted or
                            ("terminal_callback_at" in timeline and released)):
                        self.stop_timeline.pop(request.generation, None)
                elif not command_accepted:
                    self.stop_inflight.discard(request.generation)
                while len(self.stop_timeline) > 8:
                    oldest = next(iter(self.stop_timeline))
                    if oldest in self.stop_inflight:
                        break
                    self.stop_timeline.pop(oldest, None)
            with self.wake:
                self.wake.notify_all()

    def player_terminal_event(self, event):
        """Timestamp Kodi's playback callback without querying Player from it."""
        now = self.clock()
        with self.stop_lock:
            candidates = [state for state in self.stop_timeline.values()
                          if "terminal_callback_at" not in state]
            state = min(candidates, key=lambda value: value["requested_at"]) if candidates else None
            if state is not None:
                state["terminal_callback_at"] = now
                delay = int(max(0, now - state["requested_at"]) * 1000)
            else:
                delay = None
            self.last_terminal_at = now
        self._log("PLAYER_TERMINAL_CALLBACK", playback_event=event,
                  since_stop_request_ms=delay if delay is not None else "none")

    def on_notification(self, sender, method, data):
        if self.closed:
            return False
        # Kodi Monitor reports JSONRPC.NotifyAll announcements with the
        # announcement category prefixed to the message. Keep accepting the
        # bare form too for transports/test doubles that expose the schema
        # message unchanged, but reject every other category or method.
        if method == _ANNOUNCEMENT_METHOD:
            method = MESSAGE
        if sender not in (SENDER, PROVIDER_SENDER) or method != MESSAGE:
            if (sender in (SENDER, PROVIDER_SENDER) or method == MESSAGE):
                self._log("NOTIFICATION_REJECT", sender=sender, method=method)
            return False
        payload = self._decode_notification(data)
        if payload is None:
            try:
                parsed = json.loads(data) if isinstance(data, str) else data
                shape = ("list:%d" % len(parsed) if isinstance(parsed, list) else
                         "dict" if isinstance(parsed, dict) else type(parsed).__name__)
            except (TypeError, ValueError):
                shape = "invalid_json"
            self._log("NOTIFICATION_DECODE_REJECT", sender=sender, method=method,
                      data_type=type(data).__name__, data_shape=shape)
            return False
        action = payload.get("action")
        if sender == PROVIDER_SENDER:
            return self._resolved(payload)
        if action == "focus":
            return self._focus(payload)
        if action == "cancel":
            return self._cancel(payload)
        if action == "exit":
            return self._exit_home()
        if action == "preempt":
            return self._preempt(payload)
        return False

    def _focus(self, payload):
        identity = stable_identity(payload)
        try:
            window = int(payload["window"])
            container = int(payload["container"])
            focus = int(payload["focus"])
            position = int(payload["position"])
            delay = self.delay_parser(payload.get("delay", 3))
            if not math.isfinite(delay):
                raise ValueError("non-finite preview delay")
        except (KeyError, TypeError, ValueError):
            # A partially delivered/foreign notification must not raise from
            # Kodi Monitor; reject it before changing player ownership.
            self._log("FOCUS_REJECT", reason="invalid_payload")
            return False
        if window not in (10000, 11110, 11111) or container != focus or container <= 0:
            self._log("FOCUS_REJECT", reason="container_focus_mismatch")
            return False
        if payload.get("media_type") not in ("movie", "tvshow", "season", "episode"):
            self.focus_context = None
            self._log("FOCUS_REJECT", reason="context", window=window,
                      media=payload.get("media_type", "unknown"))
            self._preempt({"owner": "OTHER"})
            return False
        if not identity or position < 0 or focus in (40000, 40003):
            # A delayed focus callback may describe an empty placeholder.
            # Preserve the last valid row until the observer verifies focus.
            self._log("FOCUS_REJECT", reason="identity_or_target")
            return False
        # Store only validated rows; invalid placeholders must not be
        # rediscovered by the idle-selection observer.
        self.focus_context = dict(payload)

        try:
            player_has_media = bool(self.kodi.getCondVisibility("Player.HasMedia"))
        except Exception:
            # Fail closed: if Kodi cannot establish that playback is idle,
            # retain the current ownership rather than competing with it.
            player_has_media = True
        if self.scheduler.ownership.recover_idle_other_owner(player_has_media):
            self._log("FOCUS_OWNER_RECOVERED", reason="home_focus_no_media")

        previous = self.scheduler.active
        request = self.scheduler.ownership.latest_candidate(
            identity, window, container, focus, position)
        if request is None:
            self._log("FOCUS_REJECT", reason="ownership")
            return False
        with self.wake:
            keep = {item.generation for item in
                    (self.scheduler.resolving, self.scheduler.active) if item}
            # A displaced player can report its terminal event after new focus.
            with self.stop_lock:
                keep.update(self.stop_inflight)
            self.requests = {key: value for key, value in self.requests.items()
                             if key in keep}
            self.request_ids = {key: value for key, value in self.request_ids.items()
                                if key in keep}
            self.item_data = {key: value for key, value in self.item_data.items()
                              if key in keep}
            self.requests[request.generation] = request
            self.request_ids[request.generation] = "%s-%d" % (
                self.session_id, request.generation)
            self.item_data[request.generation] = {
                key: payload.get(key, "")
                for key in ("title", "year", "dbid", "imdb", "tmdb", "trailer_id",
                            "media_type", "show_title", "show_dbid", "show_tmdb",
                            "show_imdb", "show_year")
            }
            self._set_request_properties(request)
            self.scheduler.offer(request, delay, self.clock())
        self._log("REQUEST_ACCEPTED", generation=request.generation, window=window,
                  container=container, focus=focus, delay="%.2f" % delay)
        if previous and previous != request:
            self._stop_owned(previous)
        return True

    def _cancel(self, payload):
        identity = stable_identity(payload)
        pending = self.scheduler.latest or self.scheduler.resolving
        request = pending or self.scheduler.active
        if request == self.scheduler.active and self._owned_fullscreen(request):
            return False
        if request is None:
            # An on-unfocus can arrive after a trailer has already ended.
            # Forget the row even without a pending request; otherwise the
            # idle observer may restart its preview after the user leaves.
            context = self.focus_context
            if (context and
                    str(payload.get("container", "")) == str(context.get("container")) and
                    str(payload.get("window", "")) == str(context.get("window"))):
                self.focus_context = None
            self._log("CANCEL_NO_REQUEST")
            return True
        try:
            if int(payload.get("container", request.container)) != request.container:
                return False
        except (TypeError, ValueError):
            return False
        try:
            window = int(payload.get("window", request.window))
            if window != request.window:
                self._log("CANCEL_IGNORED", generation=request.generation,
                          reason="other_window")
                return False
            focus = int(payload.get("focus", request.focus))
            position = int(payload.get("position", request.position))
        except (TypeError, ValueError):
            return False
        self._log("CANCEL_EVALUATED", generation=request.generation,
                  pending=pending is not None, window=window, focus=focus,
                  position=position, identity_matches=identity == request.identity)
        # Kodi may invoke on-unfocus before updating System.CurrentControlId
        # and Container.Position. When there is no replacement request, the
        # explicit callback itself is authoritative: cancel the active preview
        # even if the queried focus still describes the item being left.
        # If a replacement is already pending, preserve it on stale callbacks.
        if pending is not None and window == request.window and (
                focus == request.focus and position == request.position and
                (not identity or identity == request.identity)):
            self._log("CANCEL_IGNORED", generation=request.generation,
                      reason="replacement_request_still_current")
            return False
        if pending is not None and window == request.window and identity and identity != request.identity:
            self._log("CANCEL_IGNORED", generation=request.generation,
                      reason="replacement_identity_mismatch")
            return False
        with self.wake:
            if (self.focus_context and
                    str(self.focus_context.get("window")) == str(request.window) and
                    str(self.focus_context.get("container")) == str(request.container)):
                self.focus_context = None
            # When focus moved to a non-preview item there is no replacement
            # request to protect; cancel the exact active preview instead of
            # rejecting the transition because the newly focused item differs.
            self.scheduler.cancel(request.identity)
            self._clear_current()
        self._stop_owned(request)
        self._log("REQUEST_CANCELLED", generation=request.generation)
        return True

    def _preempt(self, payload):
        owner = str(payload.get("owner", "OTHER")).upper()
        if owner not in ("MANUAL_DETAIL", "MANUAL_SPOTLIGHT", "VOD", "OTHER"):
            return False
        with self.wake:
            # A manual/VOD handoff invalidates the selected automatic row.
            # Otherwise the idle observer may restart its trailer when that
            # external playback ends, without a new focus event.
            self.focus_context = None
            self.refocus_after_stop = None
            request = self.scheduler.active
            self.scheduler.preempt(owner)
            self._clear_current()
            self.wake.notify_all()
        # Never call Kodi's Player API while holding the scheduler condition:
        # Kodi may deliver the terminal callback on another thread.
        self._stop_owned(request, require_active=False)
        return True

    def _owned_fullscreen(self, request):
        if request is None or not self.kodi.getCondVisibility(
                "Window.IsActive(fullscreenvideo) | Window.Next(fullscreenvideo)"):
            return False
        return self._owned_item() == (
            str(request.generation), request.identity,
            self.request_ids.get(request.generation))

    def _exit_home(self):
        """Invalidate Home preview work without claiming an external player.

        Home's on-unload can run when no media is playing. Marking that case as
        OTHER leaves the in-memory owner stuck forever because Kodi emits no
        player terminal callback. Keep the active request only long enough for
        its ownership-tagged Stop/terminal cleanup; pending and resolving work
        is invalidated by generation and cannot replace later playback.
        """
        if self._owned_fullscreen(self.scheduler.active):
            self._log("HOME_EXIT", active="yes", owned_stop="no", fullscreen="yes")
            return True
        with self.wake:
            self.focus_context = None
            self.refocus_after_stop = None
            active = self.scheduler.active
            self.scheduler.cancel()
            self._clear_current()
            self.wake.notify_all()
        stopped = self._stop_owned(active) if active is not None else False
        self._log("HOME_EXIT", active="yes" if active else "no",
                  owned_stop="yes" if stopped else "no")
        return True

    def external_playback_started(self, owner="OTHER"):
        """Invalidate in-flight work, but never stop/replace this external player."""
        if owner not in ("MANUAL_DETAIL", "MANUAL_SPOTLIGHT", "VOD", "OTHER"):
            owner = "OTHER"
        with self.wake:
            # A manual/VOD handoff invalidates the selected automatic row.
            # Otherwise the idle observer may restart its trailer when that
            # external playback ends, without a new focus event.
            self.focus_context = None
            self.refocus_after_stop = None
            request = self.scheduler.active
            self.scheduler.preempt(owner)
            self._clear_current()
            self.wake.notify_all()
        self._stop_owned(request, require_active=False)

    def _resolved(self, payload):
        try:
            generation = int(payload.get("generation"))
        except (TypeError, ValueError):
            return False
        request = self.requests.get(generation)
        if (request is None or
                payload.get("request_id") != self.request_ids.get(generation)):
            return False
        status = payload.get("status")
        if status == "started":
            with self.wake:
                if self.scheduler.resolving == request:
                    self.launch_pending[generation] = request
            self._log("RESOLUTION_FINISHED", generation=generation, status="started")
            return True
        if status not in ("stale", "no_results", "error", "launch_error"):
            return False
        with self.wake:
            self.launch_pending.pop(generation, None)
            self.scheduler.resolution_finished(request, still_current=False)
            self.requests.pop(generation, None)
            self.item_data.pop(generation, None)
            self._clear_generation(generation)
            self.request_ids.pop(generation, None)
            self.wake.notify_all()
        self._log("RESOLUTION_FINISHED", generation=generation, status=status)
        return True

    def av_started(self, item):
        generation = item.getProperty("AcTweeteR.PreviewGeneration")
        identity = item.getProperty("AcTweeteR.PreviewIdentity")
        try:
            generation = int(generation)
        except (TypeError, ValueError):
            self.scheduler.ownership.external_playback()
            return "UNOWNED"
        request = self.requests.get(generation)
        request_id = item.getProperty("AcTweeteR.PreviewRequestId")
        if (request is None or
                self.request_ids.get(generation) != request_id):
            self.stale_owned.add((generation, request_id))
            return "UNOWNED"
        current = self.scheduler.latest or self.scheduler.resolving
        # Kodi can temporarily expose empty/non-numeric control labels while
        # changing windows. Treat that as stale focus, never raise from the
        # Player AVStarted callback or accidentally accept an old preview.
        try:
            current_focus = int(self.kodi.getInfoLabel("System.CurrentControlId") or "-1")
            current_position = int(self.kodi.getInfoLabel(
                "Container(%d).CurrentItem" % request.container) or "-1")
        except (TypeError, ValueError):
            current_focus = current_position = -1
        labels = "Container(%d).ListItem." % request.container
        actual_identity = stable_identity({
            "imdb": self.kodi.getInfoLabel(labels + "UniqueID(imdb)"),
            "tmdb": self.kodi.getInfoLabel(labels + "UniqueID(tmdb)"),
            "dbid": self.kodi.getInfoLabel(labels + "DBID"),
        })
        valid = (request == current and request.identity == identity and
                 self.request_ids.get(generation) == request_id and
                 self.kodi.getInfoLabel(
                     "Window(Home).Property(ACTWEETER_AUTO_PREVIEW_REQUEST)") == self.request_ids.get(generation) and
                 self.kodi.getCondVisibility("Window.IsActive(%d)" % request.window) and
                 current_focus == request.focus and current_position == request.position and
                 actual_identity == request.identity)
        if not valid:
            with self.wake:
                self.launch_pending.pop(generation, None)
                if self.scheduler.resolving == request:
                    self.scheduler.resolution_finished(request, still_current=False)
                self.stale_owned.add((generation, request_id))
                self.wake.notify_all()
            return "STALE_OWNED"
        with self.wake:
            if self.scheduler.resolving != request:
                return "STALE_OWNED"
            self.launch_pending.pop(generation, None)
            self.scheduler.resolution_finished(request, still_current=True)
            self.scheduler.ownership.av_started(
                request, generation, identity, request.window, request.container)
            self._publish("ACTWEETER_AUTO_PREVIEW_OWNER", "AUTO_PREVIEW")
            self.wake.notify_all()
        return "ACCEPTED"

    def terminal(self, item, event):
        generation = item.getProperty("AcTweeteR.PreviewGeneration")
        identity = item.getProperty("AcTweeteR.PreviewIdentity")
        request_id = item.getProperty("AcTweeteR.PreviewRequestId")
        try:
            generation = int(generation)
        except (TypeError, ValueError):
            return False
        request = self.requests.get(generation)
        if (generation, request_id) in self.stale_owned:
            self._cleanup_stale(generation, identity, request_id, item)
            return True
        if (request is None or request.identity != identity or
                request_id != self.request_ids.get(generation)):
            return False
        with self.wake:
            self.launch_pending.pop(generation, None)
            if self.scheduler.resolving == request:
                # A tagged Player error/stop before AVStarted owns only this
                # in-flight request; release the serial slot without fallback.
                self.scheduler.resolution_finished(request, still_current=False)
                self.requests.pop(generation, None)
                self.item_data.pop(generation, None)
                self._delete_manifest(item.getProperty("AcTweeteR.PreviewManifest"))
                self._clear_generation(generation)
                self.request_ids.pop(generation, None)
                self.wake.notify_all()
                return True
            accepted = self.scheduler.terminal(request)
            # Preemption may clear scheduler.active before Kodi delivers the
            # displaced preview's stop callback. Its exact ListItem token
            # still authorizes cleanup, never a mutation of the new owner.
            if accepted:
                self.scheduler.ownership.terminal(request, event)
                self.last_terminal_at = self.clock()
            self._record_ownership_release(generation, event)
            self.requests.pop(generation, None)
            self.item_data.pop(generation, None)
            self._delete_manifest(item.getProperty("AcTweeteR.PreviewManifest"))
            self._clear_generation(generation)
            self.request_ids.pop(generation, None)
            self.wake.notify_all()
            return True

    def terminal_unowned_launch(self, event):
        """Release a launched request when Kodi terminates it before AVStarted.

        The bridge's `started` result means Player.play() was requested, not
        that AVStarted was observed. A matching terminal callback can therefore
        release the still-resolving request without claiming or stopping an
        untagged player. This is deliberately event-driven (no timeout).
        """
        if event not in ("stopped", "ended", "error"):
            return False
        with self.wake:
            candidates = [request for generation, request in
                          self.launch_pending.items()
                          if self.scheduler.resolving == request]
            if len(candidates) != 1:
                return False
            request = candidates[0]
            generation = request.generation
            self.launch_pending.pop(generation, None)
            self.scheduler.resolution_finished(request, still_current=False)
            self.requests.pop(generation, None)
            self.item_data.pop(generation, None)
            self._clear_generation(generation)
            self.request_ids.pop(generation, None)
            self.wake.notify_all()
        self._log("UNOWNED_LAUNCH_TERMINAL_CLEANED", generation=generation,
                  playback_event=event)
        return True

    def _delete_manifest(self, manifest):
        # A prefix alone also matches path traversal and unrelated files.
        # Delete only the exact MPD naming scheme created by our bridge.
        if (not isinstance(manifest, str) or
                re.fullmatch(r"special://temp/actweeter_preview_[A-Za-z0-9_-]+\.mpd",
                             manifest) is None):
            return
        if self.vfs is None:
            return
        path = self.vfs.translatePath(manifest)
        if self.vfs.exists(path):
            self.vfs.delete(path)

    def _cleanup_stale(self, generation, identity, request_id="", item=None):
        request = self.requests.get(generation)
        if item is not None:
            request_id = item.getProperty("AcTweeteR.PreviewRequestId")
        # A stale callback must not delete a different generation's manifest,
        # even if its item carries a syntactically valid temporary filename.
        if (not isinstance(request_id, str) or
                re.fullmatch(r"[0-9a-f]{32}-[1-9][0-9]*", request_id) is None or
                (request is not None and request.identity != identity) or
                (self.request_ids.get(generation) not in (None, request_id))):
            return False
        manifest = item.getProperty("AcTweeteR.PreviewManifest") if item else ""
        expected_manifest = "special://temp/actweeter_preview_%s.mpd" % request_id
        if manifest and manifest != expected_manifest:
            return False
        self._delete_manifest(expected_manifest)
        if self.request_ids.get(generation) == request_id:
            self._clear_generation(generation)
            self.requests.pop(generation, None)
            self.item_data.pop(generation, None)
            self.request_ids.pop(generation, None)
        self.stale_owned.discard((generation, request_id))
        with self.wake:
            self.wake.notify_all()
        return True

    def terminal_by_identity(self, generation, identity, request_id, event):
        request = self.requests.get(generation)
        if (generation, request_id) in self.stale_owned:
            return self._cleanup_stale(generation, identity, request_id)
        if (request is None or request.identity != identity or
                self.request_ids.get(generation) != request_id):
            return False
        with self.wake:
            if not self.scheduler.terminal(request):
                self._delete_manifest(
                    "special://temp/actweeter_preview_%s.mpd" % request_id)
                self.requests.pop(generation, None)
                self.item_data.pop(generation, None)
                self._clear_generation(generation)
                self.request_ids.pop(generation, None)
                self._record_ownership_release(generation, event)
                self.wake.notify_all()
                return True
            self.scheduler.ownership.terminal(request, event)
            self.requests.pop(generation, None)
            self.item_data.pop(generation, None)
            self._delete_manifest(
                "special://temp/actweeter_preview_%s.mpd" % request_id)
            self._clear_generation(generation)
            self.request_ids.pop(generation, None)
            self._record_ownership_release(generation, event)
            self.wake.notify_all()
            return True

    def _record_ownership_release(self, generation, event):
        released_at = self.clock()
        with self.stop_lock:
            timeline = self.stop_timeline.get(generation)
            if timeline is not None:
                timeline["ownership_released_at"] = released_at
                stop_delay = int(max(0, released_at - timeline["requested_at"]) * 1000)
                callback_at = timeline.get("terminal_callback_at")
                callback_delay = (int(max(0, released_at - callback_at) * 1000)
                                  if callback_at is not None else "none")
                if "worker_finished_at" in timeline:
                    self.stop_inflight.discard(generation)
                if ("worker_finished_at" in timeline and
                        "terminal_callback_at" in timeline):
                    self.stop_timeline.pop(generation, None)
            else:
                stop_delay = callback_delay = "none"
        self._log("OWNERSHIP_RELEASED", generation=generation,
                  playback_event=event, stop_to_release_ms=stop_delay,
                  callback_to_release_ms=callback_delay)
        with self.wake:
            self.wake.notify_all()

    def stop_stale_item(self, item):
        """Stop only a preview ListItem proven stale by its own generation tag."""
        if item.getProperty("AcTweeteR.PreviewOwner") != "AUTO_PREVIEW":
            return False
        try:
            generation = int(item.getProperty("AcTweeteR.PreviewGeneration"))
        except (TypeError, ValueError):
            return False
        identity = item.getProperty("AcTweeteR.PreviewIdentity")
        request = self.requests.get(generation)
        if request is not None and request.identity != identity:
            return False
        request_id = item.getProperty("AcTweeteR.PreviewRequestId")
        if self._owned_item() != (str(generation), identity, request_id):
            return False
        self.player.stop()
        return True

    def external_playback_ended(self):
        """Allow later movie focus after a non-preview player has ended."""
        with self.wake:
            self.scheduler.external_playback_ended()
            self.wake.notify_all()

    def _take_ready(self, now, player_active=False):
        # Kodi can deliver its terminal callback before xbmc.Player.stop()
        # returns. Do not let another automatic resolution hand a new item to
        # Kodi until that one Stop call has fully returned.
        with self.stop_lock:
            if self.stop_inflight:
                return None
        return self.scheduler.take_ready(now, player_active=player_active)

    def _active_focus_still_matches(self, request):
        """Check the selected card, not only the widget control's focus.

        Kodi does not emit control on-unfocus when moving between items in
        the same panel. Polling avoids leaving an owned trailer playing for
        the previously selected poster. Only an owned preview may be stopped.
        """
        try:
            if self._owned_fullscreen(request):
                return True
            if not self.kodi.getCondVisibility("Window.IsActive(%d)" % request.window):
                return False
            if int(self.kodi.getInfoLabel("System.CurrentControlId") or "-1") != request.focus:
                return False
            if int(self.kodi.getInfoLabel(
                    "Container(%d).CurrentItem" % request.container) or "-1") != request.position:
                return False
            prefix = "Container(%d).ListItem." % request.container
            return stable_identity({
                "imdb": self.kodi.getInfoLabel(prefix + "UniqueID(imdb)"),
                "tmdb": self.kodi.getInfoLabel(prefix + "UniqueID(tmdb)"),
                "dbid": self.kodi.getInfoLabel(prefix + "DBID"),
            }) == request.identity
        except (ValueError, TypeError):
            return False

    def _refocus_current_card(self, previous):
        """Request the newly selected poster after the old owned trailer stops."""
        if not self.kodi.getCondVisibility("Window.IsActive(%d)" % previous.window):
            return
        try:
            focus = int(self.kodi.getInfoLabel("System.CurrentControlId") or "-1")
            position = int(self.kodi.getInfoLabel(
                "Container(%d).CurrentItem" % previous.container) or "-1")
        except (TypeError, ValueError):
            return
        if focus != previous.focus or position < 0:
            return
        prefix = "Container(%d).ListItem." % previous.container
        payload = {
            "window": previous.window, "container": previous.container,
            "focus": focus, "position": position,
            **read_preview_metadata(self.kodi, prefix),
            "trailer_id": "", "delay": 3.0,
        }
        if stable_identity(payload) != previous.identity:
            self._log("CARD_REFOCUS", container=previous.container,
                      position=position)
            self._focus(payload)

    def _poll_selected_card(self):
        """Kodi's control onfocus does not report selection changes in a row."""
        previous = self.focus_context
        if not previous or self.kodi.getCondVisibility("Player.HasMedia"):
            return
        window, container, focus = (int(previous[key]) for key in ("window", "container", "focus"))
        if not self.kodi.getCondVisibility("Window.IsActive(%d)" % window):
            return
        try:
            if int(self.kodi.getInfoLabel("System.CurrentControlId") or "-1") != focus:
                return
            position = int(self.kodi.getInfoLabel("Container(%d).CurrentItem" % container) or "-1")
        except (TypeError, ValueError):
            return
        prefix = "Container(%d).ListItem." % container
        current = dict(previous, position=position, trailer_id="",
                       **read_preview_metadata(self.kodi, prefix))
        if (position, stable_identity(current), current["media_type"]) != (
                int(previous["position"]), stable_identity(previous), previous.get("media_type")):
            self._log("CARD_SELECTION_CHANGED", container=container, position=position)
            self._focus(current)

    def _work(self):
        while not self.closed:
            with self.wake:
                active = self.scheduler.active
            if active is not None and not self._active_focus_still_matches(active):
                self._log("FOCUS_CHANGED", generation=active.generation)
                self._preempt({"owner": "OTHER"})
                # Explicit preemption clears deferred focus by design for
                # manual/VOD handoff. Re-arm only this internal card-change
                # path, after preemption, to preview the newly selected card.
                self.refocus_after_stop = active
            if self.refocus_after_stop is not None:
                try:
                    playing = self.kodi.getCondVisibility("Player.HasMedia")
                except Exception:
                    playing = True
                if not playing:
                    previous = self.refocus_after_stop
                    self.refocus_after_stop = None
                    self._refocus_current_card(previous)
            self._poll_selected_card()
            with self.wake:
                now = self.clock()
                has_media = getattr(self.kodi, "getCondVisibility", None)
                player_active = bool(has_media("Player.HasMedia")) if has_media else False
                request = self._take_ready(now, player_active=player_active)
                if request is None:
                    timeout = 0.25 if self.scheduler.active is not None or self.refocus_after_stop is not None or self.focus_context is not None else 1.0
                    if self.scheduler.delay_deadline is not None:
                        timeout = min(timeout, max(0.01, self.scheduler.delay_deadline - now))
                    self.wake.wait(timeout)
                    continue
            has_media = getattr(self.kodi, "getCondVisibility", None)
            if has_media and has_media("Player.HasMedia"):
                with self.wake:
                    self.requests.pop(request.generation, None)
                    self.scheduler.latest = None
                    self.scheduler.delay_deadline = None
                    self.scheduler.resolving = None
                    self.scheduler.ownership.external_playback()
                    self._clear_current()
                    self.wake.notify_all()
                continue
            try:
                item_data = self.item_data.get(request.generation, {})
                terminal_at = self.last_terminal_at
                after_terminal_ms = (int(max(0, self.clock() - terminal_at) * 1000)
                                     if terminal_at is not None else "none")
                self._log("RESOLUTION_DISPATCH", generation=request.generation,
                          after_terminal_ms=after_terminal_ms)
                self.run_script({
                    "action": "resolve", "generation": request.generation,
                    "identity": request.identity, "window": request.window,
                    "container": request.container, "focus": request.focus,
                    "position": request.position,
                    "request_id": self.request_ids[request.generation],
                    **item_data,
                })
            except Exception as exc:
                self._log("RESOLUTION_DISPATCH_FAILED", generation=request.generation,
                          error=type(exc).__name__)
                self._resolved({"generation": request.generation,
                                "request_id": self.request_ids.get(request.generation),
                                "status": "launch_error"})

    def close(self):
        self.closed = True
        with self.wake:
            request = self.scheduler.active
            self.scheduler.preempt("OTHER")
            self._clear_current()
            self.wake.notify_all()
        self._stop_owned(request, require_active=False)
