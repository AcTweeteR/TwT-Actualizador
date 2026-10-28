import ast
import hashlib
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import time
import types
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from test_provider_catalog_index import INDEX, ROOT


class SeriesWidgetIndexIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = 'host|user|password'
        fingerprint = hashlib.sha256(self.source.encode()).hexdigest()
        self.folder = Path(self.temp.name) / 'catalog_generations' / ('p1-' + fingerprint) / ('a' * 32)
        self.folder.mkdir(parents=True)
        self.path = self.folder / 'xtream_streams_series.json'
        self.items = [{'series_id': str(i), 'name': 'Show %d' % i, 'year': '2024',
                       'tmdb_id': str(i), 'category_id': '1'} for i in range(30)]
        self.path.write_text(json.dumps({'_src': fingerprint, '_data': self.items}))
        self.events = [{'series_id': str(i)} for i in (9, 4, 12, 15)]
        self.recorded = True
        changes = types.SimpleNamespace(generation_processed=lambda *a: self.recorded,
                                        recent=lambda *a: self.events)
        self.g = {'series_changes': changes, 'addon': object(),
                  '_get_credentials_for_profile': lambda p: dict(zip(
                      ('xtream_url', 'xtream_username', 'xtream_password'), self.source.split('|'))),
                  '_cache_path': lambda *a, **k: str(self.path),
                  '_get_cached_xtream_categories': lambda *a, **k: [],
                  '_get_hidden_subcats': lambda *a: [], '_get_hidden_items': lambda *a: [],
                  '_is_adult_category': lambda name: False,
                  '_cache_load': lambda key: {'expires': time.time()+100, 'ranks': [
                      {'tmdb_id': str(i), 'year': '2024', 'titles': []} for i in (4, 9)]},
                  '_log': lambda text: self.assertNotIn('password', text)}
        package = os.environ.get('ACTWEETER_XSTREAM_LIVE_ZIP')
        if os.environ.get('ACTWEETER_RELEASE_CHANNEL') == 'stable':
            package = ROOT.parents[1] / 'docs/testing/repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.38~beta2.zip'
        if not package or not Path(package).is_file():
            self.skipTest('candidate ZIP is not built')
        with zipfile.ZipFile(package) as archive:
            tree = ast.parse(archive.read('plugin.video.xstream-pro/resources/lib/premium_routes.py'))
        tree.body = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name in ('indexed_series_page', '_performance_call', 'catalog', 'provider_id')]
        self.scope = {'time': time, 'number': int}
        exec(compile(tree, 'candidate-routes', 'exec'), self.scope)
        self.modules = mock.patch.dict(sys.modules, {'provider_catalog_index': INDEX})
        self.modules.start(); self.addCleanup(self.modules.stop)

    def call(self, view, **params):
        return self.scope['indexed_series_page'](self.g, 1, view,
            lambda key, default='': params.get(key, default))

    def test_pending_generation_falls_back_without_index_or_history_write(self):
        self.recorded = False
        self.assertIsNone(self.call('series_recent'))
        self.assertFalse(list(self.folder.glob('*.sqlite')))
        self.assertFalse(list(self.folder.glob('catalog-index-request-*')))

    def test_missing_index_schedules_background_and_then_matches_widgets(self):
        self.assertIsNone(self.call('series_recent'))
        self.assertEqual(len(list(self.folder.glob('catalog-index-request-*'))), 1)
        index = INDEX.CatalogIndex(str(self.path), self.source, 1, 'series', build=True)
        self.assertEqual(index.item_count, 30)
        recent = self.call('series_recent')
        self.assertEqual(recent[0], [self.items[i] for i in (9, 4, 12, 15)])
        popular = self.call('popular')
        self.assertEqual(popular[0], [self.items[i] for i in (4, 9)])

    def test_generation_changes_during_query_fall_back(self):
        INDEX.CatalogIndex(str(self.path), self.source, 1, 'series', build=True)
        calls = []
        def path(*a, **k):
            calls.append(1)
            return str(self.path) if len(calls) == 1 else str(self.path) + '.other'
        self.g['_cache_path'] = path
        self.assertIsNone(self.call('series_recent'))

    def test_query_error_falls_back_and_requests_rebuild(self):
        INDEX.CatalogIndex(str(self.path), self.source, 1, 'series', build=True)
        with mock.patch.object(INDEX.CatalogIndex, 'series_events',
                               side_effect=sqlite3.DatabaseError('corrupt')):
            self.assertIsNone(self.call('series_recent'))
        self.assertEqual(len(list(self.folder.glob('catalog-index-request-*'))), 1)

    def test_catalog_records_generation_only_if_path_stays_unchanged(self):
        records = []
        self.g['series_changes'].record_catalog = lambda *a, **kw: records.append(kw)
        self.g['_get_cached_xtream_streams'] = lambda *a, **kw: self.items
        self.scope['catalog'](self.g, 'series', 1)
        self.assertEqual(records[-1]['generation'], 'a' * 32)
        calls = []
        def path(*a, **k):
            calls.append(1)
            return str(self.path) if len(calls) == 1 else str(self.path) + '.other'
        self.g['_cache_path'] = path
        self.scope['catalog'](self.g, 'series', 1)
        self.assertIsNone(records[-1]['generation'])


if __name__ == '__main__':
    unittest.main()
