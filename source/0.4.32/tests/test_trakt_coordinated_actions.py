"""Synthetic manual actions: every XStream write is persisted before transport."""
import importlib.util
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'addons/service.actweeter/resources'))
spec = importlib.util.spec_from_file_location('coordinated_routes', ROOT / 'third_party/xstream/trakt_auto_routes.py')
routes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(routes)


class CoordinatedActionsTest(unittest.TestCase):
    def setUp(self):
        self.playing = [False]
        xbmc = types.SimpleNamespace(Player=lambda: types.SimpleNamespace(isPlaying=lambda: self.playing[0]))
        patcher = patch.dict(sys.modules, {'xbmc': xbmc})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_configured_collection_runtime_snapshot_is_atomic_and_not_reexported(self):
        from lib.collection_catalog import Catalog
        from lib.trakt_outbox import Outbox
        from lib.trakt_sync import IncompleteSnapshot
        binding = dict(account='synthetic', profile='1', provider_scope='a'*64,
                       kodi_profile='b'*64, generation='c'*64)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            catalog = Catalog(root / 'collections_catalog.db')
            identifier = catalog.create_local('Movies', kind='movie', origin='mis_colecciones')
            catalog.configure_destination(identifier, scope=binding, destination='watchlist',
                                          verified=True, confirmed=True)
            rows = [{'movie': {'title': 'Example', 'ids': {'tmdb': 42}}}]
            truncated = [False]
            paths = []
            def request(path, query):
                paths.append(path)
                if path == '/sync/last_activities':
                    return {'all': '2026-10-29T10:00:00Z'}, None
                self.assertEqual(path, '/sync/watchlist/movies')
                return list(rows), dict(page=1, page_count=1, limit=100,
                                       item_count=len(rows) + int(truncated[0]))
            trakt = types.SimpleNamespace(snapshot_request=request)
            def sync():
                routes.sync_configured_collections(None, trakt, None, None,
                    account='synthetic', profile='1', scope='a'*64, root=root)
            with patch('lib.collection_catalog._runtime_scope', return_value=binding), \
                 patch.object(routes, '_binding', return_value=('synthetic','1','a'*64,root)):
                sync()
                self.assertEqual([item['tmdb_id'] for item in catalog.members(identifier)], [42])
                # An interrupted/truncated snapshot must not delete the imported member.
                rows.clear(); truncated[0] = True
                with self.assertRaises(IncompleteSnapshot):
                    sync()
                self.assertEqual(len(catalog.members(identifier)), 1)
                truncated[0] = False
                rows.append({})
                with self.assertRaises(ValueError):
                    sync()
                self.assertEqual(len(catalog.members(identifier)), 1)
                rows.clear()
                # Local explicit removal wins over a later remote snapshot until confirmed.
                catalog.remove_member(identifier, kind='movie', tmdb_id=42, scope=binding)
                rows.append({'movie': {'title': 'Example', 'ids': {'tmdb': 42}}})
                sync()
                self.assertEqual(catalog.members(identifier), [])
                queue = Outbox(root / 'outbox.sqlite')
                catalog.handoff_changes(queue)
                import json
                with queue.connect() as db:
                    events = [json.loads(row[0]) for row in db.execute('SELECT event FROM events')]
                exported = [event for event in events if event.get('schema') == 2]
                self.assertEqual([event['operation'] for event in exported], ['watchlist.remove'])
                # A complete empty response removes only previously imported members.
                rows[:] = [{'movie': {'title': 'Other', 'ids': {'tmdb': 43}}}]
                sync()
                catalog.add_member(identifier, kind='movie', tmdb_id=99, title='Local', scope=binding)
                rows.clear(); sync()
                self.assertEqual([item['tmdb_id'] for item in catalog.members(identifier)], [99])
            self.assertNotIn('/sync/watchlist/shows', paths)

    def test_collection_confirmation_releases_only_snapshot_verified_intent(self):
        from lib.collection_catalog import Catalog
        from lib.trakt_outbox import Outbox
        binding = dict(account='synthetic', profile='1', provider_scope='a'*64,
                       kodi_profile='b'*64, generation='c'*64)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            catalog = Catalog(root / 'collections.db')
            identifier = catalog.create_local('Movies', kind='movie', origin='mis_colecciones')
            mapping = catalog.configure_destination(identifier, scope=binding, destination='watchlist',
                                                    verified=True, confirmed=True)
            catalog.add_member(identifier, kind='movie', tmdb_id=42, title='Example', scope=binding)
            queue = Outbox(root / 'outbox.sqlite')
            catalog.handoff_changes(queue)
            self.assertEqual(catalog.confirmed_changes(queue), set())
            with queue.connect() as db:
                operation = db.execute("SELECT id FROM events WHERE state='held'").fetchone()[0]
            self.assertEqual(queue.send_manual(operation, account='synthetic', profile='1',
                provider_scope='a'*64, approved=operation, now=1,
                post=lambda *_: {'added': {'movies': 1}, 'not_found': {}}), 'confirmed')
            confirmed = catalog.confirmed_changes(queue)
            self.assertEqual(len(confirmed), 1)
            def apply(items, timestamp):
                return catalog.apply_remote(identifier, scope=binding, revision=mapping['revision'],
                    items=items, observed_at=timestamp, complete=True, confirmed=confirmed)
            # Confirmed POST without matching read still protects the local addition.
            apply([], 10)
            self.assertEqual(len(catalog.members(identifier)), 1)
            apply([dict(kind='movie',tmdb_id=42,title='Example')], 11)
            self.assertEqual(catalog.confirmed_changes(queue), set())
            # A subsequent complete remote removal now propagates normally.
            self.assertEqual(apply([], 12)['removed'], 1)
            self.assertEqual(catalog.members(identifier), [])

    def test_scheduler_recovers_native_journal_handoff_after_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'trakt_local_changes.sqlite').touch()
            (root/'favorites_1.json').write_text('{}')
            (root/'favorites_2.json').write_text('{}')
            recovered=[]
            addon=types.SimpleNamespace(getAddonInfo=lambda _:folder)
            addons=types.SimpleNamespace(Addon=lambda *_:addon)
            vfs=types.SimpleNamespace(translatePath=lambda value:value)
            journal=types.SimpleNamespace(runtime_handoff=lambda path:recovered.append(path.name))
            player=types.SimpleNamespace(isPlaying=lambda:False)
            with patch.dict(sys.modules,{'trakt_local_journal':journal}):
                routes.retry_due_manual_actions(lambda _:addon, None, addons, vfs,
                    account='synthetic',profile='1',scope='a'*64,root=root,player=player)
            self.assertEqual(recovered,['favorites_1.json'])

    def test_explicit_actions_share_durable_queue_and_typed_endpoints(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            addon = types.SimpleNamespace(Addon=lambda *_: types.SimpleNamespace(getAddonInfo=lambda _: folder))
            vfs = types.SimpleNamespace(translatePath=lambda x: x)
            posted = []
            def post(path, payload, auth):
                db = sqlite3.connect(root / 'trakt_explicit_outbox.sqlite')
                states = db.execute('select state from events order by rowid').fetchall()
                db.close()
                self.assertEqual(states[-1], ('inflight',))
                posted.append((path, payload))
                if path == '/checkin': return {'id': 5}
                field = 'deleted' if path.endswith('/remove') else 'added'
                return {field: {'movies': 1}, 'not_found': {}}
            trakt = types.SimpleNamespace(post=post)
            binding = ('synthetic', '1', 'a' * 64, root)
            with patch.dict(sys.modules, {'xbmcaddon': addon, 'xbmcvfs': vfs}), \
                 patch.object(routes, '_binding', return_value=binding):
                for kind, action in [('mark_watched', None), ('mark_unwatched', None),
                                     ('watchlist', 'add'), ('collection', 'remove'), ('checkin', None)]:
                    self.assertEqual(routes.coordinated_manual_action(lambda _: None, trakt,
                        'movie', '42', '', '', kind, action), 'confirmed')
            self.assertEqual([p[0] for p in posted], ['/sync/history', '/sync/history/remove',
                '/sync/watchlist', '/sync/collection/remove', '/checkin'])

    def test_disconnect_before_post_stays_pending_for_safe_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            addon = types.SimpleNamespace(Addon=lambda *_: types.SimpleNamespace(getAddonInfo=lambda _: folder))
            vfs = types.SimpleNamespace(translatePath=lambda x: x)
            calls = []
            trakt = types.SimpleNamespace(post=lambda *args, **kwargs: calls.append(args))
            with patch.dict(sys.modules, {'xbmcaddon': addon, 'xbmcvfs': vfs}), \
                 patch.object(routes, '_binding', side_effect=[('a', '1', 'a' * 64, root), OSError('offline')]):
                state = routes.coordinated_manual_action(lambda _: None, trakt,
                    'movie', '42', '', '', 'watchlist', 'add')
            self.assertEqual(state, 'pending')
            self.assertFalse(calls)
            db = sqlite3.connect(root / 'trakt_explicit_outbox.sqlite')
            state, retry_at = db.execute('select state,retry_at from events').fetchone()
            db.close()
            self.assertEqual(state, 'pending')
            self.assertGreater(retry_at, 0)

    def test_changed_account_is_never_posted(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            addon = types.SimpleNamespace(Addon=lambda *_: types.SimpleNamespace(getAddonInfo=lambda _: folder))
            vfs = types.SimpleNamespace(translatePath=lambda x: x)
            calls = []
            trakt = types.SimpleNamespace(post=lambda *args, **kw: calls.append(args))
            with patch.dict(sys.modules, {'xbmcaddon': addon, 'xbmcvfs': vfs}), \
                 patch.object(routes, '_binding', side_effect=[('a', '1', 'a' * 64, root), ('b', '1', 'a' * 64, root)]):
                self.assertEqual(routes.coordinated_manual_action(lambda _: None, trakt,
                    'movie', '42', '', '', 'mark_watched', None), 'unknown')
            self.assertFalse(calls)

    def test_rate_limit_remains_pending_with_retry_deadline(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            addon = types.SimpleNamespace(Addon=lambda *_: types.SimpleNamespace(getAddonInfo=lambda _: folder))
            vfs = types.SimpleNamespace(translatePath=lambda x: x)
            def limited(*_args, **_kwargs):
                raise RuntimeError('Trakt rate limited. Try again later.')
            trakt = types.SimpleNamespace(post=limited)
            with patch.dict(sys.modules, {'xbmcaddon': addon, 'xbmcvfs': vfs}), \
                 patch.object(routes, '_binding', return_value=('a', '1', 'a' * 64, root)):
                self.assertEqual(routes.coordinated_manual_action(lambda _: None, trakt,
                    'movie', '42', '', '', 'mark_watched', None), 'pending')
            db = sqlite3.connect(root / 'trakt_explicit_outbox.sqlite')
            state, retry_at = db.execute('select state,retry_at from events').fetchone()
            db.close()
            self.assertEqual(state, 'pending')
            self.assertGreater(retry_at, 0)

    def test_offline_verified_binding_stages_without_posting(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            addon = types.SimpleNamespace(Addon=lambda *_: types.SimpleNamespace(getAddonInfo=lambda _: folder))
            vfs = types.SimpleNamespace(translatePath=lambda x: x)
            calls = []
            trakt = types.SimpleNamespace(post=lambda *args, **kw: calls.append(args))
            with patch.dict(sys.modules, {'xbmcaddon': addon, 'xbmcvfs': vfs}), \
                 patch.object(routes, '_binding', side_effect=OSError('offline')), \
                 patch.object(routes, '_offline_binding', return_value=('a', '1', 'a' * 64, root)):
                self.assertEqual(routes.coordinated_manual_action(lambda _: None, trakt,
                    'movie', '42', '', '', 'watchlist', 'add'), 'pending')
            self.assertFalse(calls)
            db = sqlite3.connect(root / 'trakt_explicit_outbox.sqlite')
            self.assertEqual(db.execute('select state from events').fetchone(), ('pending',))
            db.close()

    def test_retry_requires_confirmation_and_sends_only_pending_action(self):
        from lib.trakt_outbox import Outbox, manual_event
        from lib.trakt_sync import identity
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            queue = Outbox(root / 'trakt_explicit_outbox.sqlite')
            event = manual_event('a', '1', 'watchlist.add', identity('movie', {'tmdb': 42}), 'a' * 32, provider_scope='a' * 64)
            identifier = queue.enqueue_manual(event)
            addon = types.SimpleNamespace(Addon=lambda *_: types.SimpleNamespace(getAddonInfo=lambda _: folder))
            vfs = types.SimpleNamespace(translatePath=lambda x: x)
            accepted = [False]
            gui = types.SimpleNamespace(Dialog=lambda: types.SimpleNamespace(yesno=lambda *_: accepted[0]))
            plugin = types.SimpleNamespace(addDirectoryItem=lambda *_a, **_kw: None,
                                           endOfDirectory=lambda *_a, **_kw: None)
            sent = []
            trakt = types.SimpleNamespace(authorized=lambda: True,
                post=lambda path, payload, auth: sent.append(path) or {'added': {'movies': 1}})
            context = lambda key: (lambda label: label) if key == '_new_listitem' else 1
            with patch.object(routes, '_binding', return_value=('a', '1', 'a' * 64, root)):
                args = (context, lambda **_: True, trakt, addon, gui, plugin, vfs, {'operation': identifier})
                routes.retry_manual_route(*args)
                self.assertEqual(queue.status(identifier)['state'], 'pending')
                accepted[0] = True
                routes.retry_manual_route(*args)
                routes.retry_manual_route(*args)
            self.assertEqual(sent, ['/sync/watchlist'])
            self.assertEqual(queue.status(identifier)['state'], 'confirmed')

    def test_held_export_requires_separate_confirmation(self):
        from lib.trakt_outbox import Outbox, manual_event
        from lib.trakt_sync import identity
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            queue = Outbox(root / 'trakt_explicit_outbox.sqlite')
            event = manual_event('a', '1', 'watchlist.add', identity('movie', {'tmdb': 42}), 'a' * 32, provider_scope='a' * 64)
            identifier = queue.enqueue_manual(event, held=True)
            addon = types.SimpleNamespace(Addon=lambda *_: types.SimpleNamespace(getAddonInfo=lambda _: folder))
            vfs = types.SimpleNamespace(translatePath=lambda x: x)
            accepted = [False]
            gui = types.SimpleNamespace(Dialog=lambda: types.SimpleNamespace(yesno=lambda *_: accepted[0]))
            plugin = types.SimpleNamespace(addDirectoryItem=lambda *_a, **_kw: None,
                                           endOfDirectory=lambda *_a, **_kw: None)
            sent = []
            trakt = types.SimpleNamespace(authorized=lambda: True,
                post=lambda path, payload, auth: sent.append(path) or {'added': {'movies': 1}})
            context = lambda key: (lambda label: label) if key == '_new_listitem' else 1
            with patch.object(routes, '_binding', return_value=('a', '1', 'a' * 64, root)):
                args = (context, lambda **_: True, trakt, addon, gui, plugin, vfs, {'operation': identifier})
                routes.retry_manual_route(*args)
                self.assertEqual(queue.status(identifier)['state'], 'held')
                accepted[0] = True
                routes.retry_manual_route(*args)
                routes.retry_manual_route(*args)
            self.assertEqual(sent, ['/sync/watchlist'])
            self.assertEqual(queue.status(identifier)['state'], 'confirmed')

    def test_scheduled_disconnect_before_post_remains_pending(self):
        from lib.trakt_outbox import Outbox, manual_event
        from lib.trakt_sync import identity
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); queue = Outbox(root / 'trakt_explicit_outbox.sqlite')
            operation = queue.enqueue_manual(manual_event('a', '1', 'watchlist.add',
                identity('movie', {'tmdb': 42}), 'd' * 32, provider_scope='a' * 64))
            addon = types.SimpleNamespace(Addon=lambda *_: types.SimpleNamespace(getAddonInfo=lambda _: folder))
            vfs = types.SimpleNamespace(translatePath=lambda x: x)
            player = types.SimpleNamespace(isPlaying=lambda: False)
            sent = []
            trakt = types.SimpleNamespace(post=lambda *args, **kwargs: sent.append(args))
            with patch.object(routes, '_binding', side_effect=OSError('offline')):
                result = routes.retry_due_manual_actions(lambda _: None, trakt, addon, vfs,
                    account='a', profile='1', scope='a' * 64, root=root, player=player)
            self.assertEqual(result, ['pending'])
            self.assertFalse(sent)
            self.assertEqual(queue.status(operation)['state'], 'pending')

    def test_automatic_retry_sends_only_due_explicit_action_for_matching_scope(self):
        from lib.trakt_outbox import Outbox, manual_event
        from lib.trakt_sync import identity
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); queue = Outbox(root / 'trakt_explicit_outbox.sqlite')
            movie = identity('movie', {'tmdb': 42})
            chosen = queue.enqueue_manual(manual_event('a', '1', 'watchlist.add', movie,
                'a' * 32, provider_scope='a' * 64))
            queue.enqueue_manual(manual_event('a', '1', 'checkin', movie,
                'b' * 32, provider_scope='a' * 64))
            queue.enqueue_manual(manual_event('a', '1', 'collection.add', movie,
                'c' * 32, provider_scope='b' * 64))
            addon = types.SimpleNamespace(Addon=lambda *_: types.SimpleNamespace(getAddonInfo=lambda _: folder))
            vfs = types.SimpleNamespace(translatePath=lambda x: x)
            player = types.SimpleNamespace(isPlaying=lambda: False)
            sent = []
            trakt = types.SimpleNamespace(post=lambda path, payload, auth:
                sent.append(path) or {'added': {'movies': 1}})
            with patch.object(routes, '_binding', return_value=('a', '1', 'a' * 64, root)):
                outcomes = routes.retry_due_manual_actions(lambda _: None, trakt, addon, vfs,
                    account='a', profile='1', scope='a' * 64, root=root, player=player)
            self.assertEqual(outcomes, ['confirmed'])
            self.assertEqual(sent, ['/sync/watchlist'])
            self.assertEqual(queue.status(chosen)['state'], 'confirmed')

    def test_playback_defers_watched_and_blocks_checkin(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            addon = types.SimpleNamespace(Addon=lambda *_: types.SimpleNamespace(getAddonInfo=lambda _: folder))
            vfs = types.SimpleNamespace(translatePath=lambda x: x)
            calls = []
            trakt = types.SimpleNamespace(post=lambda *args, **kw: calls.append(args))
            self.playing[0] = True
            with patch.dict(sys.modules, {'xbmcaddon': addon, 'xbmcvfs': vfs}), \
                 patch.object(routes, '_binding', return_value=('a', '1', 'a' * 64, root)):
                self.assertEqual(routes.coordinated_manual_action(lambda _: None, trakt,
                    'movie', '42', '', '', 'mark_watched', None), 'pending')
                self.assertEqual(routes.coordinated_manual_action(lambda _: None, trakt,
                    'movie', '42', '', '', 'checkin', None), 'blocked_playback')
            self.assertFalse(calls)
            db = sqlite3.connect(root / 'trakt_explicit_outbox.sqlite')
            self.assertEqual(db.execute('select state from events').fetchall(), [('pending',)])
            db.close()

    def test_ambiguous_checkin_has_no_network_send(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            addon = types.SimpleNamespace(Addon=lambda *_: types.SimpleNamespace(getAddonInfo=lambda _: folder))
            vfs = types.SimpleNamespace(translatePath=lambda x: x)
            calls = []
            trakt = types.SimpleNamespace(post=lambda *args, **kw: calls.append(args))
            with patch.dict(sys.modules, {'xbmcaddon': addon, 'xbmcvfs': vfs}), \
                 patch.object(routes, '_binding', return_value=('a', '1', 'a' * 64, root)):
                with self.assertRaises(ValueError):
                    routes.coordinated_manual_action(lambda _: None, trakt, 'tv', '42', '', '', 'checkin', None)
            self.assertFalse(calls)


    def test_held_export_requires_scoped_consent_and_rechecks_revocation(self):
        from lib.trakt_outbox import Outbox, manual_event
        from lib.trakt_sync import identity
        from lib.trakt_sync_consent import grant, revoke
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); queue = Outbox(root / 'trakt_explicit_outbox.sqlite')
            operation = queue.enqueue_manual(manual_event('a', '1', 'watchlist.add',
                identity('movie', {'tmdb': 42}), 'e'*32, provider_scope='a'*64), held=True)
            addon = types.SimpleNamespace(Addon=lambda *_: types.SimpleNamespace(getAddonInfo=lambda _: folder))
            vfs = types.SimpleNamespace(translatePath=lambda value: value)
            player = types.SimpleNamespace(isPlaying=lambda: False)
            calls = []
            trakt = types.SimpleNamespace(post=lambda *a, **kw: calls.append(a) or {'added': {'movies': 1}})
            def run():
                return routes.retry_due_manual_actions(lambda _: None, trakt, addon, vfs,
                    account='a', profile='1', scope='a'*64, root=root, player=player)
            self.assertEqual(run(), [])
            consent = root/'trakt_live'/'export_consent.json'
            grant(consent, account='a', profile='1', provider_scope='a'*64)
            def revoked(*args):
                revoke(consent)
                return 'a', '1', 'a'*64, root
            with patch.object(routes, '_binding', side_effect=revoked):
                self.assertEqual(run(), ['held'])
            self.assertFalse(calls)
            self.assertEqual(queue.status(operation)['state'], 'held')
            grant(consent, account='a', profile='1', provider_scope='a'*64)
            with queue.connect() as db:
                db.execute('UPDATE events SET retry_at=0')
            with patch.object(routes, '_binding', return_value=('a', '1', 'a'*64, root)):
                self.assertEqual(run(), ['confirmed'])
            self.assertEqual(len(calls), 1)
