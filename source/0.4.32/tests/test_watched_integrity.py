"""Regressions for exact identities and dynamic completion across UI routes."""
import ast
import os
import re
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
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
        self.assertEqual(content_state.local_tmdb_id(g, 'movie', '99', '7', 2), '')
        self.assertEqual(content_state.local_tmdb_id(g, 'movie', '42', '7', 2), '42')

    def test_remembered_identity_projects_to_catalog_without_overriding_exact_ids(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'provider_search_2.sqlite'
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE items (stype TEXT,provider_id TEXT,norm TEXT,year TEXT)')
                db.execute('CREATE TABLE identity_matches (stype TEXT,provider_id TEXT,'
                           'title_key TEXT,year TEXT,tmdb_id TEXT)')
                db.execute("INSERT INTO items VALUES ('movie','7','chappie','2015')")
                db.execute("INSERT INTO identity_matches VALUES ('movie','7','chappie','2015','198184')")
            def context():
                return {'addon': SimpleNamespace(getAddonInfo=lambda _: root),
                        'xbmcvfs': SimpleNamespace(translatePath=lambda value: value)}
            self.assertEqual(content_state.provider_tmdb_id(context(), 'movie', '7', 2), '198184')
            self.assertEqual(content_state.provider_tmdb_id(context(), 'movie', '7', 2, '99'), '99')
            with sqlite3.connect(path) as db:
                db.execute("UPDATE items SET norm='different' WHERE provider_id='7'")
            self.assertEqual(content_state.provider_tmdb_id(context(), 'movie', '7', 2), '')

    def test_remembered_identity_refreshes_after_index_changes(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'provider_search_2.sqlite'
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE items (stype TEXT,provider_id TEXT,norm TEXT,year TEXT)')
                db.execute('CREATE TABLE identity_matches (stype TEXT,provider_id TEXT,title_key TEXT,year TEXT,tmdb_id TEXT)')
                db.execute("INSERT INTO items VALUES ('series','7','example','2025')")
            g = {'addon': SimpleNamespace(getAddonInfo=lambda _: root),
                 'xbmcvfs': SimpleNamespace(translatePath=lambda value: value)}
            self.assertEqual(content_state.provider_tmdb_id(g, 'series', '7', 2), '')
            with sqlite3.connect(path) as db:
                db.execute("INSERT INTO identity_matches VALUES ('series','7','example','2025','42')")
            self.assertEqual(content_state.provider_tmdb_id(g, 'series', '7', 2), '42')
            with sqlite3.connect(path) as db:
                db.execute("UPDATE items SET norm='different' WHERE provider_id='7'")
            self.assertEqual(content_state.provider_tmdb_id(g, 'series', '7', 2), '')

    def test_clean_profile_recovers_series_identity_from_metadata_and_inventory(self):
        import series_state
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'provider_search_1.sqlite'
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE items (stype TEXT,provider_id TEXT,title TEXT,norm TEXT,year TEXT)')
                db.executemany('INSERT INTO items VALUES (?,?,?,?,?)', [
                    ('series', '10', 'Paradise (2025)', 'paradise 2025', '2025'),
                    ('series', '20', 'Tierra de mafiosos (2025)', 'tierra de mafiosos 2025', '2025')])
            g = {'addon': SimpleNamespace(getAddonInfo=lambda _: root),
                 'xbmcvfs': SimpleNamespace(translatePath=lambda value: value)}
            # These are metadata and watched responses, not identifiers passed to the resolver.
            fixtures = [
                ('10', 'Paradise', {'id': 245927, 'first_air_date': '2025-01-01',
                                  'seasons': [{'season_number': 1, 'episode_count': 8},
                                              {'season_number': 2, 'episode_count': 8}]}, 16),
                ('20', 'Tierra de mafiosos', {'id': 247718, 'first_air_date': '2025-01-01',
                                  'seasons': [{'season_number': 1, 'episode_count': 10},
                                              {'season_number': 2, 'episode_count': 6}]}, 10)]
            for sid, title, response, watched_count in fixtures:
                matches = [{'tmdb_id': str(response['id']), 'title': title, 'year': '2025'}]
                evidence = content_state.series_identity_evidence(title, '2025', matches, response)
                item = {'series_id': sid, 'name': title + ' (2025)', 'year': '2025'}
                rows = [{'season': season['season_number'], 'episode': n,
                         'provider_id': str(1000 + season['season_number'] * 100 + n)}
                        for season in response['seasons'] for n in range(1, season['episode_count'] + 1)]
                inventory = {'complete': True, 'checked_at': time.time(), 'episodes': rows}
                data = {'year': '2025', 'tmdb_id': str(response['id']), '_identity_evidence': evidence}
                self.assertTrue(content_state.remember_verified_series(g, item, data, 1, inventory))
                fresh_g = {'addon': g['addon'], 'xbmcvfs': g['xbmcvfs']}
                resolved = content_state.provider_tmdb_id(fresh_g, 'series', sid, 1)
                watched = {'tmdb:episode:%s:s%s:e%s' % (response['id'], row['season'], row['episode']): True
                           for row in rows[:watched_count]}
                state = series_state.derive_series_state(resolved, sid, inventory,
                    SimpleNamespace(is_watched=lambda *args: False),
                    tmdb_watched_store=SimpleNamespace(_data=watched))
                self.assertEqual((state['watched'], state['total']), (watched_count, 16))
            self.assertIsNone(content_state.series_identity_evidence('Paradise', '2025',
                [{'tmdb_id': '1', 'title': 'Paradise', 'year': '2025'},
                 {'tmdb_id': '2', 'title': 'Paradise', 'year': '2025'}], {}))

    def test_series_identity_rejects_incomplete_stale_or_ambiguous_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'provider_search_1.sqlite'
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE items (stype TEXT,provider_id TEXT,title TEXT,norm TEXT,year TEXT)')
                db.execute("INSERT INTO items VALUES ('series','10','Example (2025)','example 2025','2025')")
            g = {'addon': SimpleNamespace(getAddonInfo=lambda _: root),
                 'xbmcvfs': SimpleNamespace(translatePath=lambda value: value)}
            item = {'series_id': '10', 'name': 'Example (2025)', 'year': '2025'}
            matches = [{'tmdb_id': '42', 'title': 'Example', 'year': '2025'}]
            details = {'id': 42, 'first_air_date': '2025-01-01',
                       'seasons': [{'season_number': 1, 'episode_count': 2}]}
            evidence = content_state.series_identity_evidence('Example', '2025', matches, details)
            data = {'tmdb_id': '42', '_identity_evidence': evidence}
            rows = [{'season': 1, 'episode': 1, 'provider_id': '101'},
                    {'season': 1, 'episode': 2, 'provider_id': '102'}]
            inventory = {'complete': True, 'checked_at': time.time(), 'episodes': rows}
            self.assertFalse(content_state.remember_verified_series(g, item, data, 1,
                dict(inventory, complete=False)))
            self.assertFalse(content_state.remember_verified_series(g, item, data, 1,
                dict(inventory, checked_at=1)))
            self.assertFalse(content_state.remember_verified_series(g, item, data, 1,
                dict(inventory, episodes=rows[:1])))
            self.assertFalse(content_state.remember_verified_series(g,
                dict(item, tmdb_id='99'), data, 1, inventory))
            with sqlite3.connect(path) as db:
                db.execute("INSERT INTO items VALUES ('series','11','Example (2025)','example 2025','2025')")
            self.assertFalse(content_state.remember_verified_series(g, item, data, 1, inventory))

    @unittest.skipIf(os.environ.get('ACTWEETER_RELEASE_CHANNEL') == 'stable',
                     'requires Beta6 XStream identity recovery')
    def test_clean_profile_uses_packaged_enrichment_and_card_routes(self):
        import series_state
        package = os.environ.get('ACTWEETER_XSTREAM_LIVE_ZIP')
        self.assertTrue(package, 'exact candidate ZIP required')
        with zipfile.ZipFile(package) as archive:
            tree = ast.parse(archive.read('plugin.video.xstream-pro/resources/lib/premium_routes.py'))
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name in ('enrich', 'listitem')]
        class Tag:
            def __getattr__(self, name):
                return lambda *args: None
        class Card:
            def __init__(self): self.properties = {}
            def setProperty(self, key, value): self.properties[key] = value
            def getVideoInfoTag(self): return Tag()
            def setArt(self, value): pass
        fixtures = {
            'Paradise': {'id': 245927, 'first_air_date': '2025-01-01',
                         'seasons': [{'season_number': 1, 'episode_count': 8},
                                     {'season_number': 2, 'episode_count': 8}]},
            'Tierra de mafiosos': {'id': 247718, 'first_air_date': '2025-01-01',
                                   'seasons': [{'season_number': 1, 'episode_count': 10},
                                               {'season_number': 2, 'episode_count': 6}]}}
        cache, calls = {}, []
        tmdb = SimpleNamespace(
            paged=lambda path, media, params, ttl: (calls.append(params['query']) or {'total_pages': 1, 'results': [
                {'tmdb_id': str(fixtures[params['query']]['id']), 'title': params['query'], 'year': '2025'}]}),
            details=lambda media, ident: next(v for v in fixtures.values() if str(v['id']) == str(ident)),
            image_url=lambda value, *args: '', fanart_url=lambda value: '')
        namespace = {'content_state': content_state, 're': re, 'time': time,
                     'normalized': lambda x: content_state._title_key(x),
                     'number': lambda value: int(value or 0), 'backdrop': lambda x: x or '',
                     'provider_id': lambda item, kind: str(item['series_id']),
                     '_performance_call': lambda g, name, fn, *args, **kwargs: fn(*args, **kwargs)}
        exec(compile(ast.Module(body=functions, type_ignores=[]), 'candidate-series', 'exec'), namespace)
        with tempfile.TemporaryDirectory() as root, patch.dict(sys.modules, {'tmdb': tmdb}):
            path = Path(root) / 'provider_search_1.sqlite'
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE items (stype TEXT,provider_id TEXT,title TEXT,norm TEXT,year TEXT)')
                db.executemany('INSERT INTO items VALUES (?,?,?,?,?)', [
                    ('series', '10', 'Paradise (2025)', 'paradise 2025', '2025'),
                    ('series', '20', 'Tierra de mafiosos (2025)', 'tierra de mafiosos 2025', '2025')])
            g = {'addon': SimpleNamespace(getAddonInfo=lambda _: root),
                 'xbmcvfs': SimpleNamespace(translatePath=lambda value: value),
                 '_cache_load': lambda key, **kwargs: cache.get(key),
                 '_cache_save': lambda key, value: cache.__setitem__(key, value),
                 '_new_listitem': lambda *args: Card(), '_log': lambda *args: None,
                 'series_changes': SimpleNamespace(series_state=series_state)}
            for sid, title, count in (('10', 'Paradise', 16), ('20', 'Tierra de mafiosos', 10)):
                response = fixtures[title]
                rows = [{'season': season['season_number'], 'episode': n,
                         'provider_id': str(1000 + season['season_number'] * 100 + n)}
                        for season in response['seasons'] for n in range(1, season['episode_count'] + 1)]
                inventory = {'complete': True, 'checked_at': time.time(), 'episodes': rows}
                watched = {'tmdb:episode:%s:s%s:e%s' % (response['id'], row['season'], row['episode']): True
                           for row in rows[:count]}
                context = {'inventory': {sid: inventory}, 'watched': SimpleNamespace(is_watched=lambda *args: False),
                           'resume': [], 'tmdb_watched': SimpleNamespace(_data=watched)}
                item = {'series_id': sid, 'name': title + ' (2025)', 'year': '2025'}
                enriched = namespace['enrich'](g, item, 'series', {'year': '2025', 'title': item['name']}, [1, 0])
                card = namespace['listitem'](g, item, 'series', enriched, profile_num=1, series_context=context)
                fresh = {'addon': g['addon'], 'xbmcvfs': g['xbmcvfs']}
                self.assertTrue(content_state.provider_tmdb_id(fresh, 'series', sid, 1))
                self.assertEqual(card.properties['XStream.SeriesComplete'], 'true' if count == 16 else 'false')
                self.assertIn('%s/16' % count, card.properties['XStream.SeriesProgressLabel'] if count < 16 else '16/16')
            self.assertEqual(calls, ['Paradise', 'Tierra de mafiosos'])
            cache.clear()
            tmdb.paged = lambda path, media, params, ttl: {'total_pages': 2, 'results': [
                {'tmdb_id': str(fixtures[params['query']]['id']), 'title': params['query'], 'year': '2025'}]}
            uncertain = namespace['enrich'](g, {'series_id': '10', 'name': 'Paradise (2025)'},
                'series', {'year': '2025', 'title': 'Paradise (2025)'}, [1, 0])
            self.assertNotIn('_identity_evidence', uncertain)

    def test_legacy_complete_marks_never_mark_a_new_episode_seen(self):
        g, movies, episodes, _, _ = self.context(
            [{'season': 1, 'episode': 1, 'provider_id': '10'}],
            {'tvshow:42': True, 'season:42:1': True})
        item = {'tmdb_type': 'tv', 'tmdb_id': '42', 'season': 1, 'episode': 2}
        self.assertIsNone(content_state.tmdb_watched_state(g, item, movies, episodes))
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
        self.assertIsNone(content_state.tmdb_watched_state(g, item, movies, episodes))
        record['complete'] = True
        record['checked_at'] = 1
        self.assertIsNone(content_state.tmdb_watched_state(g, item, movies, episodes))

    def test_missing_movie_mark_and_series_inventory_remain_unknown(self):
        g, movies, episodes, record, _ = self.context([], {})
        movie = {'tmdb_type': 'movie', 'tmdb_id': '42'}
        show = {'tmdb_type': 'tv', 'tmdb_id': '42'}
        self.assertIsNone(content_state.tmdb_watched_state(g, movie, movies, episodes))
        self.assertIsNone(content_state.tmdb_watched_state(g, show, movies, episodes))
        g['series_changes'] = None
        self.assertIsNone(content_state.tmdb_watched_state(g, show, movies, episodes))

    def test_malformed_namespaced_episode_mark_remains_unknown(self):
        g, movies, episodes, _, _ = self.context([], {'tmdb:episode:42:s1:e2': 'true'})
        episode = {'tmdb_type': 'tv', 'tmdb_id': '42', 'season': 1, 'episode': 2}
        self.assertIsNone(content_state.tmdb_watched_state(g, episode, movies, episodes))

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

    @unittest.skipIf(os.environ.get('ACTWEETER_RELEASE_CHANNEL') == 'stable',
                     'requires the Beta4 XStream package')
    def test_packaged_series_catalog_uses_persisted_identity(self):
        package = os.environ.get('ACTWEETER_XSTREAM_LIVE_ZIP')
        self.assertTrue(package, 'exact candidate ZIP required')
        with zipfile.ZipFile(package) as archive:
            tree = ast.parse(archive.read('plugin.video.xstream-pro/resources/lib/addon.py'))
        method = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                      and n.name == 'xtream_streams')
        calls = [n for n in ast.walk(method) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute) and n.func.attr == 'resolve_tmdb_id']
        self.assertTrue(any(len(call.args) == 3 and isinstance(call.args[2], ast.Call)
                            and isinstance(call.args[2].func, ast.Attribute)
                            and call.args[2].func.attr == 'provider_tmdb_id' for call in calls))

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

