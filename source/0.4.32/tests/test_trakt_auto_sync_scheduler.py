import json
import sys
import tempfile
import threading
import unittest
import importlib.util
import types
from unittest.mock import Mock, patch
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



class AutoCycleProgressTests(unittest.TestCase):
    def test_legacy_pending_allows_new_activity_without_reexport_or_data_loss(self):
        sys.path.insert(0, str(ROOT / 'addons/service.actweeter/resources'))
        from lib import trakt_auto_cycle as cycle
        from lib.trakt_live_queue import build_batch, write_batch, write_ack
        from test_trakt_sync import sync, LATE
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            service = root / 'service'
            queue = service / 'trakt_live/queue'
            scope = 'a' * 64
            def batch(tmdb, **kwargs):
                return build_batch({'profile': '1', 'account': 'user', 'items': [
                    {'identity': sync.identity('movie', {'tmdb': str(tmdb)}),
                     'provider_id': str(tmdb), 'watched': True, 'watched_at': LATE}]},
                    provider_scope=scope, consent=True, **kwargs)
            legacy = write_batch(queue, batch(42, batch_id='0' * 32))
            (service / 'trakt_live').chmod(0o700)
            original = legacy.read_bytes()
            activity = {'all': 'first'}
            export = Mock(return_value=root)
            def prepare(*args, **kwargs):
                return [batch(43, activity_fingerprint=kwargs['activity_fingerprint'],
                              catalog_generation=kwargs['catalog_generation'])]
            def apply(path, ackroot, **kwargs):
                value = json.loads(Path(path).read_text())
                return write_ack(Path(ackroot) / (value['batch_id'] + '.json'), value,
                                 [{'id': op['id'], 'status': 'applied', 'reason': None}
                                  for op in value['operations']])
            args = dict(account='user', profile='1', provider_scope=scope,
                        activity_get=lambda: ('user', activity), export_snapshot=export,
                        apply_batch=apply, addon=None, history=None, one_shot=True)
            with patch.object(cycle, 'prepare_batches', side_effect=prepare) as planner:
                self.assertEqual(cycle.run_cycle(service, root, **args)['status'], 'queued')
                self.assertEqual(cycle.run_cycle(service, root, **args)['status'], 'pending')
                self.assertEqual(cycle.run_cycle(service, root, **args)['status'], 'deferred')
                self.assertEqual(export.call_count, 1)
                self.assertEqual(planner.call_count, 1)
                self.assertFalse((service / 'trakt_live/remote/profile_1.json').exists())
                activity['all'] = 'second'
                self.assertEqual(cycle.run_cycle(service, root, **args)['status'], 'queued')
                self.assertEqual(export.call_count, 2)
            self.assertEqual(legacy.read_bytes(), original)

    def test_replanning_deduplicates_pending_operations_and_preserves_legacy_batch(self):
        sys.path.insert(0, str(ROOT / 'addons/service.actweeter/resources'))
        from lib import trakt_auto_cycle as cycle
        from lib.trakt_live_queue import build_batch, write_batch
        from test_trakt_sync import sync, LATE
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            service = root / 'service'
            queue = service / 'trakt_live/queue'
            plan = {'profile': '1', 'account': 'user', 'items': [
                {'identity': sync.identity('movie', {'tmdb': '42'}),
                 'provider_id': '42', 'watched': True, 'watched_at': LATE}]}
            legacy = write_batch(queue, build_batch(plan, provider_scope='a'*64, consent=True))
            (service / 'trakt_live').chmod(0o700)
            original = legacy.read_bytes()
            export = Mock(return_value=root)
            args = dict(account='user', profile='1', provider_scope='a'*64,
                        activity_get=lambda: ('user', {'all': 'same'}),
                        export_snapshot=export, apply_batch=Mock(), addon=None,
                        history=None, one_shot=True)
            def prepare(*unused, **kw):
                return [build_batch(plan, provider_scope='a'*64, consent=True,
                                    activity_fingerprint=kw['activity_fingerprint'])]
            with patch.object(cycle, 'prepare_batches', side_effect=prepare):
                for _ in range(2):
                    self.assertEqual(cycle.run_cycle(service, root, **args)['status'], 'deferred')
            self.assertEqual(export.call_count, 1)
            self.assertEqual(list(queue.glob('*.json')), [legacy])
            self.assertEqual(legacy.read_bytes(), original)
            self.assertFalse((service / 'trakt_live/remote/profile_1.json').exists())
            self.assertTrue((service / 'trakt_live/planned/profile_1.json').exists())
            args['apply_batch'].assert_not_called()

    def test_empty_plan_is_checkpointed_without_claiming_pending_applied(self):
        sys.path.insert(0, str(ROOT / 'addons/service.actweeter/resources'))
        from lib import trakt_auto_cycle as cycle
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            export = Mock(return_value=root)
            args = dict(account='user', profile='1', provider_scope='a' * 64,
                        activity_get=lambda: ('user', {'all': 'same'}),
                        export_snapshot=export, apply_batch=Mock(),
                        addon=None, history=None, one_shot=True)
            with patch.object(cycle, 'prepare_batches', return_value=[]) as planner:
                for _ in range(3):
                    self.assertEqual(cycle.run_cycle(root / 'service', root, **args),
                                     {'status': 'unchanged'})
                self.assertEqual(export.call_count, 1)
                self.assertEqual(planner.call_count, 1)
            self.assertTrue((root / 'service/trakt_live/remote/profile_1.json').exists())
            args['apply_batch'].assert_not_called()


