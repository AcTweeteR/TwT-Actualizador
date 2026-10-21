"""Execute the distributed stores and tracked patch against synthetic profiles only."""
import importlib.util
import ast
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT.parents[1] / 'repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.15.zip'


class CollectionsIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = tempfile.TemporaryDirectory()
        cls.root = Path(cls.source.name)
        with zipfile.ZipFile(BASELINE) as archive:
            for name in ('favorites.py', 'pending_adapter.py', 'addon.py', 'premium_routes.py'):
                target = cls.root / 'resources/lib' / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read('plugin.video.xstream-pro/resources/lib/' + name))
        spec = importlib.util.spec_from_file_location('collections_builder', ROOT / 'tools/build_xstream_package.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        builder.apply_contextual_unified_patch(cls.root, ROOT / 'third_party/xstream/patches/1.1.2/actweeter-collections.patch')
        builder.apply_contextual_unified_patch(cls.root, ROOT / 'third_party/xstream/patches/1.1.2/actweeter-collections-empty.patch')

    @classmethod
    def tearDownClass(cls):
        cls.source.cleanup()

    def setUp(self):
        self.data = tempfile.TemporaryDirectory()
        self.addCleanup(self.data.cleanup)
        mocks = {
            'xbmc': types.SimpleNamespace(getCondVisibility=lambda _: False),
            'xbmcvfs': types.SimpleNamespace(translatePath=lambda value: value),
            'lang': types.SimpleNamespace(_t=lambda _: 'Favoritos'),
        }
        with patch.dict(sys.modules, mocks):
            scope = {}
            exec(compile((self.root / 'resources/lib/favorites.py').read_bytes(), 'favorites.py', 'exec'), scope)
        self.Favorites = scope['Favorites']
        self.addon = types.SimpleNamespace(getAddonInfo=lambda _: self.data.name)
        scope = {}
        exec(compile((self.root / 'resources/lib/pending_adapter.py').read_bytes(), 'pending_adapter.py', 'exec'), scope)
        self.Pending = scope['PendingAdapter']
        self.store = self.Favorites(self.addon, '1')
        self.pending = self.Pending(self.store)

    def item(self, kind='movie', identity='42'):
        return {'id': identity, 'stype': kind, 'name': 'Synthetic ' + kind, 'url': 'plugin://synthetic/'}

    def test_pending_alone_is_not_a_favorite(self):
        self.pending.add('movie', self.item())
        self.assertFalse(self.store.is_favorite('42', stype='movie'))
        self.assertEqual(self.store.get_favorites(), [])

    def test_distributable_contains_exact_tested_store_and_routes(self):
        import hashlib
        import json
        manifest = json.loads((ROOT / 'third_party/xstream/upstream.json').read_text())
        package = ROOT.parents[1] / 'docs/testing/repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.17.zip'
        with zipfile.ZipFile(package) as archive:
            self.assertIsNone(archive.testzip())
            for name in ('favorites.py', 'pending_adapter.py', 'addon.py', 'premium_routes.py'):
                member = 'resources/lib/' + name
                payload = archive.read('plugin.video.xstream-pro/' + member)
                self.assertEqual(payload, (self.root / member).read_bytes())
                self.assertEqual(hashlib.sha256(payload).hexdigest(), manifest['local_runtime_sha256'][member])

    def test_removing_favorite_keeps_pending_and_custom_folder(self):
        item = self.item()
        self.store.add(item)
        self.store.add(item, 'Custom')
        self.pending.add('movie', item)
        self.store.remove('42', stype='movie')
        self.assertTrue(self.pending.contains('movie', '42'))
        self.assertEqual(self.store.get_all('Custom'), [item])
        self.assertEqual(self.store.get_favorites(), [])

    def test_removing_pending_keeps_favorite(self):
        self.store.add(self.item())
        self.pending.add('movie', self.item())
        self.pending.remove('movie', '42')
        self.assertTrue(self.store.is_favorite('42', stype='movie'))
        self.assertFalse(self.pending.contains('movie', '42'))

    def test_movie_series_numeric_id_collision(self):
        for kind in ('movie', 'series'):
            self.assertTrue(self.store.add(self.item(kind)))
            self.pending.add(kind, self.item(kind))
        self.store.remove('42', stype='movie')
        self.assertTrue(self.store.is_favorite('42', stype='series'))
        self.assertEqual(self.store.get_favorites('movie'), [])
        self.assertEqual(len(self.store.get_favorites('series')), 1)
        self.pending.remove('series', '42')
        self.assertTrue(self.pending.contains('movie', '42'))

    def test_persistence_and_profile_isolation(self):
        self.store.add(self.item())
        self.pending.add('series', self.item('series'))
        reopened = self.Favorites(self.addon, '1')
        self.assertTrue(reopened.is_favorite('42', stype='movie'))
        self.assertTrue(self.Pending(reopened).contains('series', '42'))
        self.assertEqual(self.Favorites(self.addon, '2').get_favorites(), [])

    def test_legacy_list_and_english_folder_are_read_without_migration(self):
        import json
        path = Path(self.store.file)
        for payload in ([self.item()], {'version': 1, 'Favorites': [self.item()]}):
            path.write_text(json.dumps(payload))
            before = path.read_bytes()
            reopened = self.Favorites(self.addon, '1')
            self.assertTrue(reopened.is_favorite('42', stype='movie'))
            self.assertEqual(path.read_bytes(), before)

    def test_unknown_completion_never_removes_pending(self):
        self.pending.add('series', self.item('series'))
        for state in (None, False, 'true', 1):
            self.assertFalse(self.pending.reconcile_completion('series', '42', state))
            self.assertTrue(self.pending.contains('series', '42'))
        self.assertTrue(self.pending.reconcile_completion('series', '42', True))

    def test_toggle_is_scoped_to_explicit_folder_and_type(self):
        self.pending.add('movie', self.item())
        self.store.add(self.item('series'))
        self.assertTrue(self.store.toggle(self.item()))
        self.assertFalse(self.store.toggle(self.item()))
        self.assertTrue(self.store.is_favorite('42', stype='series'))
        self.assertTrue(self.pending.contains('movie', '42'))

    def test_context_has_independent_actions_and_updates_after_mutation(self):
        from urllib.parse import urlencode
        tree = ast.parse((self.root / 'resources/lib/addon.py').read_bytes())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                        and node.name == '_build_favorite_ctx')
        env = {'_get_profile_fav': lambda _: self.store, 'fav': self.store,
               '_t': lambda key, *args: {30009: 'Favoritos', 30746: 'Añadir a favoritos',
                                        30747: 'Quitar de favoritos'}.get(key, str(key)),
               'build_url': lambda params: 'plugin://synthetic/?' + urlencode(params),
               'is_url_downloadable': lambda _: False}
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'context.py', 'exec'), env)
        def context():
            with patch.dict(sys.modules, {'pending_adapter': types.SimpleNamespace(PendingAdapter=self.Pending)}):
                return env['_build_favorite_ctx']('42', 'Synthetic', 'movie', '', '', profile_num='1')
        self.assertEqual([label for label, _ in context()], ['Añadir a favoritos', 'Añadir a pendientes'])
        self.store.add(self.item())
        self.pending.add('movie', self.item())
        self.assertEqual([label for label, _ in context()], ['Quitar de favoritos', 'Quitar de pendientes'])
        self.store.remove('42', stype='movie')
        actions = context()
        self.assertEqual([label for label, _ in actions], ['Añadir a favoritos', 'Quitar de pendientes'])
        self.assertEqual(len(actions), len({action for _, action in actions}))

    def test_collection_root_always_returns_two_typed_folders_without_provider_lookup(self):
        from urllib.parse import urlencode, urlsplit, parse_qs
        namespace = {}
        with patch.dict(sys.modules, {'content_state': types.SimpleNamespace()}):
            exec(compile((self.root / 'resources/lib/premium_routes.py').read_bytes(), 'routes.py', 'exec'), namespace)
        class Item:
            def __init__(self, label): self.label, self.properties = label, {}
            def setArt(self, art): self.art = art
            def setProperty(self, key, value): self.properties[key] = value
        for kind in ('movie', 'series'):
            rows = []
            plugin = types.SimpleNamespace(setContent=lambda *a: None,
                setPluginCategory=lambda *a: None, endOfDirectory=lambda *a, **kw: None,
                addDirectoryItem=lambda handle, route, item, folder: rows.append((route, item, folder)))
            env = {'pm': types.SimpleNamespace(active='2'), 'addon_handle': 1,
                   'xbmcplugin': plugin, '_new_listitem': Item,
                   'build_url': lambda params: 'plugin://synthetic/?' + urlencode(params)}
            namespace['dispatch'](env, {'view': ['collections_root'], 'stype': [kind]})
            self.assertEqual([item.label for _, item, _ in rows], ['Favoritos', 'Pendientes'])
            for route, item, folder in rows:
                self.assertTrue(folder)
                self.assertEqual(parse_qs(urlsplit(route).query)['stype'], [kind])
                self.assertEqual(parse_qs(urlsplit(route).query)['profile_num'], ['2'])
                self.assertEqual(item.properties['AcTweeteR.CollectionFolder'], '1')
                self.assertNotIn('AcTweeteR.Expand', item.properties)

    def test_empty_collections_render_native_navigation_and_do_not_write(self):
        from urllib.parse import urlencode, urlsplit, parse_qs
        namespace = {}
        with patch.dict(sys.modules, {'content_state': types.SimpleNamespace()}):
            exec(compile((self.root / 'resources/lib/premium_routes.py').read_bytes(), 'routes.py', 'exec'), namespace)
        namespace['catalog'] = lambda *args: ([], ('unused', 'unused', 'unused'))
        namespace['indexed_movie_page'] = lambda *args: None
        namespace['add_provider_item'] = lambda *args, **kw: self.fail('empty must not render provider media')
        class Item:
            def __init__(self, label): self.label, self.properties = label, {}
            def setArt(self, art): self.art = art
            def setProperty(self, key, value): self.properties[key] = value
        rows = []
        plugin = types.SimpleNamespace(setContent=lambda *a: None,
            addSortMethod=lambda *a: None, SORT_METHOD_NONE=0,
            endOfDirectory=lambda *a, **kw: None,
            addDirectoryItem=lambda handle, route, li, is_folder: rows.append((route,li,is_folder)))
        env = {'pm': types.SimpleNamespace(active='1'), 'addon_handle': 1,
               'xbmcplugin': plugin, 'build_url': lambda q:'plugin://synthetic/?'+urlencode(q),
               '_get_profile_fav': lambda _:self.store, '_new_listitem': Item,
               'pending_adapter': types.SimpleNamespace(PendingAdapter=self.Pending),
               '_prefetch_vod_info_batch': lambda *args: None}
        from pathlib import Path
        favorite_file = Path(self.store.file)
        for stype in ('movie','series'):
            for view in ('favorites','pending'):
                rows.clear()
                before = favorite_file.read_bytes() if favorite_file.exists() else None
                namespace['dispatch'](env, {'view':[view], 'stype':[stype], 'browse':['1']})
                after = favorite_file.read_bytes() if favorite_file.exists() else None
                self.assertEqual(before,after)
                self.assertEqual(len(rows),1)
                route,item,is_folder=rows[0]
                self.assertTrue(is_folder)
                self.assertEqual(item.properties['AcTweeteR.EmptyCollection'],'1')
                self.assertIn('Colección vacía',item.label)
                q=parse_qs(urlsplit(route).query)
                self.assertEqual(q['view'],['collections_root'])
                self.assertEqual(q['stype'],[stype])
                self.assertEqual(q['profile_num'],['1'])

    def test_provider_routes_exclude_pending_only_and_missing_items(self):
        namespace = {}
        with patch.dict(sys.modules, {'content_state': types.SimpleNamespace()}):
            exec(compile((self.root / 'resources/lib/premium_routes.py').read_bytes(), 'routes.py', 'exec'), namespace)
        shown, ended = [], []
        catalog = [{'stream_id': '42', 'series_id': '42', 'name': 'Synthetic'},
                   {'stream_id': '43', 'series_id': '43', 'name': 'Pending only'}]
        namespace['catalog'] = lambda *args: (catalog, ('unused', 'unused', 'unused'))
        namespace['indexed_movie_page'] = lambda *args: None
        namespace['prepare_series_state_context'] = lambda *args: None
        namespace['add_provider_item'] = lambda g, item, stype, *args, **kw: shown.append((stype, item['name']))
        self.store.add(self.item('series'))
        self.pending.add('movie', self.item('movie', '43'))
        self.store.add(self.item('movie', '999'))  # No longer in the provider catalog.
        class Item:
            def __init__(self, label): self.label, self.properties = label, {}
            def setArt(self, art): self.art = art
            def setProperty(self, key, value): self.properties[key] = value
        empty_rows = []
        plugin = types.SimpleNamespace(setContent=lambda *a: None,
            addSortMethod=lambda *a: None, SORT_METHOD_NONE=0,
            endOfDirectory=lambda *a, **kw: ended.append(kw),
            addDirectoryItem=lambda handle, route, item, folder:
                empty_rows.append((route, item, folder)))
        env = {'pm': types.SimpleNamespace(active='1'), 'addon_handle': 1,
               'xbmcplugin': plugin, 'build_url': lambda _: 'unused',
               '_get_profile_fav': lambda _: self.store,
               'pending_adapter': types.SimpleNamespace(PendingAdapter=self.Pending),
               '_prefetch_vod_info_batch': lambda *a: None,
               '_new_listitem': Item}
        for kind, expected in (('movie', []), ('series', [('series', 'Synthetic')])):
            shown.clear()
            namespace['dispatch'](env, {'view': ['favorites'], 'stype': [kind], 'browse': ['1']})
            self.assertEqual(shown, expected)
            self.assertFalse(ended[-1]['cacheToDisc'])
        self.assertEqual(len(empty_rows), 1)
        self.assertTrue(empty_rows[0][2])
        self.assertEqual(empty_rows[0][1].label, 'Contenido no disponible en el catálogo actual')
        self.assertEqual(empty_rows[0][1].properties['AcTweeteR.EmptyCollection'], '1')
        self.assertTrue(self.store.is_favorite('999', stype='movie'))
