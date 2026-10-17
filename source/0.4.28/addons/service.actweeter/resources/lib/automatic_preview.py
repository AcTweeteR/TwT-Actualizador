"""Pure request/ownership gate for automatic trailers; no Kodi or network I/O.

The caller must attach the request ID to the resolved ListItem and observe that
ID from Player.getPlayingItem(). Global pending state alone is not ownership.
"""

from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True)
class PreviewRequest:
    generation: int
    identity: str
    window: int
    container: int
    focus: int
    provider: str = "SLYGUY"
    position: int = -1


class PreviewOwnership:
    OWNERS = {"NONE", "AUTO_PREVIEW", "MANUAL_DETAIL", "MANUAL_SPOTLIGHT", "OTHER"}

    def __init__(self):
        self.lock = RLock()
        self.generation = 0
        self.request = None
        self.started = None
        self.launching = None
        self.owner = "NONE"

    def external_playback(self):
        """Invalidate automatic work as soon as a non-preview player starts."""
        with self.lock:
            self.generation += 1
            self.request = None
            self.launching = None
            self.started = None
            self.owner = "OTHER"

    def service_stopped(self):
        """Drop in-memory ownership on normal service shutdown/restart."""
        with self.lock:
            self.generation += 1
            self.request = None
            self.launching = None
            self.started = None
            self.owner = "NONE"

    def external_playback_ended(self):
        """Release an external playback owner without reviving old requests."""
        with self.lock:
            if self.owner != "AUTO_PREVIEW":
                self.generation += 1
                self.request = None
                self.launching = None
                self.started = None
                self.owner = "NONE"

    def candidate(self, identity, window, container, focus, position=-1):
        with self.lock:
            self.generation += 1
            self.request = None
            if (not identity or window not in (10000, 11111) or
                    container <= 0 or focus in (40000, 40003) or
                    self.owner not in ("NONE", "AUTO_PREVIEW")):
                return None
            self.request = PreviewRequest(self.generation, identity, window, container, focus,
                                          position=position)
            return self.request

    def latest_candidate(self, identity, window, container, focus, position=-1):
        """Replace a pending candidate (latest-wins); never create a FIFO."""
        return self.candidate(identity, window, container, focus, position)

    def current(self, request, identity, window, container):
        with self.lock:
            return (request is not None and request == self.request and
                    request.generation == self.generation and
                    request.identity == identity and request.window == window and
                    request.container == container and
                    self.owner in ("NONE", "AUTO_PREVIEW"))

    def cancel(self):
        with self.lock:
            self.generation += 1
            self.request = None

    def may_launch(self, request, identity, window, container, player_active):
        with self.lock:
            return (not player_active and self.launching is None and
                    self.current(request, identity, window, container))

    def av_started(self, request, observed_request, identity, window, container):
        """Return ACCEPT, STOP_STALE_OWNED, or IGNORE_UNOWNED.

        STOP is allowed only for the actual ListItem carrying this request ID;
        it can never be used to stop a VOD/manual player based on old markers.
        """
        with self.lock:
            if request is None or observed_request != request.generation:
                return "IGNORE_UNOWNED"
            if self.owner in ("MANUAL_DETAIL", "MANUAL_SPOTLIGHT", "OTHER"):
                return "IGNORE_UNOWNED"
            if not self.current(request, identity, window, container):
                self.started = request
                self.owner = "AUTO_PREVIEW"
                if self.launching == request:
                    self.launching = None
                return "STOP_STALE_OWNED"
            self.started = request
            if self.launching == request:
                self.launching = None
            self.owner = "AUTO_PREVIEW"
            return "ACCEPT"

    def may_stop(self, request, observed_request):
        with self.lock:
            return (self.owner == "AUTO_PREVIEW" and request is not None and
                    self.started == request and observed_request == request.generation)

    def handoff(self, owner):
        if owner not in ("MANUAL_DETAIL", "MANUAL_SPOTLIGHT", "OTHER"):
            raise ValueError("invalid playback owner")
        with self.lock:
            previous = self.started if self.owner == "AUTO_PREVIEW" else None
            self.cancel()
            self.owner = owner
            self.started = None
            self.launching = None
            return previous

    def terminal(self, request, event):
        with self.lock:
            if (event not in ("stopped", "ended", "error") or request is None or
                    self.owner != "AUTO_PREVIEW" or self.started != request):
                return False
            self.started = None
            if self.launching == request:
                self.launching = None
            self.owner = "NONE"
            if self.request == request:
                self.request = None
            return True

    def terminal_playing_item(self, event, observed_generation, listitem_owner):
        """Callback entry point: a Kodi player event must carry our ListItem tag."""
        with self.lock:
            request = self.started
            if (request is None or listitem_owner != "AUTO_PREVIEW" or
                    observed_generation != request.generation):
                return False
        return self.terminal(request, event)

    def launch_failed(self, request):
        """Release only this unstarted reservation on a real provider error."""
        with self.lock:
            if (request is None or self.launching != request or
                    self.started is not None or self.owner != "NONE"):
                return False
            self.launching = None
            return True

    def may_fallback(self, request, reason, identity, window, container):
        with self.lock:
            return (reason in ("NO_RESULTS", "RESOLUTION_ERROR") and
                    self.current(request, identity, window, container) and
                    self.started is None)

    def resolve_and_launch(self, request, snapshot, resolve, launch):
        """Resolve away from Kodi's UI and revalidate before requesting play.

        `resolve` must only resolve, never dispatch or play. `launch` receives
        the request so the Kodi ListItem can carry its generation. AVStarted
        must still validate that tag because Kodi starts asynchronously.
        """
        if not self.may_launch(request, **snapshot()):
            return "CANCELLED"
        try:
            resolved = resolve(request)
        except Exception:
            with self.lock:
                if not self.may_launch(request, **snapshot()):
                    return "STALE"
                return "RESOLUTION_ERROR"
        with self.lock:
            if not self.may_launch(request, **snapshot()):
                return "STALE"
            if resolved is None:
                return "NO_RESULTS"
            self.launching = request
            try:
                launch(resolved, request)
            except Exception:
                if self.launching == request:
                    self.launching = None
                return "LAUNCH_ERROR"
            return "LAUNCH_REQUESTED"


