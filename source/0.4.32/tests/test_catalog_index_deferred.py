import ast
import hashlib
import importlib.util
import json
import re
import unicodedata
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from contextlib import closing
from pathlib import Path
from unittest import mock

from test_provider_catalog_index import INDEX, ROOT


class DeferredIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'catalog.json'
        self.source = 'synthetic-provider|synthetic-user|synthetic-secret'
        self.items = [{'stream_id': str(i), 'name': 'Title %s' % (i // 2),
                       'year': '2024', 'category_id': str(i % 2), 'added': str(i),
                       'plot': 'Escaped " text \\ é {} []', 'tmdb_id': str(i),
                       'stream_icon': 'https://synthetic.invalid/poster'} for i in range(1100)]
        self.write()

    def write(self, items=None):
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps({'_src': self.source, '_data':
            self.items if items is None else items}), encoding='utf-8')
        temporary.replace(self.path)

    def open(self, **kwargs):
        return INDEX.CatalogIndex(str(self.path), self.source, 1, 'movie', **kwargs)

    def schedule(self):
        with mock.patch.object(INDEX.time, 'time', return_value=-10):
            INDEX.schedule_rebuild(str(self.path), self.source, 1, 'movie')

    def worker(self, **kwargs):
        return INDEX.IndexBuildWorker(self.temp.name, idle=lambda: True,
            cancelled=kwargs.pop('cancelled', lambda: False), **kwargs)

    def requests(self):
        return list(Path(self.temp.name).glob('catalog-index-request-*.json'))

    def test_transactional_generation_request_is_discovered_and_indexed(self):
        fingerprint = hashlib.sha256(self.source.encode()).hexdigest()
        parent = Path(self.temp.name) / 'catalog_generations'
        generation = 'a' * 32
        folder = parent / ('p1-' + fingerprint) / generation
        folder.mkdir(parents=True)
        path = folder / 'movies.json'
        path.write_text(json.dumps({'_src': fingerprint, '_data': self.items}), encoding='utf-8')
        (parent / ('p1-' + fingerprint + '.json')).write_text(json.dumps(
            {'schema': 1, 'generation': generation}), encoding='utf-8')
        with mock.patch.object(INDEX.time, 'time', return_value=-10):
            INDEX.schedule_rebuild(str(path), self.source, 1, 'movie')
        request = list(folder.glob('catalog-index-request-*.json'))
        self.assertEqual(len(request), 1)
        self.assertNotIn(self.source, request[0].read_text())
        self.worker().run_pending()
        self.assertFalse(request[0].exists())
        index = INDEX.CatalogIndex(str(path), self.source, 1, 'movie')
        self.assertTrue(index.reused)
        self.assertEqual(index.item_count, len(self.items))
        with self.assertRaises(ValueError):
            INDEX.CatalogIndex(str(path), 'another-provider', 1, 'movie')
        with self.assertRaises(ValueError):
            INDEX.CatalogIndex(str(path), self.source, 2, 'movie')

    def test_series_index_worker_preserves_series_ids_and_order(self):
        items = [dict(item, series_id='series-' + str(i), stream_id='other-' + str(i))
                 for i, item in enumerate(self.items[:8])]
        self.write(items)
        with mock.patch.object(INDEX.time, 'time', return_value=-10):
            INDEX.schedule_rebuild(str(self.path), self.source, 1, 'series')
        self.worker().run_pending()
        index = INDEX.CatalogIndex(str(self.path), self.source, 1, 'series')
        result, more = index.page(browse=True, limit=8)
        self.assertEqual(result, items)
        self.assertFalse(more)
        result, _ = index.page(provider_id='series-3', browse=True)
        self.assertEqual(result, [items[3]])
        ranks = [{'tmdb_id': items[3]['tmdb_id'], 'year': items[3]['year'],
                  'titles': []}]
        result, _ = index.ranked(ranks, provider_id='series-3', browse=True)
        self.assertEqual(result, [items[3]])

    def test_series_index_request_tracks_active_generation(self):
        fingerprint = hashlib.sha256(self.source.encode()).hexdigest()
        parent = Path(self.temp.name) / 'catalog_generations'
        provider = 'p1-' + fingerprint
        generation = 'a' * 32
        folder = parent / provider / generation
        folder.mkdir(parents=True)
        path = folder / 'xtream_streams_series.json'
        items = [{'series_id': 's1', 'name': 'Example', 'year': '2024',
                  'category_id': '1'}]
        path.write_text(json.dumps({'_src': fingerprint, '_data': items}))
        pointer = parent / (provider + '.json')
        pointer.write_text(json.dumps({'schema': 1, 'generation': generation}))
        with mock.patch.object(INDEX.time, 'time', return_value=-10):
            INDEX.schedule_rebuild(str(path), self.source, 1, 'series')
        pointer.write_text(json.dumps({'schema': 1, 'generation': 'b' * 32}))
        self.worker().run_pending()
        self.assertFalse(list(folder.glob('*.sqlite')))
        pointer.write_text(json.dumps({'schema': 1, 'generation': generation}))
        self.worker().run_pending()
        index = INDEX.CatalogIndex(str(path), self.source, 1, 'series')
        self.assertEqual(index.page(browse=True)[0], items)

    def test_independent_workers_build_one_series_index(self):
        items = [{'series_id': str(i), 'name': 'Title %s' % i,
                  'year': '2024', 'category_id': '1'} for i in range(300)]
        self.write(items)
        with mock.patch.object(INDEX.time, 'time', return_value=-10):
            INDEX.schedule_rebuild(str(self.path), self.source, 1, 'series')
        code = ('import sys; sys.path.insert(0, sys.argv[1]); '
                'from provider_catalog_index import IndexBuildWorker; '
                'IndexBuildWorker(sys.argv[2], idle=lambda: True, '
                'cancelled=lambda: False).run_pending()')
        processes = [subprocess.Popen([sys.executable, '-c', code,
                     str(ROOT / 'third_party/xstream'), self.temp.name]) for _ in range(2)]
        for process in processes:
            self.assertEqual(process.wait(timeout=10), 0)
        self.assertEqual(len(list(Path(self.temp.name).glob('*.sqlite'))), 1)
        self.assertFalse(self.requests())
        index = INDEX.CatalogIndex(str(self.path), self.source, 1, 'series')
        self.assertEqual(index.item_count, len(items))

    def test_series_events_match_visible_catalog_order_and_deduplication(self):
        items = [
            {'series_id': '1', 'name': 'One', 'year': '2024', 'category_id': 'a'},
            {'series_id': '2', 'name': 'Two', 'year': '2024', 'category_id': 'a'},
            {'series_id': '1', 'name': 'One revised', 'year': '2024', 'category_id': 'a'},
            {'series_id': '3', 'name': 'Hidden', 'year': '2024', 'category_id': 'b'},
        ]
        self.write(items)
        index = INDEX.CatalogIndex(str(self.path), self.source, 1, 'series', build=True)
        events = [{'series_id': value} for value in ('3', '2', '1', '2', 'missing')]
        result, more = index.series_events(events, blocked_categories=('b',), limit=2)
        self.assertEqual(result, [items[1], items[2]])
        self.assertFalse(more)
        result, more = index.series_events(events, blocked_categories=('b',), browse=True, limit=2)
        self.assertEqual(result, [items[1], items[2]])
        self.assertTrue(more)
        result, more = index.series_events(events, blocked_categories=('b',), browse=True, page=2, limit=2)
        self.assertEqual(result, [items[1]])
        self.assertFalse(more)

    def test_independent_workers_share_generation_build_lock(self):
        fingerprint = hashlib.sha256(self.source.encode()).hexdigest()
        parent = Path(self.temp.name) / 'catalog_generations'
        folder = parent / ('p1-' + fingerprint) / ('a' * 32)
        folder.mkdir(parents=True)
        path = folder / 'movies.json'
        path.write_text(json.dumps({'_src': fingerprint, '_data': self.items}), encoding='utf-8')
        (parent / ('p1-' + fingerprint + '.json')).write_text(json.dumps(
            {'schema': 1, 'generation': 'a' * 32}), encoding='utf-8')
        with mock.patch.object(INDEX.time, 'time', return_value=-10):
            INDEX.schedule_rebuild(str(path), self.source, 1, 'movie')
        code = ('import sys; sys.path.insert(0, sys.argv[1]); '
                'from provider_catalog_index import IndexBuildWorker; '
                'IndexBuildWorker(sys.argv[2], idle=lambda: True, '
                'cancelled=lambda: False).run_pending()')
        processes = [subprocess.Popen([sys.executable, '-c', code,
                     str(ROOT / 'third_party/xstream'), self.temp.name]) for _ in range(2)]
        for process in processes:
            self.assertEqual(process.wait(timeout=10), 0)
        self.assertEqual(len(list(folder.glob('*.sqlite'))), 1)
        self.assertFalse(list(folder.glob('catalog-index-request-*.json')))
        self.assertEqual(INDEX.CatalogIndex(str(path), self.source, 1, 'movie').item_count,
                         len(self.items))

    def test_worker_ignores_requests_from_inactive_generations(self):
        fingerprint = hashlib.sha256(self.source.encode()).hexdigest()
        parent = Path(self.temp.name) / 'catalog_generations'
        folder = parent / ('p1-' + fingerprint) / ('a' * 32)
        folder.mkdir(parents=True)
        path = folder / 'movies.json'
        path.write_text(json.dumps({'_src': fingerprint, '_data': self.items}), encoding='utf-8')
        (parent / ('p1-' + fingerprint + '.json')).write_text(json.dumps(
            {'schema': 1, 'generation': 'b' * 32}), encoding='utf-8')
        self.path = path
        self.schedule()
        self.worker().run_pending()
        self.assertEqual(len(list(folder.glob('catalog-index-request-*.json'))), 1)
        self.assertFalse(list(folder.glob('*.sqlite')))

    def test_malformed_generation_pointer_does_not_block_legacy_request(self):
        parent = Path(self.temp.name) / 'catalog_generations'
        parent.mkdir()
        name = 'p1-' + 'a' * 64
        (parent / name).mkdir()
        (parent / (name + '.json')).write_text('[]', encoding='utf-8')
        self.schedule()
        self.worker().run_pending()
        self.assertTrue(self.open().reused)

    def test_missing_open_never_reads_catalog_or_starts_a_build(self):
        before = self.path.read_bytes()
        with mock.patch.object(INDEX.CatalogIndex, '_ensure', side_effect=AssertionError('build')), \
             mock.patch('builtins.open', side_effect=AssertionError('read')):
            with self.assertRaises(INDEX.IndexUnavailable) as error:
                self.open()
        self.assertEqual(error.exception.state, 'missing')
        self.assertEqual(before, self.path.read_bytes())
        self.assertFalse(list(Path(self.temp.name).glob('*.sqlite')))

    def test_pending_request_is_private_deduplicated_and_completes_after_restart(self):
        self.schedule(); self.schedule()
        self.assertEqual(len(self.requests()), 1)
        text = self.requests()[0].read_text()
        for secret in ('synthetic-provider', 'synthetic-user', 'synthetic-secret', 'Title'):
            self.assertNotIn(secret, text)
        # Simulate an interrupted previous process: only a temporary DB was left.
        stamp = INDEX._stamp(str(self.path), self.source, 1, 'movie')
        partial = Path(str(self.path) + '.idx-' + stamp[4][:16] + '.sqlite.tmp-crash')
        partial.write_bytes(b'partial')
        self.worker().run_pending()
        self.assertFalse(partial.exists())
        self.assertFalse(self.requests())
        self.assertTrue(self.open().reused)

    def test_valid_v13_index_is_reused_without_rewriting(self):
        package = ROOT.parents[1] / 'docs/testing/repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.13.zip'
        with zipfile.ZipFile(package) as archive:
            scope = {}
            exec(compile(archive.read('plugin.video.xstream-pro/resources/lib/provider_catalog_index.py'), 'v13', 'exec'), scope)
        previous = scope['CatalogIndex'](str(self.path), self.source, 1, 'movie')
        before = Path(previous.path).read_bytes()
        current = self.open()
        self.assertEqual(current.page(mode='recent', limit=20), previous.page(mode='recent', limit=20))
        self.assertEqual(before, Path(previous.path).read_bytes())

    def test_stale_update_never_serves_removed_items_and_rebuilds(self):
        self.open(build=True)
        self.write([dict(self.items[0], stream_id='new')])
        with self.assertRaises(INDEX.IndexUnavailable) as error:
            self.open()
        self.assertEqual(error.exception.state, 'stale')
        self.schedule(); self.worker().run_pending()
        self.assertEqual([x['stream_id'] for x in self.open().page()[0]], ['new'])

    def test_corrupt_and_incompatible_indexes_fallback_then_recover(self):
        index = self.open(build=True)
        for corruption in ('sqlite', 'schema'):
            if corruption == 'sqlite':
                Path(index.path).write_bytes(b'partial or corrupt')
            else:
                with closing(sqlite3.connect(index.path)) as db:
                    db.execute('DROP INDEX recent')
                    db.commit()
            with self.assertRaises(INDEX.IndexUnavailable):
                self.open()
            self.schedule(); self.worker().run_pending()
            self.assertTrue(self.open().reused)

    def test_ranked_full_content_parity_with_v12_and_v13(self):
        ranks = [{'tmdb_id': str(i), 'year': '2024', 'titles': ['Title %s' % (i // 2)]}
                 for i in (29, 19, 99, 2, 11)]
        current = self.open(build=True)
        package_dir = ROOT.parents[1] / 'docs/testing/repo/plugin.video.xstream-pro'
        with zipfile.ZipFile(package_dir / 'plugin.video.xstream-pro-1.1.2.13.zip') as archive:
            scope = {}
            exec(compile(archive.read('plugin.video.xstream-pro/resources/lib/provider_catalog_index.py'), 'v13', 'exec'), scope)
        previous = scope['CatalogIndex'](str(self.path), self.source, 1, 'movie')
        with zipfile.ZipFile(package_dir / 'plugin.video.xstream-pro-1.1.2.12.zip') as archive:
            tree = ast.parse(archive.read('plugin.video.xstream-pro/resources/lib/premium_routes.py'))
        selected = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name in ('normalized', 'provider_id', 'ranked_provider_items')]
        scope = {'re': re, 'unicodedata': unicodedata, 'time': time}
        exec(compile(ast.Module(body=selected, type_ignores=[]), 'v12', 'exec'), scope)
        for browse in (False, True):
            for category in ('', '1'):
                args = dict(blocked_categories=('0',), hidden_ids=('11',), category=category,
                            browse=browse, limit=3)
                self.assertEqual(current.ranked(ranks, **args), previous.ranked(ranks, **args))
                visible = [item for item in self.items if item['category_id'] != '0' and item['stream_id'] != '11']
                legacy = scope['ranked_provider_items']({'_cache_load': lambda key:
                    {'expires': time.time() + 100, 'ranks': ranks}}, visible, 'movie', 'popular')
                legacy = [item for item in legacy if not category or item['category_id'] == category]
                if not browse:
                    seen, unique = set(), []
                    for item in legacy:
                        ident = (scope['normalized'](item['name']), item['year'])
                        if ident not in seen:
                            unique.append(item); seen.add(ident)
                    legacy = unique
                self.assertEqual(current.ranked(ranks, **args), (legacy[:3], len(legacy) > 3))

    def test_rebuild_request_replaces_a_structurally_valid_but_wrong_index(self):
        index = self.open(build=True)
        with closing(sqlite3.connect(index.path)) as db:
            db.execute('DELETE FROM items')
            db.commit()
        self.assertEqual(self.open().page()[0], [])
        self.schedule(); self.worker().run_pending()
        self.assertEqual(self.open().item_count, len(self.items))

    def test_cancelled_build_preserves_source_and_retries_with_a_new_worker(self):
        before = self.path.read_bytes()
        self.schedule()
        with mock.patch.object(INDEX.CatalogIndex, '_ensure', side_effect=INDEX.BuildCancelled()):
            self.worker().run_pending()
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(len(self.requests()), 1)
        payload = json.loads(self.requests()[0].read_text())
        self.assertEqual(payload['attempts'], 1)
        payload['not_before'] = 0
        INDEX._write_request(str(self.requests()[0]), payload)
        self.worker().run_pending()
        self.assertTrue(self.open().reused)

    def test_cancel_during_batches_never_publishes_partial_index(self):
        calls = []
        def cancel():
            calls.append(1)
            return len(calls) >= 3
        with self.assertRaises(INDEX.BuildCancelled):
            self.open(build=True, cancel=cancel)
        self.assertFalse(list(Path(self.temp.name).glob('*.sqlite')))
        self.assertFalse(list(Path(self.temp.name).glob('*.tmp-*')))
        self.assertTrue(self.open(build=True).item_count)

    def test_storage_sqlite_and_read_failures_leave_a_retryable_request(self):
        for failure in ('space', 'sqlite', 'read'):
            self.schedule()
            original = self.path.read_bytes()
            error = sqlite3.OperationalError('synthetic-secret') if failure == 'sqlite' else OSError('synthetic-secret')
            with mock.patch.object(INDEX.CatalogIndex, '_ensure', side_effect=error):
                self.worker().run_pending()
            self.assertEqual(original, self.path.read_bytes())
            self.assertEqual(len(self.requests()), 1)
            self.requests()[0].unlink()
        with mock.patch.object(INDEX.sqlite3, 'connect', side_effect=sqlite3.OperationalError('full')):
            with self.assertRaises(sqlite3.Error): self.open(build=True)
        self.assertFalse(list(Path(self.temp.name).glob('*.tmp-*')))

    def test_real_publish_and_read_errors_cleanup_temporary_database(self):
        for module, method in ((INDEX.os, 'replace'), (INDEX.mmap, 'mmap')):
            with mock.patch.object(module, method, side_effect=OSError('ENOSPC or read failed')):
                with self.assertRaises(OSError): self.open(build=True)
            self.assertFalse(list(Path(self.temp.name).glob('*.sqlite')))
            self.assertFalse(list(Path(self.temp.name).glob('*.tmp-*')))

    def test_insert_failure_closes_sqlite_and_preserves_authoritative_json(self):
        connect = sqlite3.connect
        original = self.path.read_bytes()
        closed = []
        class FailedInsert:
            def __init__(self, *args, **kwargs): self.db = connect(*args, **kwargs)
            def execute(self, *args): return self.db.execute(*args)
            def executemany(self, *args): raise sqlite3.OperationalError('synthetic full disk')
            def close(self): closed.append(True); self.db.close()
        with mock.patch.object(INDEX.sqlite3, 'connect', side_effect=FailedInsert):
            with self.assertRaises(sqlite3.OperationalError): self.open(build=True)
        self.assertTrue(closed)
        self.assertEqual(original, self.path.read_bytes())
        self.assertFalse(list(Path(self.temp.name).glob('*.sqlite')))
        self.assertFalse(list(Path(self.temp.name).glob('*.tmp-*')))

    def test_request_has_grace_period_before_service_build(self):
        INDEX.schedule_rebuild(str(self.path), self.source, 1, 'movie')
        self.worker().run_pending()
        with self.assertRaises(INDEX.IndexUnavailable): self.open()
        self.assertEqual(len(self.requests()), 1)

    def test_two_widgets_and_two_workers_build_only_once(self):
        threads = [threading.Thread(target=lambda: INDEX.schedule_rebuild(str(self.path), self.source, 1, 'movie')) for _ in range(2)]
        for t in threads: t.start()
        for t in threads: t.join()
        for path in self.requests():
            payload = json.loads(path.read_text()); payload['not_before'] = 0
            INDEX._write_request(str(path), payload)
        entered, release = threading.Event(), threading.Event()
        original = INDEX.CatalogIndex._ensure
        def build(obj, *args):
            entered.set(); release.wait(3)
            return original(obj, *args)
        with mock.patch.object(INDEX.CatalogIndex, '_ensure', autospec=True, side_effect=build) as ensure:
            first = threading.Thread(target=self.worker().run_pending)
            first.start(); self.assertTrue(entered.wait(3))
            self.worker().run_pending()
            with self.assertRaises(INDEX.IndexUnavailable): self.open()
            release.set(); first.join(3)
            self.assertEqual(ensure.call_count, 1)
        self.assertTrue(self.open().reused)

    def test_obsolete_jobs_are_discarded_and_empty_catalog_is_valid(self):
        self.schedule(); self.write([])
        self.worker().run_pending()
        self.assertFalse(self.requests())
        self.schedule(); self.worker().run_pending()
        self.assertEqual(self.open().page(), ([], False))

    def test_scope_changed_while_building_does_not_publish(self):
        calls = []
        def update():
            calls.append(1)
            if len(calls) == 2: self.write([])
            return False
        with self.assertRaises(INDEX.BuildCancelled): self.open(build=True, cancel=update)
        self.assertFalse(list(Path(self.temp.name).glob('*.sqlite')))

    def test_profile_and_provider_do_not_share_ready_indexes(self):
        self.open(build=True)
        for profile, source in ((2, self.source), (1, 'other-provider')):
            with self.assertRaises(INDEX.IndexUnavailable):
                INDEX.CatalogIndex(str(self.path), source, profile, 'movie')

    def test_idle_gate_and_shutdown_do_not_spawn_plugin_threads(self):
        worker = INDEX.IndexBuildWorker(self.temp.name, idle=lambda: False, cancelled=lambda: False)
        self.schedule(); worker.tick(); self.assertIsNone(worker.thread)
        worker.close(); worker.tick(); self.assertIsNone(worker.thread)

    def test_plugin_fallback_schedules_without_building_and_survives_full_disk(self):
        # Compile the actual patched helper without importing Kodi's dispatcher.
        spec = importlib.util.spec_from_file_location('builder31', ROOT / 'tools/build_xstream_package.py')
        builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(ROOT.parents[1] / 'docs/testing/repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.12.zip') as archive:
            for relative in ('resources/lib/premium_routes.py', 'service.py'):
                archive.extract('plugin.video.xstream-pro/' + relative, tmp)
            root = Path(tmp) / 'plugin.video.xstream-pro'
            builder.apply_contextual_unified_patch(root, ROOT / 'third_party/xstream/patches/1.1.2/actweeter-catalog-index.patch')
            tree = ast.parse((root / 'resources/lib/premium_routes.py').read_text())
            tree.body = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                         and node.name in ('indexed_movie_page', '_performance_call')]
            scope = {'time': time, 'os': __import__('os'), 'number': int}
            exec(compile(tree, 'premium_helper', 'exec'), scope)
        g = {'_get_credentials_for_profile': lambda p: dict(zip(('xtream_url','xtream_username','xtream_password'), self.source.split('|'))),
             '_cache_valid': lambda key: True, '_cache_path': lambda key: str(self.path),
             '_log': lambda message: self.assertNotIn('synthetic-secret', message)}
        with mock.patch.dict(sys.modules, {'provider_catalog_index': INDEX}), \
             mock.patch.object(INDEX.CatalogIndex, '_ensure', side_effect=AssertionError('synchronous build')):
            self.assertIsNone(scope['indexed_movie_page'](g, 1, 'recent', lambda key, default='': default))
            self.assertEqual(len(self.requests()), 1)
            self.requests()[0].unlink()
            with mock.patch.object(INDEX, '_write_request', side_effect=OSError('disk full synthetic-secret')):
                self.assertIsNone(scope['indexed_movie_page'](g, 1, 'recent', lambda key, default='': default))

        self.open(build=True)
        g.update(_get_cached_xtream_categories=lambda *a: [], _get_hidden_subcats=lambda *a: [],
                 _get_hidden_items=lambda *a: [], _is_adult_category=lambda name: False)
        with mock.patch.dict(sys.modules, {'provider_catalog_index': INDEX}), \
             mock.patch.object(INDEX.CatalogIndex, 'page', side_effect=sqlite3.DatabaseError('damaged page')):
            self.assertIsNone(scope['indexed_movie_page'](g, 1, 'recent', lambda key, default='': default))
        self.assertEqual(len(self.requests()), 1)
        self.assertNotIn('synthetic-secret', self.requests()[0].read_text())

    def test_page_parity_with_legacy_filters_sorting_metadata_and_pagination(self):
        index = self.open(build=True)
        hidden = {'0', '3'}; blocked = {'1'}
        for mode in ('catalog', 'recent'):
            for browse in (False, True):
                for provider_id in ('', '4'):
                    for page in (1, 2):
                        items = [item for item in self.items if item['stream_id'] not in hidden
                                 and item['category_id'] not in blocked]
                        if mode == 'recent': items.sort(key=lambda item: int(item['added']), reverse=True)
                        if provider_id: items = [item for item in items if item['stream_id'] == provider_id]
                        if not browse and not provider_id:
                            seen, rows = set(), []
                            for item in items:
                                key = (INDEX._norm(item['name']), item['year'])
                                if key not in seen: seen.add(key); rows.append(item)
                            items = rows
                        start = (page - 1) * 7
                        expected = (items[start:start + 7], len(items) > start + 7)
                        actual = index.page(mode=mode, hidden_ids=hidden, blocked_categories=blocked,
                                            browse=browse, provider_id=provider_id, page=page, limit=7)
                        self.assertEqual(expected, actual)

    def test_build_trace_is_aggregated_numeric_and_does_not_expose_source(self):
        spec = importlib.util.spec_from_file_location('trace31', ROOT / 'third_party/xstream/performance_diagnostics.py')
        diagnostics = importlib.util.module_from_spec(spec); spec.loader.exec_module(diagnostics)
        lines = []
        self.schedule()
        self.worker(trace_factory=lambda: diagnostics.PerformanceTrace(log=lines.append)).run_pending()
        self.assertEqual(len(lines), 1)
        self.assertNotIn('synthetic-secret', lines[0]); self.assertNotIn('Title ', lines[0])
        payload = json.loads(lines[0].split(' ', 2)[2])
        self.assertEqual(payload['counts']['index.build.rows'], len(self.items))
        self.assertEqual(payload['counts']['index.rebuild.completed'], 1)
        for name in ('scan','decode','fields','insert','sql_indexes','commit','validate','duration'):
            self.assertIn('index.build.' + name, payload['phases'])

    def test_existing_xstream_service_owns_worker_tick_and_shutdown(self):
        spec = importlib.util.spec_from_file_location('service_builder31', ROOT / 'tools/build_xstream_package.py')
        builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(ROOT.parents[1] / 'docs/testing/repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.12.zip') as archive:
            for name in ('service.py', 'resources/lib/premium_routes.py'):
                archive.extract('plugin.video.xstream-pro/' + name, tmp)
            root = Path(tmp) / 'plugin.video.xstream-pro'
            builder.apply_contextual_unified_patch(root, ROOT / 'third_party/xstream/patches/1.1.2/actweeter-catalog-index.patch')
            service = (root / 'service.py').read_text()
        kodi = mock.MagicMock(); kodi.Monitor.return_value.abortRequested.side_effect = [False, True]
        kodi.Monitor.return_value.waitForAbort.return_value = False
        addon = mock.MagicMock(); addon.Addon.return_value.getAddonInfo.return_value = self.temp.name
        vfs = mock.MagicMock(); vfs.translatePath.side_effect = lambda path: path
        worker = mock.MagicMock()
        modules = {'xbmc': kodi, 'xbmcaddon': addon, 'xbmcvfs': vfs,
                   'provider_catalog_index': mock.MagicMock(IndexBuildWorker=worker),
                   'pvr_epg_guard': mock.MagicMock(), 'pvr_group_memory': mock.MagicMock(),
                   'recent_tv_native': mock.MagicMock()}
        with mock.patch.dict(sys.modules, modules):
            exec(compile(service, 'service.py', 'exec'), {'__file__': '/synthetic/service.py'})
        worker.return_value.tick.assert_called_once()
        worker.return_value.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
