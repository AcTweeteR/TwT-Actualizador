"""Offline explicit Trakt action boundary, without Kodi playback hooks."""
import importlib
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'addons/service.actweeter/resources'))
Outbox = importlib.import_module('lib.trakt_outbox').Outbox
Actions = importlib.import_module('lib.trakt_explicit_actions').ExplicitWatchedActions
identity = importlib.import_module('lib.trakt_sync').identity


class ExplicitActionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.queue = Outbox(Path(temp.name) / 'queue.db')
        self.actions = Actions(self.queue)
        self.content = identity('movie', {'tmdb': 42})
        self.operation = self.actions.prepare(account='account-a', profile='1',
            identity=self.content, watched_at='2026-10-21T12:00:00Z')

    def test_preparation_never_sends(self):
        self.assertEqual(self.queue.status(self.operation), {'state': 'pending', 'attempts': 0})
        self.assertEqual(self.actions.prepare(account='account-a', profile='1',
            identity=self.content, watched_at='2026-10-21T12:00:00Z'), self.operation)

    def test_submit_requires_operation_specific_approval(self):
        calls = []
        def post(path, payload):
            calls.append(path)
            return {'added': {'movies': 1}, 'not_found': {}}
        with self.assertRaises(PermissionError):
            self.actions.submit(self.operation, account='account-a', profile='1',
                approval=None, post=post, now=1)
        self.assertEqual(calls, [])
        self.assertEqual(self.actions.submit(self.operation, account='account-a', profile='1',
            approval=self.operation, post=post, now=1), 'confirmed')
        self.assertEqual(calls, ['/sync/history'])

    def test_readback_after_network_loss(self):
        def timeout(*args): raise TimeoutError()
        self.actions.submit(self.operation, account='account-a', profile='1',
            approval=self.operation, post=timeout, now=1)
        event = self.queue.status(self.operation)
        self.assertEqual(event['state'], 'unknown')
        snapshot = {'account': 'account-a', 'complete': True,
            'history': [{'identity': self.content, 'watched_at': '2026-10-21T12:00:00Z'}]}
        result = self.actions.verify([self.operation], snapshot, account='account-a', profile='1')
        self.assertEqual(result[self.operation], 'confirmed')
        self.assertEqual(self.queue.status(self.operation)['attempts'], 1)


if __name__ == '__main__':
    unittest.main()
