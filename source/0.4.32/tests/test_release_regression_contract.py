"""Hard gates for the exact local Beta; Stable promotion has its own explicit gate."""
import ast
import os
import types
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1] / 'repo'
REQUIRED_SEED_REPOS = ('repository.rivulet', 'repository.zachmorris')


class ReleaseRegressionContract(unittest.TestCase):
    def test_beta_bootstrap_repositories_are_discoverable(self):
        path = os.environ.get('ACTWEETER_BETA_INDEX')
        if not path:
            self.skipTest('Requires an exact staged Beta index')
        index = ET.parse(path).getroot()
        for addon_id in REQUIRED_SEED_REPOS:
            with self.subTest(addon=addon_id):
                addon = index.find("addon[@id='%s']" % addon_id)
                self.assertIsNotNone(addon)
                self.assertIsNotNone(addon.find('extension[@point="xbmc.addon.repository"]'))

    @unittest.skipUnless(os.environ.get('ACTWEETER_RELEASE_CHANNEL') == 'stable',
                         'requires ACTWEETER_RELEASE_CHANNEL=stable')
    def test_stable_bootstrap_repositories_are_discoverable(self):
        index = ET.parse(REPO / 'addons.xml').getroot()
        for addon_id in REQUIRED_SEED_REPOS:
            with self.subTest(addon=addon_id):
                self.assertIsNotNone(index.find("addon[@id='%s']" % addon_id))
                self.assertTrue(list((REPO / addon_id).glob(addon_id + '-*.zip')))

    def test_trakt_recommendations_route_exists_in_actual_candidate(self):
        candidate = os.environ.get('ACTWEETER_XSTREAM_LIVE_ZIP')
        if not candidate:
            self.skipTest('Requires exact staged XStream candidate')
        with zipfile.ZipFile(candidate) as z:
            addon = z.read('plugin.video.xstream-pro/resources/lib/addon.py').decode()
            routes = z.read('plugin.video.xstream-pro/resources/lib/tmdb_routes.py').decode()
            trakt = z.read('plugin.video.xstream-pro/resources/lib/trakt.py').decode()
        methods = {n.name for n in ast.parse(routes).body if isinstance(n, ast.FunctionDef)}
        self.assertFalse('_tmdb_routes.trakt_recommendations_route(' in addon, 'legacy Trakt route remains in packaged XStream')
        self.assertIn('trakt_list_route', methods)
        self.assertIn('trakt_recommendations', addon)
        self.assertIn('section == "recommendations"', routes)
        self.assertIn('AcTweeteR.Expand', routes)
        self.assertIn('cached_request(_media_path(section, media)', trakt)

    def test_recommendation_api_uses_authenticated_hourly_cache_only_for_recommendations(self):
        candidate = os.environ.get('ACTWEETER_XSTREAM_LIVE_ZIP')
        if not candidate:
            self.skipTest('Requires exact staged XStream candidate')
        with zipfile.ZipFile(candidate) as archive:
            source = archive.read('plugin.video.xstream-pro/resources/lib/trakt.py').decode()
        function = next(node for node in ast.parse(source).body
                        if isinstance(node, ast.FunctionDef) and node.name == '_media_list_one')
        calls = []
        def cached(path, params, auth, ttl, timeout):
            calls.append(('cache', path, params, auth, ttl, timeout))
            return [], 1
        def direct(path, params, auth):
            calls.append(('direct', path, params, auth))
            return [], 1
        scope = {'_trakt_media_name': lambda kind: ('movies' if kind == 'movie' else 'shows', kind),
                 '_media_path': lambda section, media: '/' + section + '/' + media,
                 'cached_request': cached, 'request': direct,
                 'normalize_entries': lambda rows, media: rows}
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<candidate trakt>', 'exec'), scope)
        scope['_media_list_one']('recommendations', 'movie')
        scope['_media_list_one']('watchlist', 'tv')
        self.assertEqual(calls[0], ('cache', '/recommendations/movies',
                                   {'extended': 'full', 'page': 1, 'limit': 100,
                                    'ignore_collected': 'true'}, True, 3600, 5))
        self.assertEqual(calls[1], ('direct', '/watchlist/shows',
                                   {'extended': 'full', 'page': 1, 'limit': 20}, True))

    def test_recommendation_cache_is_scoped_to_authenticated_account(self):
        candidate = os.environ.get('ACTWEETER_XSTREAM_LIVE_ZIP')
        if not candidate:
            self.skipTest('Requires exact staged XStream candidate')
        with zipfile.ZipFile(candidate) as archive:
            source = archive.read('plugin.video.xstream-pro/resources/lib/trakt.py').decode()
        function = next(node for node in ast.parse(source).body
                        if isinstance(node, ast.FunctionDef) and node.name == 'cached_request')
        state = {'token': 'account-one', 'calls': 0, 'cached': {}}
        cache = types.SimpleNamespace(
            make_key=lambda *parts: tuple(str(part) for part in parts),
            get=lambda namespace, key: state['cached'].get((namespace, key)),
            set=lambda namespace, key, result, ttl: state['cached'].update({(namespace, key): result}))
        def request(path, params, auth, timeout):
            state['calls'] += 1
            return [state['token']], 1
        scope = {'cache': cache, '_read_tokens': lambda: {'access_token': state['token']},
                 'request': request}
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<candidate trakt>', 'exec'), scope)
        self.assertEqual(scope['cached_request']('/recommendations/movies'), (['account-one'], 1))
        self.assertEqual(scope['cached_request']('/recommendations/movies'), (['account-one'], 1))
        state['token'] = 'account-two'
        self.assertEqual(scope['cached_request']('/recommendations/movies'), (['account-two'], 1))
        self.assertEqual(state['calls'], 2)

    def test_manual_trailer_hides_info_while_owned_player_runs(self):
        candidate = os.environ.get('ACTWEETER_SKIN_LIVE_ZIP')
        if not candidate:
            self.skipTest('Requires exact staged skin candidate')
        with zipfile.ZipFile(candidate) as z:
            info = ET.fromstring(z.read('skin.actweeter/1080i/DialogVideoInfo.xml'))
        group = next(node for node in info.findall("controls/control[@type='group']")
                     if any(child.text == 'BingieInfo' for child in node.findall('include')))
        self.assertEqual(group.findtext('visible'),
                         '!Player.HasVideo | String.IsEmpty(Window(Home).Property(SLYGUY_TRAILER_RETURN_PENDING))')
        includes = {node.text: node.get('condition') for node in group.findall('include')}
        self.assertEqual(includes, {'BingieInfo': 'Skin.HasSetting(UseBingieInfoDialog)',
                                   'BingieAltInfo': '!Skin.HasSetting(UseBingieInfoDialog)'})

    def test_auto_preview_options_are_exposed_in_packaged_skin(self):
        candidate = os.environ.get('ACTWEETER_SKIN_LIVE_ZIP')
        if not candidate:
            self.skipTest('Requires exact staged skin candidate')
        with zipfile.ZipFile(candidate) as archive:
            root = ET.fromstring(archive.read('skin.actweeter/1080i/IncludesSkinSettings.xml'))
        controls = {n.get('id'): n for n in root.findall('.//control')}
        for control_id in ('31370', '31173'):
            with self.subTest(control_id=control_id):
                visible = controls[control_id].findtext('visible')
                self.assertIn('System.HasAddon(slyguy.trailers)', visible)
                self.assertNotEqual(visible, 'false')
        delay = controls['31213'].findtext('visible')
        self.assertIn('Skin.HasSetting(BingieAutoTrailer)', delay)

    def test_compatible_slyguy_layouts_are_not_blocked_by_old_version_pins(self):
        candidate = os.environ.get('ACTWEETER_SERVICE_LIVE_ZIP')
        if not candidate:
            self.skipTest('Requires exact staged service candidate')
        with zipfile.ZipFile(candidate) as z:
            prefix = 'service.actweeter/resources/lib/'
            bridge = z.read(prefix + 'slyguy_bridge_install.py').decode()
            guard = z.read(prefix + 'slyguy_player_guard.py').decode()
        self.assertNotIn("getAddonInfo('version')!='0.2.1'", bridge)
        self.assertNotIn('getAddonInfo("version") != "0.87.3"', guard)
        self.assertIn("payloads(originals)", bridge)
        self.assertIn('payload(source)', guard)


if __name__ == '__main__':
    unittest.main()
