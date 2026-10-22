"""No network: explicit operations, uncertain writes and restart safety."""
import importlib
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'addons/service.actweeter/resources'))
outbox = importlib.import_module('lib.trakt_outbox')
sync = importlib.import_module('lib.trakt_sync')


class OutboxTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'queue.sqlite'
        self.queue = outbox.Outbox(self.path)
        self.event = outbox.watched_event('synthetic-account', '1',
            sync.identity('movie', {'tmdb': 42}), '2026-10-21T12:00:00Z')
        self.op = self.queue.enqueue(self.event)
        self.calls = []

    def send(self, **kwargs):
        options = {'account': 'synthetic-account', 'profile': '1', 'approved': self.op,
                   'post': self.post, 'now': 100}
        options.update(kwargs)
        return self.queue.send(self.op, **options)

    def post(self, path, payload):
        self.calls.append((path, payload))
        return {'added': {'movies': 1, 'episodes': 0}, 'not_found': {}}

    def test_repeated_enqueue_and_restart_do_not_duplicate(self):
        self.assertEqual(outbox.Outbox(self.path).enqueue(self.event), self.op)
        self.assertEqual(self.send(), 'confirmed')
        self.assertEqual(self.send(), 'confirmed')
        self.assertEqual(len(self.calls), 1)

    def test_specific_approval_is_required_before_network(self):
        for approval in (None, True, 'another-operation'):
            with self.assertRaises(PermissionError): self.send(approved=approval)
        self.assertFalse(self.calls)

    def test_account_or_profile_change_blocks_send(self):
        for kwargs in ({'account': 'other'}, {'profile': '2'}):
            with self.assertRaises(PermissionError): self.send(**kwargs)
        self.assertFalse(self.calls)

    def test_unknown_outcome_is_never_retried(self):
        def timeout(*args): raise TimeoutError()
        self.assertEqual(self.send(post=timeout), 'unknown')
        self.assertEqual(self.send(), 'unknown')
        self.assertFalse(self.calls)
        self.assertEqual(self.queue.status(self.op)['attempts'], 1)

    def test_inflight_after_crash_is_not_retried(self):
        with self.queue.connect() as db:
            db.execute("UPDATE events SET state='inflight' WHERE id=?", (self.op,))
        self.queue = outbox.Outbox(self.path)
        self.assertEqual(self.send(), 'inflight')
        self.assertFalse(self.calls)

    def test_confirmed_rate_limit_waits_before_retry(self):
        def rate_limit(*args): raise outbox.RetryLater(30)
        self.assertEqual(self.send(post=rate_limit), 'pending')
        self.assertEqual(self.send(now=120), 'pending')
        self.assertFalse(self.calls)
        self.assertEqual(self.send(now=131), 'confirmed')

    def test_not_found_or_malformed_success_is_not_confirmed(self):
        self.assertEqual(self.send(post=lambda *_: {'added': {'movies': 0}}), 'unknown')

    def test_payload_cannot_inject_arbitrary_endpoint_or_url(self):
        self.event['payload']['url'] = 'https://invalid.example'
        with self.assertRaises(ValueError): self.queue.enqueue(self.event)

    def test_lost_response_can_be_confirmed_without_reposting(self):
        def timeout(*args): raise TimeoutError()
        self.send(post=timeout)
        snapshot = {'account': 'synthetic-account', 'complete': True, 'history': [
            {'identity': self.event['identity'], 'watched_at': self.event['watched_at']}]}
        self.assertEqual(self.queue.confirm_from_snapshot(self.op, snapshot,
                         account='synthetic-account', profile='1'), 'confirmed')
        self.assertEqual(self.send(), 'confirmed')
        self.assertFalse(self.calls)

    def test_different_date_or_content_does_not_resolve_unknown_write(self):
        def timeout(*args): raise TimeoutError()
        self.send(post=timeout)
        snapshot = {'account': 'synthetic-account', 'complete': True, 'history': [
            {'identity': self.event['identity'], 'watched_at': '2026-10-20T12:00:00Z'}]}
        self.assertEqual(self.queue.confirm_from_snapshot(self.op, snapshot,
                         account='synthetic-account', profile='1'), 'unknown')
        with self.assertRaises(PermissionError):
            self.queue.confirm_from_snapshot(self.op, snapshot, account='other', profile='1')

    def test_partial_history_never_confirms_uncertain_write(self):
        self.send(post=lambda *_: (_ for _ in ()).throw(TimeoutError()))
        snapshot = {'account': 'synthetic-account', 'history': [
            {'identity': self.event['identity'], 'watched_at': self.event['watched_at']}]}
        for complete in (None, False):
            candidate = dict(snapshot)
            if complete is not None:
                candidate['complete'] = complete
            with self.assertRaises(ValueError):
                self.queue.confirm_from_snapshot(self.op, candidate,
                    account='synthetic-account', profile='1')
        self.assertEqual(self.queue.status(self.op)['state'], 'unknown')
        self.assertEqual(self.send(), 'unknown')
        self.assertFalse(self.calls)

    def test_episode_payload_marks_only_one_explicit_episode(self):
        content = sync.identity('episode', show_ids={'tmdb': 42}, season=0, episode=1)
        event = outbox.watched_event('synthetic-account', '1', content, self.event['watched_at'])
        seasons = event['payload']['shows'][0]['seasons']
        self.assertEqual(seasons, [{'number': 0, 'episodes': [{'number': 1, 'watched_at': self.event['watched_at']}]}])
        with self.assertRaises(ValueError):
            outbox.watched_event('synthetic-account', '1', sync.identity('show', {'tmdb': 42}), self.event['watched_at'])


if __name__ == '__main__':
    unittest.main()
