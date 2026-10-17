"""Pure decision helpers for returning from a manual SlyGuy movie trailer."""

from __future__ import annotations


DETAIL_WINDOW_ID = 12003
HOME_WINDOW_ID = 10000
SPOTLIGHT_CONTROL_ID = 1508
MOVIES_HUB_WINDOW_ID = 11111
MOVIE_LIST_WINDOW_IDS = frozenset((MOVIES_HUB_WINDOW_ID, 10025))
IDENTITY_PREFIXES = ("imdb", "tmdb", "dbid")
TERMINAL_EVENTS = frozenset(("stopped", "ended", "error"))


def parse_identity(value):
    """Accept only a typed, non-empty provider/database identity."""
    if not isinstance(value, str) or ":" not in value:
        return None
    kind, identifier = value.split(":", 1)
    if kind not in IDENTITY_PREFIXES or not identifier:
        return None
    if any(char in identifier for char in "\r\n\x00"):
        return None
    return kind, identifier


def identity_matches(identity, current_values):
    """Compare the captured identity with Kodi's current ListItem identity."""
    parsed = parse_identity(identity)
    if parsed is None:
        return False
    kind, expected = parsed
    return str(current_values.get(kind, "")) == expected


def marker_cleanup_allowed(current_identity, expected_identity, *,
                           identity_verified=False, pending=False,
                           explicit_request=False):
    """Allow cleanup after verified detail restoration without racing a new request."""
    if current_identity == expected_identity:
        return True
    return (not current_identity and identity_verified and
            not pending and not explicit_request)


def capture_context(*, pending, explicit_request, vod_pending, window_id,
                    item_type, identity, current_values, origin="VIDEO_INFO",
                    source_window_id=None, return_control_id=None):
    """Capture an explicitly armed SlyGuy request from an approved surface."""
    if not pending or not explicit_request or vod_pending:
        return None
    if str(item_type).casefold() != "movie":
        return None
    if not identity_matches(identity, current_values):
        return None
    kind, _ = parse_identity(identity)
    origin = str(origin or "VIDEO_INFO").upper()
    if origin == "VIDEO_INFO":
        if window_id != DETAIL_WINDOW_ID:
            return None
        return {"identity": identity, "identity_kind": kind,
                "origin": origin, "return_window_id": DETAIL_WINDOW_ID}
    if origin == "SPOTLIGHT":
        if (source_window_id != HOME_WINDOW_ID or
                return_control_id != SPOTLIGHT_CONTROL_ID):
            return None
        return {"identity": identity, "identity_kind": kind,
                "origin": origin, "return_window_id": HOME_WINDOW_ID,
                "return_control_id": SPOTLIGHT_CONTROL_ID}
    return None


def return_decision(context, *, event, player_active, window_id, current_values,
                    control_focused=False):
    """Return wait, preserve, restore, or abandon based on observed Kodi state."""
    if not context or event not in TERMINAL_EVENTS:
        return "ignore"
    if player_active:
        return "wait"
    if context.get("origin") == "SPOTLIGHT" and window_id == HOME_WINDOW_ID:
        parsed = parse_identity(context["identity"])
        observed = current_values.get(parsed[0], "") if parsed else ""
        if not observed:
            return "wait"
        if str(observed) != parsed[1]:
            return "abandon"
        return "preserve" if control_focused else "focus_spotlight"
    if window_id == context.get("return_window_id") and identity_matches(
            context["identity"], current_values):
        if context.get("origin") == "SPOTLIGHT" and not control_focused:
            return "focus_spotlight"
        return "preserve"
    if context.get("origin") == "SPOTLIGHT":
        if window_id == HOME_WINDOW_ID:
            return "abandon"
        return "wait"
    if window_id in MOVIE_LIST_WINDOW_IDS and identity_matches(
            context["identity"], current_values):
        return "restore"
    if window_id == DETAIL_WINDOW_ID or window_id in MOVIE_LIST_WINDOW_IDS:
        return "abandon"
    return "wait"


class TerminalEventGate:
    """Claim at most one terminal callback for a captured trailer context."""

    def __init__(self):
        self.claimed = False

    def claim(self, event):
        if self.claimed or event not in TERMINAL_EVENTS:
            return False
        self.claimed = True
        return True
