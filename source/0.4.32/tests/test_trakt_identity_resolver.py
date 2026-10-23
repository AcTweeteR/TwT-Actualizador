import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'addons/service.actweeter/resources'))
from lib.trakt_identity_resolver import resolve_identities
from lib.trakt_sync import ProviderIndex


class IdentityResolverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for stype in ('movie', 'series'):
            self.write('data_cache_p1_xtream_streams_%s.json' % stype,
                       {'_src': 'host|user|pass', '_data': []})

    def write(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value, ensure_ascii=False))
        return path

    def export(self, title='Café Azul', year=2020, tmdb=42, kind='movies'):
        media_kind = 'movie' if kind == 'movies' else 'show'
        media = {'title' if media_kind == 'movie' else 'name': title,
                 'year': year, 'ids': {'tmdb': tmdb}}
        row = {'movie' if media_kind == 'movie' else 'show': media}
        return {'responses': [{'path': '/sync/history/' + kind, 'data': [row]}]}

    def test_provider_backed_id_is_scoped_and_recomputable(self):
        self.write('data_cache_p1_xtream_streams_movie.json', {'_src': 'https://host.invalid|user|secret',
            '_data': [{'stream_id': 7, 'name': 'Café Azul', 'year': 2020, 'tmdb_id': 42}]})
        self.write('data_cache_p1_xtream_streams_series.json', {'_src': 'https://host.invalid|user|secret',
            '_data': []})
        first = resolve_identities(self.root, profile='1', export_payload=self.export())
        self.assertEqual(first['summary']['verified_movies'], 1)
        record = first['verified'][0]
        self.assertEqual(record['status'], 'VERIFIED')
        self.assertIn('provider_catalog', record['provenance'])
        self.assertNotIn('secret', json.dumps(record))
        self.assertEqual(len(record['catalog_fingerprint']), 64)
        second = resolve_identities(self.root, profile='1', export_payload=self.export())
        self.assertEqual(first['verified'][0]['catalog_fingerprint'],
                         second['verified'][0]['catalog_fingerprint'])
        self.assertTrue(first['verified'][0]['verified_at'])

    def test_exact_title_candidate_never_enters_verified_provider_index(self):
        self.write('data_cache_p1_xtream_streams_movie.json', {'_src': 'host|user|pass',
            '_data': [{'stream_id': 7, 'name': 'Cafe Azul', 'year': 2020}]})
        result = resolve_identities(self.root, profile='1', export_payload=self.export(), include_candidates=True)
        self.assertEqual(result['verified'], [])
        self.assertEqual(result['candidates'][0]['status'], 'CANDIDATE')
        self.assertEqual(result['candidates'][0]['provider_ids'], ['7'])
        index = ProviderIndex(result['verified'], profile='1')
        self.assertEqual(index.match({'kind': 'movie', 'ids': {'tmdb': '42'}})[0], 'unavailable')

    def test_candidate_scan_is_opt_in_for_preview_not_sync_cycles(self):
        self.write('data_cache_p1_xtream_streams_movie.json', {'_src': 'host|user|pass',
            '_data': [{'stream_id': 7, 'name': 'Cafe Azul', 'year': 2020}]})
        result = resolve_identities(self.root, profile='1', export_payload=self.export())
        self.assertEqual(result['candidates'], [])
        self.assertEqual(result['summary']['candidate_scan'], 'not_requested')

    def test_redacted_catalog_cannot_claim_provider_scope(self):
        self.write('data_cache_p1_xtream_streams_movie.json', {'_src': 'redacted',
            '_data': [{'stream_id': 7, 'name': 'Film', 'tmdb_id': 42}]})
        result = resolve_identities(self.root, profile='1')
        self.assertFalse(result['summary']['provider_scope_available'])
        self.assertEqual(result['verified'], [])

    def test_year_and_ambiguity_preserve_candidates_without_verification(self):
        self.write('data_cache_p1_xtream_streams_movie.json', {'_src': 'host|user|pass',
            '_data': [{'stream_id': 7, 'name': 'Cafe Azul', 'year': 2020},
                      {'stream_id': 8, 'name': 'Café Azul', 'year': 2020},
                      {'stream_id': 9, 'name': 'Café Azul', 'year': 1998}]})
        result = resolve_identities(self.root, profile='1', export_payload=self.export(), include_candidates=True)
        self.assertEqual(result['candidates'][0]['provider_ids'], ['7', '8'])
        self.assertEqual(result['verified'], [])

    def test_xstream_cache_identity_matches_trakt_without_title_only_join(self):
        self.write('data_cache_p1_xtream_streams_movie.json', {'_src': 'host|user|pass',
            '_data': [{'stream_id': 7, 'name': 'Título español', 'year': 2020}]})
        self.write('data_cache_p1_premium_meta_movie_7_es.json',
                   {'expires': time.time() + 3600,
                    'data': {'title': 'Café Azul', 'tmdb_id': 42, 'imdb_id': 'tt0000042'}})
        result = resolve_identities(self.root, profile='1', export_payload=self.export(), include_candidates=True)
        self.assertEqual(len(result['verified']), 1)
        self.assertEqual(result['verified'][0]['provider_id'], '7')
        self.assertEqual(result['verified'][0]['verification_method'], 'XSTREAM_MATCHED')
        self.assertIn('xstream_premium_cache', result['verified'][0]['provenance'])
        self.assertEqual(result['verified'][0]['ids']['tmdb'], '42')
        trakt_only = {'responses': [{'path': '/sync/history/movies', 'data': [
            {'movie': {'title': 'Café Azul', 'year': 2020, 'ids': {'trakt': 456}}}]}]}
        candidate = resolve_identities(self.root, profile='1', export_payload=trakt_only,
                                       include_candidates=True)
        self.assertEqual(candidate['verified'], [])
        self.assertEqual(candidate['candidates'][0]['provider_ids'], ['7'])
        self.assertEqual(candidate['candidates'][0]['ids'], {'trakt': '456'})

    def test_xstream_cache_year_conflict_is_never_verified(self):
        self.write('data_cache_p1_xtream_streams_movie.json', {'_src': 'host|user|pass',
            '_data': [{'stream_id': 7, 'name': 'Café Azul', 'year': 2020}]})
        self.write('data_cache_p1_premium_meta_movie_7_es.json',
                   {'expires': time.time() + 3600,
                    'data': {'title': 'Café Azul', 'tmdb_id': 42}})
        export = self.export(year=2021)
        result = resolve_identities(self.root, profile='1', export_payload=export)
        self.assertEqual(result['verified'], [])
        self.assertIn('trakt_identity_year_or_id_disagrees',
                      {row['reason'] for row in result['conflicts']})

    def test_expired_xstream_cache_cannot_authorize_restore(self):
        self.write('data_cache_p1_xtream_streams_movie.json', {'_src': 'host|user|pass',
            '_data': [{'stream_id': 7, 'name': 'Café Azul', 'year': 2020}]})
        self.write('data_cache_p1_premium_meta_movie_7_es.json',
                   {'expires': time.time() - 1,
                    'data': {'title': 'Café Azul', 'tmdb_id': 42}})
        result = resolve_identities(self.root, profile='1', export_payload=self.export())
        self.assertEqual(result['verified'], [])

    def test_nonfinite_xstream_cache_expiry_is_rejected(self):
        self.write('data_cache_p1_xtream_streams_movie.json', {'_src': 'host|user|pass',
            '_data': [{'stream_id': 7, 'name': 'Café Azul', 'year': 2020}]})
        self.write('data_cache_p1_premium_meta_movie_7_es.json',
                   {'expires': float('nan'),
                    'data': {'title': 'Café Azul', 'tmdb_id': 42}})
        result = resolve_identities(self.root, profile='1', export_payload=self.export())
        self.assertEqual(result['verified'], [])

    def test_cached_external_id_collision_excludes_every_provider_item(self):
        self.write('data_cache_p1_xtream_streams_movie.json', {'_src': 'host|user|pass',
            '_data': [{'stream_id': 7, 'name': 'Café Azul', 'year': 2020},
                      {'stream_id': 8, 'name': 'Café Azul', 'year': 2020}]})
        for provider_id in ('7', '8'):
            self.write('data_cache_p1_premium_meta_movie_%s_es.json' % provider_id,
                       {'expires': time.time() + 3600,
                        'data': {'title': 'Café Azul', 'tmdb_id': 42}})
        result = resolve_identities(self.root, profile='1', export_payload=self.export())
        self.assertEqual(result['verified'], [])
        self.assertEqual({row['reason'] for row in result['conflicts']},
                         {'external_id_multiple_provider_items'})

    def test_cached_identity_conflicting_with_provider_id_is_rejected(self):
        self.write('data_cache_p1_xtream_streams_movie.json', {'_src': 'host|user|pass',
            '_data': [{'stream_id': 7, 'name': 'Café Azul', 'year': 2020, 'tmdb_id': 99}]})
        self.write('data_cache_p1_premium_meta_movie_7_es.json',
                   {'expires': time.time() + 3600,
                    'data': {'title': 'Café Azul', 'tmdb_id': 42}})
        result = resolve_identities(self.root, profile='1', export_payload=self.export())
        self.assertEqual(result['verified'], [])
        self.assertIn('external_sources_disagree',
                      {row['reason'] for row in result['conflicts']})

    def test_external_id_collision_is_conflict_and_excluded(self):
        self.write('data_cache_p1_xtream_streams_movie.json', {'_src': 'host|user|pass',
            '_data': [{'stream_id': 7, 'name': 'First', 'tmdb_id': 42},
                      {'stream_id': 8, 'name': 'Second', 'tmdb_id': 42}]})
        result = resolve_identities(self.root, profile='1')
        self.assertEqual(result['verified'], [])
        self.assertEqual({x['provider_id'] for x in result['conflicts']}, {'7', '8'})

    def test_conflicting_trakt_years_are_not_joined_as_a_candidate(self):
        self.write('data_cache_p1_xtream_streams_movie.json', {'_src': 'host|user|pass',
            '_data': [{'stream_id': 7, 'name': 'Same film', 'year': 2020}]})
        export = {'responses': [{'path': '/sync/history/movies', 'data': [
            {'movie': {'title': 'Same film', 'year': 2020, 'ids': {'tmdb': 42}}},
            {'movie': {'title': 'Same film', 'year': 2021, 'ids': {'tmdb': 42}}}]}]}
        result = resolve_identities(self.root, profile='1', export_payload=export,
                                    include_candidates=True)
        self.assertEqual(result['candidates'], [])
        self.assertIn('trakt_years_disagree', {x['reason'] for x in result['conflicts']})

    def test_disagreeing_provider_details_are_reported_as_conflict(self):
        self.write('data_cache_p1_xtream_streams_movie.json', {'_src': 'host|user|pass',
            '_data': [{'stream_id': 7, 'name': 'Film', 'tmdb_id': 42}]})
        self.write('data_cache_p1_vod_info_7.json', {
            'movie_data': {'stream_id': 7, 'name': 'Film'}, 'info': {'tmdb_id': 99}})
        result = resolve_identities(self.root, profile='1', include_candidates=True)
        self.assertEqual(result['verified'], [])
        self.assertEqual(result['conflicts'][0]['reason'], 'external_sources_disagree')

    def test_profile_scope_isolated_and_catalog_change_invalidates_fingerprint(self):
        self.write('data_cache_p1_xtream_streams_movie.json', {'_src': 'host|user|pass',
            '_data': [{'stream_id': 7, 'name': 'Film', 'tmdb_id': 42}]})
        self.write('data_cache_p2_xtream_streams_movie.json', {'_src': 'other|user|pass',
            '_data': [{'stream_id': 7, 'name': 'Film', 'tmdb_id': 42}]})
        self.write('data_cache_p2_xtream_streams_series.json', {'_src': 'other|user|pass',
            '_data': []})
        one = resolve_identities(self.root, profile='1')['verified'][0]
        two = resolve_identities(self.root, profile='2')['verified'][0]
        self.assertNotEqual(one['provider_scope'], two['provider_scope'])
        self.write('data_cache_p1_xtream_streams_movie.json', {'_src': 'host|user|pass',
            '_data': [{'stream_id': 7, 'name': 'Film', 'tmdb_id': 43}]})
        changed = resolve_identities(self.root, profile='1')['verified'][0]
        self.assertNotEqual(one['catalog_fingerprint'], changed['catalog_fingerprint'])
        self.assertEqual(changed['ids']['tmdb'], '43')

    def test_different_movie_and_series_provider_scopes_fail_closed(self):
        self.write('data_cache_p1_xtream_streams_movie.json', {'_src': 'host|user|pass',
            '_data': [{'stream_id': 7, 'name': 'Film', 'tmdb_id': 42}]})
        self.write('data_cache_p1_xtream_streams_series.json', {'_src': 'other|user|pass',
            '_data': [{'series_id': 9, 'name': 'Show', 'tmdb_id': 99}]})
        result = resolve_identities(self.root, profile='1')
        self.assertFalse(result['summary']['provider_scope_available'])
        self.assertEqual(result['verified'], [])


if __name__ == '__main__':
    unittest.main()
