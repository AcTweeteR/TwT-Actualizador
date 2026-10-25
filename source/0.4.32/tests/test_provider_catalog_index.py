import importlib.util
import hashlib
import json
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'provider_catalog_index', ROOT / 'third_party/xstream/provider_catalog_index.py')
INDEX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INDEX)


class ProviderCatalogIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'catalog.json'
        self.source = 'https://provider.invalid|user|password'
        self.items = [
            {'stream_id': 'hidden-first', 'name': 'Café (2024)', 'year': '2024',
             'category_id': '1', 'tmdb_id': '7', 'added': '10',
             'url': 'https://synthetic.invalid/movie/hidden-first'},
            {'stream_id': 'visible-edition', 'name': 'Cafe', 'year': '2024',
             'category_id': '2', 'tmdb_id': '7', 'added': '20',
             'url': 'https://synthetic.invalid/movie/visible-edition'},
            {'stream_id': 'old', 'name': 'Old', 'year': '2020',
             'category_id': '2', 'tmdb_id': '8', 'added': '1'},
            {'stream_id': 'old', 'name': 'Old', 'year': '2020',
             'category_id': '2', 'tmdb_id': '8', 'added': '2'},
            {'stream_id': 'unicode', 'name': '東京 (2025)', 'year': '2025',
             'category_id': '2', 'tmdb_id': '9', 'added': '30'},
        ]
        self.write_catalog()

    def tearDown(self):
        self.temp.cleanup()

    def write_catalog(self, items=None, source=None):
        self.path.write_text(json.dumps({'_src': source or self.source,
            '_data': self.items if items is None else items}, ensure_ascii=False), encoding='utf-8')

    def index(self, source=None, profile=1):
        return INDEX.CatalogIndex(str(self.path), source or self.source, profile, 'movie', build=True)

    def test_catalog_and_recent_preserve_filters_dedup_order_and_unicode_offsets(self):
        index = self.index()
        items, more = index.page(blocked_categories=('1',), limit=48)
        self.assertEqual([item['stream_id'] for item in items], ['visible-edition', 'old', 'unicode'])
        self.assertEqual(items[0], self.items[1])
        self.assertEqual(items[0]['url'], self.items[1]['url'])
        self.assertFalse(more)
        recent, more = index.page(mode='recent', blocked_categories=('1',), limit=48)
        self.assertEqual([item['stream_id'] for item in recent], ['unicode', 'visible-edition', 'old'])
        self.assertFalse(more)

    def test_browse_keeps_duplicate_editions_and_page_limit_is_capped(self):
        items, more = self.index().page(blocked_categories=('1',), browse=True,
                                         page=1, limit=999)
        self.assertEqual(len(items), 4)
        self.assertFalse(more)
        self.assertEqual([item['stream_id'] for item in items],
                         ['visible-edition', 'old', 'old', 'unicode'])

    def test_explicit_provider_id_keeps_duplicate_rows_like_legacy_route(self):
        items, more = self.index().page(provider_id='old', limit=48)
        self.assertEqual(len(items), 2)
        self.assertFalse(more)

    def test_ranked_preserves_provider_rank_and_rejects_ambiguous_titles(self):
        items, more = self.index().ranked([
            {'tmdb_id': '9', 'year': '2025', 'titles': ['東京']},
            {'tmdb_id': '', 'year': '2024', 'titles': ['café']},
        ], blocked_categories=('1',), limit=48)
        self.assertEqual([item['stream_id'] for item in items], ['unicode', 'visible-edition'])
        self.assertFalse(more)

    def test_indexed_search_matches_accents_substrings_and_visibility(self):
        index = self.index()
        self.assertEqual([x['stream_id'] for x in index.search('Cafe', blocked_categories=('1',))], ['visible-edition'])
        self.assertEqual([x['stream_id'] for x in index.search('afe', blocked_categories=('1',))], ['visible-edition'])
        self.assertEqual(index.search('Cafe', blocked_categories=('1',), hidden_ids=('visible-edition',)), [])
        self.assertEqual([x['stream_id'] for x in index.search('東京')], ['unicode'])

    def test_search_preserves_catalog_order_for_prefix_and_substring(self):
        self.write_catalog(items=[
            {'stream_id': 'first', 'name': 'The Matrix', 'category_id': '2'},
            {'stream_id': 'second', 'name': 'Matrix Reloaded', 'category_id': '2'},
            {'stream_id': 'third', 'name': 'Matrix Revolutions', 'category_id': '2'},
        ])
        index = self.index()
        self.assertEqual([x['stream_id'] for x in index.search('matrix', limit=2)],
                         ['first', 'second'])
        self.assertEqual([x['stream_id'] for x in index.search('matrix', limit=100)],
                         ['first', 'second', 'third'])

    def test_search_index_rejects_stale_source_and_is_profile_isolated(self):
        original = self.index()
        self.assertEqual(len(original.search('cafe')), 2)
        self.write_catalog(items=[{'stream_id': 'new', 'name': 'New Film', 'category_id': '2'}])
        with self.assertRaises(INDEX.IndexUnavailable):
            INDEX.CatalogIndex(str(self.path), self.source, 1, 'movie')
        rebuilt = self.index()
        self.assertEqual(rebuilt.search('cafe'), [])
        self.assertEqual([x['stream_id'] for x in rebuilt.search('new')], ['new'])

    def test_source_and_profile_are_isolated_and_no_source_is_written_to_index(self):
        first = self.index(profile=1)
        second = self.index(profile=2)
        self.assertNotEqual(first.path, second.path)
        with self.assertRaisesRegex(ValueError, 'does not match'):
            self.index(source='other-provider')
        self.assertNotIn('password', Path(first.path).read_bytes().decode('latin1'))

    def test_concurrent_builds_publish_complete_indexes(self):
        results = []
        errors = []

        def build():
            try:
                index = self.index()
                results.append(index.page(limit=48)[0])
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=build) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertFalse(errors)
        self.assertEqual(len(results), 2)
        self.assertEqual([item['stream_id'] for item in results[0]],
                         [item['stream_id'] for item in results[1]])

    def test_patch_applies_to_current_candidate_and_source_hash_is_locked(self):
        source_root = ROOT / 'third_party/xstream'
        manifest = json.loads((source_root / 'upstream.json').read_text())
        patch = source_root / manifest['catalog_index_patch'].removeprefix('third_party/xstream/')
        source = source_root / 'provider_catalog_index.py'
        self.assertEqual(hashlib.sha256(patch.read_bytes()).hexdigest(),
                         manifest['catalog_index_patch_sha256'])
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),
                         manifest['catalog_index_source_sha256'])
        package = ROOT.parents[1] / 'docs/testing/repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.12.zip'
        builder_path = ROOT / 'tools/build_xstream_package.py'
        spec = importlib.util.spec_from_file_location('xstream_package_builder', builder_path)
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory() as temp, zipfile.ZipFile(package) as archive:
            archive.extract('plugin.video.xstream-pro/resources/lib/premium_routes.py', temp)
            archive.extract('plugin.video.xstream-pro/service.py', temp)
            root = Path(temp) / 'plugin.video.xstream-pro'
            self.assertGreater(builder.apply_contextual_unified_patch(root, patch), 7)
            runtime = root / 'resources/lib/premium_routes.py'
            text = runtime.read_text(encoding='utf-8')
            self.assertIn('indexed_movie_page', text)
            self.assertIn('Movie catalog index unavailable; using original path', text)
            self.assertIn('resources/lib/provider_catalog_index.py',
                          builder_path.read_text(encoding='utf-8'))

    def test_catalog_change_rebuilds_index_and_corrupt_index_recovers(self):
        first = self.index()
        self.path.write_text(self.path.read_text() + ' ', encoding='utf-8')
        refreshed = self.index()
        self.assertEqual(refreshed.path, first.path)
        self.assertFalse(refreshed.page(limit=48)[1])
        Path(refreshed.path).write_bytes(b'corrupt')
        recovered = self.index()
        self.assertTrue(recovered.invalidated)
        self.assertFalse(recovered.page(limit=48)[1])

    def test_empty_catalog_is_valid_and_invalid_json_fails_closed(self):
        self.write_catalog([])
        index = self.index()
        self.assertEqual(index.item_count, 0)
        self.assertEqual(index.page(limit=20), ([], False))
        self.path.write_text('{broken', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.index()


if __name__ == '__main__':
    unittest.main()
