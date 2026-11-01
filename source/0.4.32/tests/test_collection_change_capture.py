"""Local collection changes and their journal commit together."""
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest

source = Path(__file__).resolve().parents[1] / 'addons/service.actweeter/resources/lib/collection_catalog.py'
spec = importlib.util.spec_from_file_location('capture_catalog', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CollectionCaptureTests(unittest.TestCase):
    def test_local_changes_and_import_origins_are_separate(self):
        with tempfile.TemporaryDirectory() as folder:
            store = module.Catalog(Path(folder) / 'collections.db')
            identifier = store.create_local('Synthetic', origin='mis_colecciones')
            store.add_member(identifier, kind='movie', tmdb_id=42, title='Example')
            store.add_member(identifier, kind='movie', tmdb_id=42, title='Example')
            store.add_member(identifier, kind='show', tmdb_id=7, title='Series', origin='trakt_import')
            store.remove_member(identifier, kind='movie', tmdb_id=42)
            with store._db() as db:
                rows = db.execute('select operation,kind,tmdb_id,origin,status from changes order by id').fetchall()
            self.assertEqual(rows, [('list_create', 'mixed', None, 'local', 'pending'),
                ('member_add', 'movie', 42, 'local', 'pending'),
                ('member_add', 'show', 7, 'trakt_import', 'observed'),
                ('member_remove', 'movie', 42, 'local', 'pending')])

    def test_journal_failure_rolls_back_list_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            store = module.Catalog(Path(folder) / 'collections.db')
            identifier = store.create_local('Synthetic', origin='mis_colecciones')
            with store._db() as db:
                db.execute("CREATE TRIGGER fail_change BEFORE INSERT ON changes BEGIN SELECT RAISE(ABORT, 'fail'); END")
            with self.assertRaises(sqlite3.IntegrityError):
                store.add_member(identifier, kind='movie', tmdb_id=42, title='Example')
            self.assertEqual(store.members(identifier), [])

    def test_remote_snapshot_rejects_stale_scope_and_rolls_back_interruption(self):
        scope = dict(account='synthetic', profile='1', provider_scope='a'*64,
                     kodi_profile='b'*64, generation='c'*64)
        with tempfile.TemporaryDirectory() as folder:
            store = module.Catalog(Path(folder) / 'collections.db')
            identifier = store.create_local('Synthetic', origin='mis_colecciones')
            mapping = store.configure_destination(identifier, scope=scope,
                destination='list.123', verified=True, confirmed=True)
            def apply(items, timestamp=10):
                return store.apply_remote(identifier, scope=scope, revision=mapping['revision'],
                    items=items, observed_at=timestamp, complete=True)
            item = dict(kind='movie', tmdb_id=42, title='Example')
            with store._db() as db:
                db.execute("CREATE TRIGGER fail_import BEFORE INSERT ON changes WHEN NEW.origin='trakt_import' BEGIN SELECT RAISE(ABORT, 'interrupted'); END")
            with self.assertRaises(sqlite3.IntegrityError):
                apply([item])
            self.assertEqual(store.members(identifier), [])
            with store._db() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM remote_state').fetchone()[0], 0)
                db.execute('DROP TRIGGER fail_import')
            self.assertEqual(apply([item])['added'], 1)
            self.assertTrue(apply([], 9)['stale'])
            self.assertEqual(len(store.members(identifier)), 1)
            store.configure_destination(identifier, scope=scope, destination='watchlist',
                                        verified=True, confirmed=True)
            with self.assertRaises(PermissionError):
                apply([], 11)
            self.assertEqual(len(store.members(identifier)), 1)
