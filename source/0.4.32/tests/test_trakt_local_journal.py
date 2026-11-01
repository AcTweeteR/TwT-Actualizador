"""Synthetic XStream journal; no provider URLs or remote network."""
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'third_party/xstream'))
import trakt_local_journal as journal


class LocalJournalTests(unittest.TestCase):
    def test_prepare_captures_native_destination_and_external_identity_at_write_time(self):
        import types
        from unittest.mock import patch
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/service.actweeter/resources'))
        from lib.collection_catalog import Catalog
        from lib.trakt_outbox import Outbox
        scope=dict(account='synthetic',profile='1',provider_scope='a'*64,kodi_profile='b'*64,generation='c'*64)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            catalog=Catalog(root/'collections_catalog.db')
            local=catalog.create_local('Native movies',kind='movie',origin='mis_colecciones')
            catalog.configure_destination(local,scope=scope,destination='watchlist',verified=True,confirmed=True)
            with catalog._db() as db:
                mappings=json.loads(db.execute('SELECT mappings FROM lists WHERE local_id=?',(local,)).fetchone()[0])
                mappings['xstream_source']=dict(folder_sha256=journal._hash('Favorites'),media_type='movie')
                db.execute('UPDATE lists SET mappings=? WHERE local_id=?',(json.dumps(mappings),local))
            addon=types.SimpleNamespace(getAddonInfo=lambda key: str(root) if key=='profile' else str(Path(__file__).resolve().parents[1]/'addons/service.actweeter'))
            modules={
                'xbmcaddon':types.SimpleNamespace(Addon=lambda *_: addon),
                'xbmcvfs':types.SimpleNamespace(translatePath=lambda value:value),
                'trakt_live_consumer':types.SimpleNamespace(_catalog_scope_verified=lambda *a:True),
                'trakt_provider_index':types.SimpleNamespace(verified_vod_records=lambda *a,**kw:[dict(provider_id='7',ids={'tmdb':42})]),
                'trakt_series_index':types.SimpleNamespace(verified_show_records=lambda *a,**kw:[])}
            store=root/'favorites_1.json'
            with patch.dict(sys.modules,modules),journal.verified_scope(**scope):
                ticket=journal.prepare(store,'Favorites',{'Favorites':[]},{'Favorites':[{'id':'7','stype':'movie'}]})
                journal.finish(ticket)
            queue=Outbox(root/'outbox.sqlite')
            self.assertEqual(journal.deliver(store,queue,scope=scope),1)
            with queue.connect() as db:
                raw,state=db.execute('SELECT event,state FROM events').fetchone()
            event=json.loads(raw)
            self.assertEqual(event['operation'],'watchlist.add')
            self.assertEqual(event['identity']['ids']['tmdb'],'42')
            self.assertEqual(state,'held')

    def test_captured_native_destinations_handoff_is_idempotent_and_scoped(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/service.actweeter/resources'))
        from lib.trakt_outbox import Outbox
        scope = dict(account='synthetic', profile='1', provider_scope='a'*64,
                     kodi_profile='b'*64, generation='c'*64)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = root / 'favorites_1.json'
            database, _ = journal._database(store)
            queue = Outbox(root / 'outbox.sqlite')
            with sqlite3.connect(database) as db:
                db.execute('CREATE TABLE changes (id TEXT PRIMARY KEY,event TEXT,state TEXT)')
                for collection in ('favorites', 'pending'):
                    for media, kind in (('movie','movie'), ('series','show')):
                        for action in ('add','remove'):
                            identifier = collection + media + action
                            event = dict(kind='Favorites',scope=scope,origin='local',changes=[dict(
                                media_type=media,change=action,
                                external_identity=dict(kind=kind,ids=dict(tmdb=42)),
                                destination_capture=dict(scope=scope,destination='list.123' if collection=='favorites' else 'watchlist'))])
                            db.execute('INSERT INTO changes VALUES (?,?,?)',(identifier,json.dumps(event),'ready'))
            self.assertEqual(journal.deliver(store,queue,scope=dict(scope,account='other')),0)
            self.assertEqual(journal.deliver(store,queue,scope=scope),8)
            self.assertEqual(journal.deliver(store,queue,scope=scope),0)
            with queue.connect() as db:
                rows=db.execute('SELECT event,state FROM events').fetchall()
            self.assertEqual(len(rows),8)
            self.assertTrue(all(state=='held' for _,state in rows))
            self.assertEqual({json.loads(raw)['operation'] for raw,_ in rows},
                             {'list.123.add','list.123.remove','watchlist.add','watchlist.remove'})

    def test_runtime_handoff_recovers_committed_prepared_write(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            store = Path(folder) / 'favorites_1.json'
            before={'Favorites': []}
            after={'Favorites': [{'id':'7','stype':'movie'}]}
            ticket=journal.prepare(store,'Favorites',before,after)
            store.write_text(json.dumps(after))
            journal.runtime_handoff(store)
            with sqlite3.connect(ticket[0]) as db:
                self.assertEqual(db.execute('SELECT state FROM changes WHERE id=?',(ticket[1],)).fetchone(),('quarantined',))

    def test_records_local_and_remote_without_private_urls(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            watched = root / 'watched_movies_p2.json'
            first = journal.prepare(watched, 'WatchedMovies', {}, {'42': True})
            journal.finish(first)
            resume = root / 'resume_points_p2.json'
            with journal.remote_changes():
                second = journal.prepare(resume, 'ResumePoints', {},
                    {'name||https://secret.invalid/user/password/42.mp4':
                     {'position': 100, 'duration': 1000, 'timestamp': 123}})
                journal.finish(second)
            db = sqlite3.connect(root / 'trakt_local_changes.sqlite')
            rows = db.execute('select event,state from changes order by rowid').fetchall(); db.close()
            self.assertEqual([json.loads(row[0])['origin'] for row in rows], ['local', 'trakt_import'])
            self.assertEqual([row[1] for row in rows], ['quarantined', 'observed'])
            self.assertNotIn('secret.invalid', str(rows))
            self.assertNotIn('password', str(rows))
            self.assertEqual(json.loads(rows[0][0])['changes'][0]['identity'], '42')

    def test_unfinished_write_remains_prepared_after_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            ticket = journal.prepare(root / 'watched_movies_p1.json', 'WatchedMovies', {}, {'42': True})
            db = sqlite3.connect(root / 'trakt_local_changes.sqlite')
            self.assertEqual(db.execute('select state from changes where id=?', (ticket[1],)).fetchone(), ('prepared',))
            db.close()
            journal.finish(ticket)
            db = sqlite3.connect(root / 'trakt_local_changes.sqlite')
            self.assertEqual(db.execute('select state from changes where id=?', (ticket[1],)).fetchone(), ('quarantined',))
            db.close()

    def test_symlink_journal_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); other = root / 'other'; other.write_text('unchanged')
            (root / 'trakt_local_changes.sqlite').symlink_to(other)
            with self.assertRaises(ValueError):
                journal.prepare(root / 'watched_movies_p1.json', 'WatchedMovies', {}, {'42': True})
            self.assertEqual(other.read_text(), 'unchanged')

    def test_recovery_records_only_matching_written_state_and_quarantines_others(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = root / 'watched_movies_p1.json'
            applied = journal.prepare(store, 'WatchedMovies', {}, {'42': True})
            journal.recover(store, {'42': True})
            pending = journal.prepare(store, 'WatchedMovies', {'42': True}, {'43': True})
            journal.recover(store, {'42': True})
            with sqlite3.connect(root / 'trakt_local_changes.sqlite') as db:
                states = dict(db.execute('select id,state from changes'))
            self.assertEqual(states[applied[1]], 'quarantined')
            self.assertEqual(states[pending[1]], 'quarantined')
            journal.recover(store, {'43': True})
            with sqlite3.connect(root / 'trakt_local_changes.sqlite') as db:
                self.assertEqual(db.execute('select state from changes where id=?', (pending[1],)).fetchone(), ('quarantined',))


    def test_scoped_capture_handoff_and_crash_retry_are_idempotent(self):
        from unittest.mock import patch
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/service.actweeter/resources'))
        from lib.trakt_outbox import Outbox
        with tempfile.TemporaryDirectory() as folder:
            store = Path(folder) / 'watched_movies_p1.json'
            scope = dict(account='test', profile='1', provider_scope='a'*64,
                         kodi_profile='b'*64, generation='c'*64)
            outbox = Outbox(Path(folder) / 'outbox.sqlite')
            with journal.verified_scope(**scope):
                journal.finish(journal.prepare(store, 'WatchedMovies', {}, {'tmdb:movie:198184': True}))
            self.assertEqual(journal.deliver(store, outbox, scope=dict(scope, account='other')), 0)
            enqueue = outbox.enqueue_manual
            def interrupted(event, **kwargs):
                enqueue(event, **kwargs)
                raise OSError('crash after durable enqueue')
            with patch.object(outbox, 'enqueue_manual', side_effect=interrupted):
                with self.assertRaises(OSError):
                    journal.deliver(store, outbox, scope=scope)
            self.assertEqual(journal.deliver(store, outbox, scope=scope), 1)
            self.assertEqual(journal.deliver(store, outbox, scope=scope), 0)
            with outbox.connect() as db:
                rows = db.execute('SELECT id,event FROM events').fetchall()
            self.assertEqual(len(rows), 1)
            operation = rows[0][0]
            self.assertEqual(outbox.status(operation)['state'], 'held')
            self.assertEqual(outbox.pending_manual(account='test', profile='1', provider_scope='a'*64, now=9999999999), [])
            result = outbox.send_manual(operation, account='test', profile='1', provider_scope='a'*64,
                approved=operation, post=lambda path, payload: {'added': {'movies': 1}}, now=1)
            self.assertEqual(result, 'confirmed')
            with sqlite3.connect(Path(folder) / 'trakt_local_changes.sqlite') as db:
                raw, state = db.execute('SELECT event,state FROM changes').fetchone()
            self.assertEqual(state, 'queued')
            self.assertEqual(json.loads(raw)['outbox_ids'], [operation])

    def test_scoped_import_and_ambiguous_ids_never_enter_outbox(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/service.actweeter/resources'))
        from lib.trakt_outbox import Outbox
        with tempfile.TemporaryDirectory() as folder:
            store = Path(folder) / 'watched_movies_p1.json'
            scope = dict(account='test', profile='1', provider_scope='a'*64,
                         kodi_profile='b'*64, generation='c'*64)
            outbox = Outbox(Path(folder) / 'outbox.sqlite')
            with journal.verified_scope(**scope):
                journal.finish(journal.prepare(store, 'WatchedMovies', {}, {'42': True}))
                with journal.remote_changes():
                    journal.finish(journal.prepare(store, 'WatchedMovies', {}, {'tmdb:movie:198184': True}))
            self.assertEqual(journal.deliver(store, outbox, scope=scope), 0)
            with outbox.connect() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM events').fetchone()[0], 0)


    def test_runtime_binding_invalidates_on_account_credentials_and_provider_change(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = root / 'watched_movies_p1.json'
            addon = SimpleNamespace(getAddonInfo=lambda name: str(root))
            vfs = SimpleNamespace(translatePath=lambda path: path)
            tokens = {'access_token': 'synthetic-private-token'}
            manager = SimpleNamespace(active=1, get_credentials=lambda: {})
            provider = ['a'*64]
            modules = dict(xbmcaddon=SimpleNamespace(Addon=lambda name: addon), xbmcvfs=vfs,
                trakt=SimpleNamespace(_read_tokens=lambda: dict(tokens)),
                profiles=SimpleNamespace(ProfileManager=lambda addon: manager),
                trakt_live_queue=SimpleNamespace(provider_fingerprint=lambda *args: provider[0]))
            journal.remember_binding(addon, 'account', '1', provider[0], tokens, vfs)
            self.assertNotIn(tokens['access_token'], (root/'trakt_capture_binding.json').read_text())
            with patch.dict(sys.modules, modules):
                for expected in ('ready', 'quarantined', 'quarantined'):
                    with journal.runtime_scope(store):
                        ticket = journal.prepare(store, 'WatchedMovies', {}, {'tmdb:movie:198184': True})
                    journal.finish(ticket)
                    with sqlite3.connect(ticket[0]) as db:
                        self.assertEqual(db.execute('SELECT state FROM changes WHERE id=?', (ticket[1],)).fetchone()[0], expected)
                    if expected == 'ready':
                        tokens['access_token'] = 'different-account-token'
                    else:
                        tokens['access_token'] = 'synthetic-private-token'
                        provider[0] = 'd'*64


    def test_verified_episode_add_remove_reaches_existing_queue(self):
        from unittest.mock import patch
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/service.actweeter/resources'))
        from lib.trakt_outbox import Outbox
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); store = root / 'watched_episodes_p1.json'
            scope = dict(account='test', profile='1', provider_scope='a'*64,
                         kodi_profile='b'*64, generation='c'*64)
            content = dict(kind='episode', ids={'tmdb': 1399}, season=2, episode=3)
            outbox = Outbox(root / 'outbox.sqlite')
            with patch.object(journal, '_episode_identity', return_value=content), journal.verified_scope(**scope):
                journal.finish(journal.prepare(store, 'WatchedEpisodes', {}, {'77': {'2': ['990']}}))
                journal.finish(journal.prepare(store, 'WatchedEpisodes', {'77': {'2': ['990']}}, {}))
            self.assertEqual(journal.deliver(store, outbox, scope=scope), 2)
            with outbox.connect() as db:
                rows = [(json.loads(raw), state) for raw, state in db.execute('SELECT event,state FROM events ORDER BY rowid')]
            self.assertEqual([e['operation'] for e, _ in rows], ['history.add', 'history.remove'])
            self.assertTrue(all(state == 'held' for _, state in rows))
            for event, _ in rows:
                self.assertEqual(event['identity']['ids'], {'tmdb': '1399'})
                self.assertEqual(event['identity']['episode'], 3)
                self.assertEqual(event['payload']['shows'][0]['seasons'][0]['episodes'][0]['number'], 3)


    def test_resume_consolidation_preserves_evidence_and_rejects_stale_advance(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Path(folder)/'resume_points_p1.json'
            scope = dict(account='a', profile='1', provider_scope='a'*64,
                         kodi_profile='b'*64, generation='c'*64)
            ids = []
            with journal.verified_scope(**scope):
                for stamp, position in [(100, 100), (200, 200), (150, 150)]:
                    ticket = journal.prepare(store, 'ResumePoints', {},
                        {'private-playback-key': dict(timestamp=stamp, position=position, duration=1000)})
                    journal.finish(ticket); ids.append(ticket[1])
            with sqlite3.connect(Path(folder)/'trakt_local_changes.sqlite') as db:
                rows = {key:(json.loads(raw), state) for key,raw,state in db.execute('SELECT id,event,state FROM changes')}
            self.assertEqual([rows[key][1] for key in ids], ['superseded', 'ready', 'superseded'])
            self.assertEqual(rows[ids[1]][0]['changes'][0]['percent'], 20)
            self.assertEqual(rows[ids[0]][0]['superseded_by'], ids[1])
            self.assertNotIn('private-playback-key', str(rows))


    def test_resume_and_collection_receipts_are_durable_never_sendable(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/service.actweeter/resources'))
        from lib.trakt_outbox import Outbox
        from lib.collection_catalog import Catalog
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); queue = Outbox(root/'outbox.sqlite')
            scope = dict(account='a', profile='1', provider_scope='a'*64,
                         kodi_profile='b'*64, generation='c'*64)
            store = root/'resume_points_p1.json'
            with journal.verified_scope(**scope):
                journal.finish(journal.prepare(store, 'ResumePoints', {},
                    {'secret-url': dict(position=120, duration=1000, timestamp=123)}))
            self.assertEqual(journal.deliver(store, queue, scope=scope), 1)
            self.assertEqual(journal.deliver(store, queue, scope=scope), 0)
            catalog = Catalog(root/'collections.db')
            identifier = catalog.create_local('private list', origin='mis_colecciones')
            catalog.add_member(identifier, kind='movie', tmdb_id=42, title='private title')
            catalog.handoff_changes(queue)
            catalog.handoff_changes(queue)
            with queue.connect() as db:
                rows = db.execute('SELECT event,state FROM events').fetchall()
            self.assertEqual(len(rows), 3)
            self.assertTrue(all(state == 'retained' for _,state in rows))
            self.assertNotIn('secret-url', str(rows))
            self.assertNotIn('private title', str(rows))
            self.assertEqual(queue.pending_manual(account='a', profile='1', provider_scope='a'*64,
                now=9999999999, include_held=True), [])


    def test_collection_mapping_captures_destination_without_rebinding_history(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/service.actweeter/resources'))
        from lib.collection_catalog import Catalog
        from lib.trakt_outbox import Outbox
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); catalog=Catalog(root/'collections.db'); queue=Outbox(root/'queue.sqlite')
            scope=dict(account='a',profile='1',provider_scope='a'*64,kodi_profile='b'*64,generation='c'*64)
            identifier=catalog.create_local('Local',origin='mis_colecciones')
            catalog.add_member(identifier,kind='movie',tmdb_id=1,title='Historical')
            catalog.configure_destination(identifier,scope=scope,destination='watchlist',verified=True,confirmed=True)
            catalog.add_member(identifier,kind='movie',tmdb_id=2,title='New',scope=scope)
            catalog.remove_member(identifier,kind='movie',tmdb_id=2,scope=scope)
            catalog.add_member(identifier,kind='movie',tmdb_id=3,title='Imported',origin='trakt_import',scope=scope)
            catalog.add_member(identifier,kind='movie',tmdb_id=4,title='Other account',scope=dict(scope,account='other'))
            catalog.configure_destination(identifier,scope=scope,destination='list.123',verified=True,confirmed=True)
            catalog.handoff_changes(queue); catalog.handoff_changes(queue)
            with queue.connect() as db:
                events=[json.loads(row[0]) for row in db.execute("SELECT event FROM events WHERE state='held'")]
            self.assertEqual([e['operation'] for e in events],['watchlist.add','watchlist.remove'])
            self.assertTrue(all(e['identity']['ids']=={'tmdb':'2'} for e in events))
