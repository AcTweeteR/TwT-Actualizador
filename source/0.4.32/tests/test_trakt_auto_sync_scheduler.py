import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'addons/service.actweeter/resources/lib'))
import trakt_sync_consent as consent
from trakt_sync_scheduler import Scheduler


class TraktAutoSyncSchedulerTests(unittest.TestCase):
    def test_consent_is_scoped_private_durable_and_revocable(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'profile' / 'trakt_live' / 'consent.json'
            scope = 'a' * 64
            consent.grant(path, account='user-1', profile='2', provider_scope=scope)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertTrue(consent.enabled(path))
            self.assertTrue(consent.authorized(
                path, account='user-1', profile='2', provider_scope=scope))
            for changed in ({'account': 'user-2'}, {'profile': '1'},
                            {'provider_scope': 'b' * 64}):
                args = dict(account='user-1', profile='2', provider_scope=scope)
                args.update(changed)
                self.assertFalse(consent.authorized(path, **args))
            self.assertTrue(consent.suspend(path))
            self.assertFalse(consent.enabled(path))
            self.assertFalse(consent.authorized(
                path, account='user-1', profile='2', provider_scope=scope))
            consent.grant(path, account='user-1', profile='2', provider_scope=scope)
            consent.revoke(path)
            self.assertFalse(consent.enabled(path))

    def test_consent_rejects_unverified_or_unsafe_scope(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'consent.json'
            with self.assertRaises(ValueError):
                consent.grant(path, account='', profile='2', provider_scope='a' * 64)
            path.symlink_to(Path(folder) / 'missing')
            self.assertFalse(consent.enabled(path))

    def test_scheduler_requires_opt_in_skips_playback_and_waits_five_minutes(self):
        with tempfile.TemporaryDirectory() as folder:
            now = [1000.0]
            scheduler = Scheduler(Path(folder) / 'scheduler.json', clock=lambda: now[0])
            calls = []
            dispatch = lambda: calls.append(now[0])
            self.assertFalse(scheduler.dispatch_if_due(dispatch, authorized=False))
            self.assertFalse(scheduler.dispatch_if_due(dispatch, authorized=True, playing=True))
            self.assertTrue(scheduler.dispatch_if_due(dispatch, authorized=True))
            self.assertFalse(scheduler.dispatch_if_due(dispatch, authorized=True))
            now[0] += 299
            self.assertFalse(scheduler.dispatch_if_due(dispatch, authorized=True))
            now[0] += 1
            self.assertTrue(scheduler.dispatch_if_due(dispatch, authorized=True))
            self.assertEqual(len(calls), 2)

    def test_dispatch_failure_uses_bounded_exponential_backoff(self):
        with tempfile.TemporaryDirectory() as folder:
            now = [10.0]
            path = Path(folder) / 'scheduler.json'
            scheduler = Scheduler(path, clock=lambda: now[0])
            fail = lambda: (_ for _ in ()).throw(RuntimeError('offline'))
            self.assertFalse(scheduler.dispatch_if_due(fail, authorized=True))
            state = json.loads(path.read_text())
            self.assertEqual(state['failures'], 1)
            self.assertEqual(state['next_at'], 310.0)

    def test_concurrent_calls_dispatch_once(self):
        with tempfile.TemporaryDirectory() as folder:
            scheduler = Scheduler(Path(folder) / 'scheduler.json', clock=lambda: 100)
            entered = threading.Event()
            release = threading.Event()
            calls = []
            def dispatch():
                calls.append(1)
                entered.set()
                release.wait(2)
            result = []
            thread = threading.Thread(target=lambda: result.append(
                scheduler.dispatch_if_due(dispatch, authorized=True)))
            thread.start()
            self.assertTrue(entered.wait(1))
            self.assertFalse(scheduler.dispatch_if_due(dispatch, authorized=True))
            release.set()
            thread.join(2)
            self.assertEqual(calls, [1])
            self.assertEqual(result, [True])


if __name__ == '__main__':
    unittest.main()