class LatestPreviewScheduler:
    """Single-resolver latest-wins scheduler, independent of Kodi APIs."""

    def __init__(self, ownership=None):
        from threading import Condition
        self.condition = Condition(RLock())
        self.ownership = ownership or PreviewOwnership()
        self.latest = None
        self.resolving = None
        self.active = None
        self.delay_deadline = None
        self.cancelled = 0
        self.stale = 0

    def offer(self, request, delay_seconds, now):
        with self.condition:
            if self.latest is not None or self.resolving is not None:
                self.cancelled += 1
            self.latest = request
            self.ownership.request = request
            self.ownership.generation = request.generation
            self.delay_deadline = now + max(0.0, float(delay_seconds))
            self.condition.notify_all()

    def cancel(self, identity=None):
        with self.condition:
            current = self.latest or self.resolving or self.active
            if current is not None and identity and current.identity != identity:
                return False
            if self.latest is not None or self.resolving is not None:
                self.cancelled += 1
            self.latest = None
            self.delay_deadline = None
            self.ownership.cancel()
            self.condition.notify_all()
            return True

    def take_ready(self, now, player_active=False):
        """Claim only one resolver slot, and only after inherited preview delay."""
        with self.condition:
            if (self.latest is None or self.resolving is not None or
                    self.active is not None or player_active or
                    self.delay_deadline is None or now < self.delay_deadline):
                return None
            request = self.latest
            self.latest = None
            self.delay_deadline = None
            self.resolving = request
            return request

    def resolution_finished(self, request, *, still_current):
        with self.condition:
            if self.resolving != request:
                self.stale += 1
                return False
            self.resolving = None
            if not still_current:
                self.stale += 1
                self.condition.notify_all()
                return False
            self.active = request
            self.condition.notify_all()
            return True

    def terminal(self, request):
        with self.condition:
            if self.active != request:
                return False
            self.active = None
            self.condition.notify_all()
            return True

    def preempt(self, owner):
        if owner not in ("MANUAL_DETAIL", "MANUAL_SPOTLIGHT", "VOD", "OTHER"):
            raise ValueError("unsupported preempting owner")
        with self.condition:
            active = self.active
            self.latest = None
            self.active = None
            self.delay_deadline = None
            self.ownership.generation += 1
            self.ownership.request = None
            self.ownership.launching = None
            self.ownership.started = None
            self.ownership.owner = owner
            self.condition.notify_all()
            return active

    def external_playback_ended(self):
        with self.condition:
            if self.active is None:
                self.ownership.external_playback_ended()
            self.condition.notify_all()

    def resolver_count(self):
        with self.condition:
            return int(self.resolving is not None)
