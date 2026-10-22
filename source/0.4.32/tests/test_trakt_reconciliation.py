"""Offline Trakt readback reconciliation; never calls Trakt endpoints."""
import importlib
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'addons/service.actweeter/resources'))
outbox = importlib.import_module('lib.trakt_outbox')
reconcile = importlib.import_module('lib.trakt_reconciliation').reconcile_uncertain
sync = importlib.import_module('lib.trakt_sync')


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.queue = outbox.Outbox(Path(temp.name) / 'events.sqlite')
        self.event = outbox.watched_event('account-a', '1',
            sync.identity('movie', {'tmdb': 42}), '2026-10-21T12:00:00Z')
        self.op = self.queue.enqueue(self.event)
        self.queue.send(self.op, account='account-a', profile='1', approved=self.op,
                        post=lambda *_: (_ for _ in ()).throw(TimeoutError()), now=1)
        self.snapshot = {'account': 'account-a', 'complete': True,
                         'history': [{'identity': self.event['identity'],
                                      'watched_at': self.event['watched_at']}]}

    def test_matching_history_confirms_without_repost(self):
        self.assertEqual(reconcile(self.queue, [self.op], self.snapshot,
                                   account='account-a', profile='1')[self.op], 'confirmed')
        self.assertEqual(self.queue.status(self.op)['attempts'], 1)

    def test_incomplete_or_wrong_account_cannot_confirm(self):
        for altered in ({'complete': False}, {'account': 'account-b'}, {'history': None}):
            with self.assertRaises(ValueError):
                reconcile(self.queue, [self.op], dict(self.snapshot, **altered),
                          account='account-a', profile='1')
        self.assertEqual(self.queue.status(self.op)['state'], 'unknown')

    def test_missing_history_preserves_unknown(self):
        snapshot = dict(self.snapshot, history=[])
        self.assertEqual(reconcile(self.queue, [self.op], snapshot,
                                   account='account-a', profile='1')[self.op], 'unknown')

    def test_profile_mismatch_rejected(self):
        with self.assertRaises(PermissionError):
            reconcile(self.queue, [self.op], self.snapshot, account='account-a', profile='2')


if __name__ == '__main__':
    unittest.main()
