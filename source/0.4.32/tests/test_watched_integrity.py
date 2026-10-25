"""Regressions for exact identities and dynamic completion across UI routes."""
import ast
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import unittest
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'addons/service.actweeter/resources/lib'))
import content_state


class WatchedIntegrityTests(unittest.TestCase):
    def context(self, rows, watched=None, provider_seen=False):
        record = {'tmdb_id': '42', 'episodes': rows, 'complete': True,
                  'checked_at': time.time()}
        movies = SimpleNamespace(_data=watched or {})
        episodes = SimpleNamespace(is_watched=lambda *args: provider_seen)
        calls = []
        def inventory(*args):
            calls.append(1)
            return {'7': record}
        g = {'addon': object(), 'pm': SimpleNamespace(active='2'),
             'series_changes': SimpleNamespace(inventory_map=inventory)}
        return g, movies, episodes, record, calls

    def test_provider_identity_uses_profile_scoped_response_and_rejects_conflicts(self):
        calls = []
        def loader(key, profile_num):
            calls.append((key, profile_num))
            return {'movie_data': {'stream_id': 7}, 'info': {'tmdb_id': 42}}
        g = {'_cache_load': loader}
        self.assertEqual(content_state.provider_tmdb_id(g, 'movie', '7', 2), '42')
        self.assertEqual(calls, [('vod_info_7', 2)])
        self.assertEqual(content_state.provider_tmdb_id(g, 'movie', '7', 2, '99'), '')
        self.assertEqual(content_state.provider_tmdb_id(g, 'movie', '8', 2), '')

    def test_legacy_complete_marks_never_mark_a_new_episode_seen(self):
        g, movies, episodes, _, _ = self.context(
            [{'season': 1, 'episode': 1, 'provider_id': '10'}],
            {'tvshow:42': True, 'season:42:1': True})
        item = {'tmdb_type': 'tv', 'tmdb_id': '42', 'season': 1, 'episode': 2}
        self.assertFalse(content_state.tmdb_watched_state(g, item, movies, episodes))
        movies._data['tmdb:episode:42:s1:e2'] = True
        self.assertTrue(content_state.tmdb_watched_state(g, item, movies, episodes))

    def test_exact_episode_provider_mark_is_reused_but_explicit_false_wins(self):
        g, movies, episodes, _, _ = self.context(
            [{'season': 0, 'episode': 1, 'provider_id': '10'}], provider_seen=True)
        item = {'tmdb_type': 'tv', 'tmdb_id': '42', 'season': 0, 'episode': 1}
        self.assertTrue(content_state.tmdb_watched_state(g, item, movies, episodes))
        movies._data['tmdb:episode:42:s0:e1'] = False
        self.assertFalse(content_state.tmdb_watched_state(g, item, movies, episodes))

    def test_inventory_growth_removes_show_and_season_checks_until_episode_seen(self):
        g, movies, episodes, record, calls = self.context(
            [{'season': 1, 'episode': 1, 'provider_id': '10'}],
            {'tmdb:episode:42:s1:e1': True, 'tvshow:42': True, 'season:42:1': True})
        show = {'tmdb_type': 'tv', 'tmdb_id': '42'}
        season = dict(show, kind='season', season=1)
        for item in (show, season):
            self.assertTrue(content_state.tmdb_watched_state(g, item, movies, episodes))
        record['episodes'].append({'season': 1, 'episode': 2, 'provider_id': '11'})
        for item in (show, season):
            self.assertFalse(content_state.tmdb_watched_state(g, item, movies, episodes))
        movies._data['tmdb:episode:42:s1:e2'] = True
        for item in (show, season):
            self.assertTrue(content_state.tmdb_watched_state(g, item, movies, episodes))
        self.assertEqual(calls, [1])
        record['episodes'].append({'season': 2, 'episode': 1, 'provider_id': '12'})
        self.assertFalse(content_state.tmdb_watched_state(g, show, movies, episodes))
        self.assertTrue(content_state.tmdb_watched_state(g, season, movies, episodes))

    def test_stale_or_incomplete_inventory_cannot_certify_completion(self):
        g, movies, episodes, record, _ = self.context(
            [{'season': 1, 'episode': 1, 'provider_id': '10'}], provider_seen=True)
        item = {'tmdb_type': 'tv', 'tmdb_id': '42'}
        record['complete'] = False
        self.assertFalse(content_state.tmdb_watched_state(g, item, movies, episodes))
        record['complete'] = True
        record['checked_at'] = 1
        self.assertFalse(content_state.tmdb_watched_state(g, item, movies, episodes))

    def test_resume_adapter_reuses_real_episode_fields_and_exact_movie_url_id(self):
        records = [
            {'stype': 'movie', 'url': 'https://provider.invalid/movie/account/key/7.mp4',
             'position': 200, 'duration': 1000, 'timestamp': 3},
            {'stype': 'series', 'url': 'https://provider.invalid/series/account/key/7.mp4',
             'series_id': '8', 'ep_id': '7', 'season_num': 0, 'episode_num': 1,
             'position': 100, 'duration': 1000, 'timestamp': 4}]
        g = {'addon': None, 'ResumePoints': lambda *args, **kwargs:
             SimpleNamespace(get_all=lambda: records)}
        self.assertIs(content_state.resume_entry(g, 2, provider_id='7'), records[0])
        self.assertIs(content_state.resume_entry(g, 2, provider_id='7', series_id='8',
                                                season=0, episode=1), records[1])
        self.assertIsNone(content_state.resume_entry(g, 2, provider_id='77'))
        self.assertIsNone(content_state.resume_entry(g, 2, provider_id='7', series_id='8',
                                                    season=0, episode=2))

    def test_remote_percentage_requires_exact_identity_and_never_sets_seek_point(self):
        class Item:
            def __init__(self): self.properties = {}
            def setProperty(self, key, value): self.properties[key] = value
            def getVideoInfoTag(self): raise AssertionError('absolute seek was fabricated')
        raw = {'movie': {'ids': {'tmdb': 42}}, 'progress': 33.3}
        card = Item()
        self.assertTrue(content_state.apply_remote_progress(card, {'tmdb_id': '42', 'raw': raw}))
        self.assertEqual(card.properties, {'XStream.RemoteProgress': '33.3'})
        for progress in (None, '40', True, -1, 0, 100, float('inf'), float('nan')):
            card = Item()
            self.assertFalse(content_state.apply_remote_progress(card,
                {'tmdb_id': '42', 'raw': dict(raw, progress=progress)}))
            self.assertEqual(card.properties, {})
        self.assertFalse(content_state.apply_remote_progress(Item(), {'tmdb_id': '99', 'raw': raw}))

    def test_both_skin_card_templates_render_percentage_with_native_priority(self):
        root = ET.parse(ROOT / 'addons/skin.actweeter/1080i/IncludesViews.xml').getroot()
        for name in ('WatchedIndicatorLayout', 'WatchedIndicatorLayoutBingie'):
            include = root.find("include[@name='%s']" % name)
            progress = next(n for n in include.iter('control')
                            if n.findtext('description') == 'In progress Overlay')
            labels = [n for n in progress.findall('control') if n.get('type') == 'label']
            self.assertEqual(len(labels), 2)
            native = next(n for n in labels if '.Property(XStream.RemoteProgress)' not in n.findtext('label'))
            remote = next(n for n in labels if '.Property(XStream.RemoteProgress)' in n.findtext('label'))
            self.assertTrue(native.findtext('visible').startswith('!Integer.IsEqual'))
            self.assertTrue(remote.findtext('visible').startswith('Integer.IsEqual'))

    def test_packaged_tmdb_route_uses_dynamic_exact_state(self):
        package = os.environ.get('ACTWEETER_XSTREAM_LIVE_ZIP')
        self.assertTrue(package, 'exact candidate ZIP required')
        with zipfile.ZipFile(package) as archive:
            tree = ast.parse(archive.read('plugin.video.xstream-pro/resources/lib/tmdb_routes.py'))
        method = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_is_watched')
        g, movies, episodes, _, _ = self.context([], {'tvshow:42': True, 'season:42:1': True})
        namespace = {'_CTX': g}
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'candidate-route', 'exec'), namespace)
        self.assertFalse(namespace['_is_watched'](
            {'tmdb_type': 'tv', 'tmdb_id': '42', 'season': 1, 'episode': 2}, movies, episodes))

    def test_packaged_trakt_media_card_exposes_percentage_without_fake_resume(self):
        package = os.environ.get('ACTWEETER_XSTREAM_LIVE_ZIP')
        self.assertTrue(package, 'exact candidate ZIP required')
        with zipfile.ZipFile(package) as archive:
            tree = ast.parse(archive.read('plugin.video.xstream-pro/resources/lib/tmdb_routes.py'))
        method = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_media_item')
        class Item:
            def __init__(self): self.properties = {}
            def setProperty(self, key, value): self.properties[key] = value
            def setArt(self, value): pass
            def addContextMenuItems(self, value): pass
        context = {'_new_listitem': lambda *args: Item(), '_set_tmdb_item_info': lambda *args: None,
                   '_tmdb_item_ctx': lambda *args, **kwargs: [],
                   '_tmdb_source_select_url': lambda *args, **kwargs: 'plugin://synthetic',
                   '_local_icon': lambda *args: ''}
        namespace = {'c': context.__getitem__, '_is_watched': lambda *args: False,
                     '_maybe_rpdb_poster': lambda item: '',
                     '_source_auto_play_first_enabled': lambda: False}
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'candidate-progress-card', 'exec'), namespace)
        _, item, _ = namespace['_media_item']({'tmdb_type': 'movie', 'tmdb_id': '42',
            'raw': {'movie': {'ids': {'tmdb': 42}}, 'progress': 33.3}})
        self.assertEqual(item.properties['XStream.RemoteProgress'], '33.3')

    def test_packaged_provider_cards_keep_artwork_but_never_trust_title_identity(self):
        package = os.environ.get('ACTWEETER_XSTREAM_LIVE_ZIP')
        self.assertTrue(package, 'exact candidate ZIP required')
        with zipfile.ZipFile(package) as archive:
            tree = ast.parse(archive.read('plugin.video.xstream-pro/resources/lib/premium_routes.py'))
        method = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'listitem')
        class Tag:
            def __init__(self): self.values = {}
            def __getattr__(self, key):
                return lambda *args: self.values.__setitem__(key, args)
        class Item:
            def __init__(self): self.tag, self.properties, self.art = Tag(), {}, {}
            def getVideoInfoTag(self): return self.tag
            def setProperty(self, key, value): self.properties[key] = value
            def setArt(self, art): self.art.update(art)
        raw = {}
        g = {'addon': object(), '_cache_load': lambda *args, **kwargs: raw,
             '_new_listitem': lambda *args: Item(),
             'WatchedMovies': lambda *args, **kwargs: SimpleNamespace(
                 _data={'tmdb:movie:99': True, 'tmdb:movie:42': True}),
             'ResumePoints': lambda *args, **kwargs: SimpleNamespace(get_all=lambda: [])}
        namespace = {'content_state': content_state, 'backdrop': lambda x: x or '',
                     'number': lambda value: int(value or 0),
                     'provider_id': lambda item, kind: str(item.get('stream_id') or '')}
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'candidate-provider', 'exec'), namespace)
        data = {'title': 'Ambiguous title', 'tmdb_id': '99', 'imdb_id': 'tt999',
                'poster_url': 'https://art.invalid/poster.jpg'}
        card = namespace['listitem'](g, {'stream_id': 7}, 'movie', dict(data), profile_num=2)
        self.assertNotIn('setPlaycount', card.tag.values)
        self.assertNotIn('setUniqueIDs', card.tag.values)
        self.assertEqual(card.art['poster'], data['poster_url'])
        raw.update(movie_data={'stream_id': 7}, info={'tmdb_id': '42'})
        card = namespace['listitem'](g, {'stream_id': 7}, 'movie', dict(data), profile_num=2)
        self.assertEqual(card.tag.values['setPlaycount'], (1,))
        self.assertEqual(card.tag.values['setUniqueIDs'], ({'tmdb': '42'}, 'tmdb'))

