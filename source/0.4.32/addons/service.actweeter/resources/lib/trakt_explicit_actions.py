"""Opt-in service boundary for explicit Trakt watched-history actions.

Playback callbacks and scheduled background jobs must not call this adapter:
script.trakt remains the playback scrobbler. No credentials are stored here.
"""
from .trakt_outbox import watched_event
from .trakt_reconciliation import reconcile_uncertain


class ExplicitWatchedActions:
    def __init__(self, outbox):
        self.outbox = outbox

    def prepare(self, *, account, profile, identity, watched_at):
        """Durably stage an explicit operation; never send it automatically."""
        event = watched_event(account, profile, identity, watched_at)
        return self.outbox.enqueue(event)

    def submit(self, operation, *, account, profile, approval, post, now):
        """A separate user-approved operation ID is required for any POST."""
        return self.outbox.send(operation, account=account, profile=profile,
                                approved=approval, post=post, now=now)

    def verify(self, operations, snapshot, *, account, profile):
        """Resolve uncertain operations using authenticated complete GET data."""
        return reconcile_uncertain(self.outbox, operations, snapshot,
                                   account=account, profile=profile)