class AutoRouteRefreshTests(unittest.TestCase):
    def test_refresh_preserves_intermediate_writes_even_when_later_cycle_fails(self):
        sys.path.insert(0, str(ROOT / 'addons/service.actweeter/resources'))
        from lib import trakt_auto_cycle, trakt_sync_consent, trakt_sync_scheduler
        spec = importlib.util.spec_from_file_location('auto_routes_test',
            ROOT / 'third_party/xstream/trakt_auto_routes.py')
        route = importlib.util.module_from_spec(spec); spec.loader.exec_module(route)
        for final in ('deferred', 'pending', 'error', 'no_writes'):
            with self.subTest(final=final), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                xbmc = Mock(); xbmc.Player.return_value.isPlaying.return_value = False
                addon = Mock(); addon.getAddonInfo.return_value = str(root)
                context = lambda key: {'addon': addon, 'addon_handle': 1,
                                      '_new_listitem': Mock()}[key]
                consumer = types.SimpleNamespace(apply_batch=Mock(return_value={
                    'results': [{'status': 'deferred' if final == 'no_writes' else 'applied'}]}))
                calls = []
                def run(*args, **kwargs):
                    calls.append(1)
                    if len(calls) == 1:
                        kwargs['apply_batch']('fixture')
                        return {'status': 'pending'}
                    if final == 'error':
                        raise OSError('offline')
                    return {'status': 'deferred' if final == 'no_writes' else final}
                with patch.object(route, '_binding', return_value=('user', '1', 'a'*64, root)), \
                     patch.object(trakt_sync_consent, 'authorized', return_value=True), \
                     patch.object(trakt_sync_scheduler, 'record_result'), \
                     patch.object(trakt_auto_cycle, 'run_cycle', side_effect=run), \
                     patch.dict(sys.modules, {'history': types.ModuleType('history'),
                         'trakt_live_consumer': consumer,
                         'trakt_snapshot': types.ModuleType('trakt_snapshot'), 'xbmc': xbmc}):
                    vfs = Mock(); vfs.translatePath.side_effect = str
                    addons = Mock(); addons.Addon.return_value = addon
                    route.cycle_route(context, lambda **kw: True, Mock(), addons,
                                      xbmc, Mock(), vfs)
                self.assertEqual(xbmc.executebuiltin.call_count, 0 if final == 'no_writes' else 1)

if __name__ == '__main__':
    unittest.main()
