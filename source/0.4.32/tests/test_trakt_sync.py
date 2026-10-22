"""Synthetic API data only: no credentials, network, installed profiles or playback."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('trakt_sync', ROOT / 'addons/service.actweeter/resources/lib/trakt_sync.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)

EARLY = '2026-10-20T10:00:00Z'
LATE = '2026-10-21T10:00:00Z'


class API:
    def __init__(self):
        self.calls = []
        self.responses = {
            '/users/settings': ({'user': {'ids': {'slug': 'synthetic-user'}}}, 1),
            '/sync/last_activities': ({'all': LATE}, 1),
            '/sync/watched/movies': ([{'movie': {'ids': {'tmdb': 42, 'imdb': 'tt42'}},
                                      'last_watched_at': EARLY}], 1),
            '/sync/watched/shows': ([{'show': {'ids': {'tmdb': 42}}, 'seasons': [
                {'number': 0, 'episodes': [{'number': 1, 'last_watched_at': EARLY}]}]}], 1),
            '/sync/playback/movies': ([{'movie': {'ids': {'tmdb': 42, 'imdb': 'tt42'}},
                                       'progress': 43, 'paused_at': LATE}], 1),
            '/sync/playback/episodes': ([], 1),
            '/sync/history/movies': ([{'movie': {'ids': {'tmdb': 42}},
                                      'id': 1, 'watched_at': EARLY}], 1),
            '/sync/history/episodes': ([], 1),
        }

    def get(self, path, params):
        self.calls.append((path, params))
        response = self.responses[path]
        return copy.deepcopy(response(params) if callable(response) else response)


def catalog(kind='movie', provider_id='7', **kwargs):
    result = {'kind': kind, 'provider_id': provider_id, 'confidence': 'verified', 'profile': '1',
              'duration_seconds': 1000}
    if kind == 'episode':
        result.update(show_ids={'tmdb': '42'}, season=0, episode=1)
    else:
        result['ids'] = {'tmdb': '42', 'imdb': 'tt42'}
    result.update(kwargs)
    return result


class TraktSyncTests(unittest.TestCase):
    def setUp(self):
        self.api = API()

    def plan(self, records=None, **kwargs):
        return sync.import_plan(sync.fetch_snapshot(self.api.get), records or [catalog(), catalog('episode')],
                                profile='1', account='synthetic-user', **kwargs)

    def test_id_validation(self):
        self.assertEqual(sync.normalize_ids({'tmdb': True, 'tvdb': -1, 'imdb': 'TT0042',
                                             'trakt': '0002', 'url': 'private'}),
                         {'imdb': 'tt0042', 'trakt': '2'})

    def test_no_title_identity(self):
        self.assertIsNone(sync.identity('movie', {'title': 'Matching title'}))
        self.assertIsNone(sync.identity('movie', {'tvdb': 42}))

    def test_episode_does_not_reuse_series_tmdb_as_movie(self):
        episode = sync.identity('episode', {'tmdb': 99}, show_ids={'tmdb': 42}, season=0, episode=1)
        self.assertNotEqual(episode['key'], sync.identity('movie', {'tmdb': 42})['key'])
        self.assertEqual(episode['ids'], {'tmdb': '42'})

    def test_episode_requires_show_and_numbers(self):
        for values in ({'show_ids': {'tmdb': 42}, 'episode': 1},
                       {'show_ids': {'tmdb': 42}, 'season': 1, 'episode': 0},
                       {'show_ids': {}, 'season': 1, 'episode': 1}):
            self.assertIsNone(sync.identity('episode', **values))

    def test_snapshot_has_explicit_episode_not_completed_series(self):
        snapshot = sync.fetch_snapshot(self.api.get)
        episode = snapshot['records']['episode:tmdb:42:s0:e1']
        self.assertEqual(episode['watched_at'], EARLY)
        self.assertNotIn('show:tmdb:42', snapshot['records'])

    def test_watched_series_requests_progress_inventory(self):
        sync.fetch_snapshot(self.api.get)
        query = next(params for path, params in self.api.calls if path == '/sync/watched/shows')
        self.assertEqual(query, {'page': 1, 'limit': 100, 'extended': 'progress'})

    def test_native_transport_get_only_and_no_url_or_token_export(self):
        snapshot = sync.fetch_snapshot(self.api.get)
        self.assertEqual(len(self.api.calls), 10)
        self.assertNotIn('token', str(snapshot))
        self.assertNotIn('url', str(snapshot))
        self.assertTrue(all(p.startswith(('/sync/', '/users/')) for p, _ in self.api.calls))

    def test_history_preserves_multiple_plays_and_deduplicates_event_id(self):
        row = self.api.responses['/sync/history/movies'][0][0]
        self.api.responses['/sync/history/movies'] = ([row, row, dict(row, id=2, watched_at=LATE)], 1)
        self.assertEqual(len(sync.fetch_snapshot(self.api.get)['history']), 2)

    def test_complete_pagination(self):
        self.api.responses['/sync/history/movies'] = lambda params: ([{
            'movie': {'ids': {'tmdb': 42}}, 'watched_at': EARLY, 'id': params['page']}], 3)
        snapshot = sync.fetch_snapshot(self.api.get)
        self.assertEqual(len(snapshot['history']), 3)

    def test_missing_page_is_not_an_empty_snapshot(self):
        self.api.responses['/sync/history/movies'] = ([], 2)
        with self.assertRaises(sync.IncompleteSnapshot): sync.fetch_snapshot(self.api.get)

    def test_empty_final_page_is_not_a_complete_snapshot(self):
        self.api.responses['/sync/history/movies'] = lambda params: (
            ([{'movie': {'ids': {'tmdb': 42}}, 'watched_at': EARLY, 'id': 1}], 2)
            if params['page'] == 1 else ([], 2))
        with self.assertRaises(sync.IncompleteSnapshot): sync.fetch_snapshot(self.api.get)

    def test_invalid_page_count_and_limit_fail_closed(self):
        for count in ('2', 1001):
            self.api.responses['/sync/history/movies'] = ([], count)
            with self.assertRaises(sync.IncompleteSnapshot): sync.fetch_snapshot(self.api.get)

    def test_empty_collection_with_zero_pages_is_a_valid_empty_result(self):
        self.api.responses['/sync/history/movies'] = ([], 0)
        snapshot = sync.fetch_snapshot(self.api.get)
        self.assertTrue(snapshot['complete'])
        self.assertEqual(snapshot['history'], [])

    def test_pages_changed_during_import(self):
        self.api.responses['/sync/history/movies'] = lambda params: ([{
            'movie': {'ids': {'tmdb': 42}}, 'watched_at': EARLY, 'id': params['page']}],
            2 if params['page'] == 1 else 3)
        with self.assertRaises(sync.IncompleteSnapshot): sync.fetch_snapshot(self.api.get)

    def test_cancellation(self):
        with self.assertRaises(sync.IncompleteSnapshot):
            sync.fetch_snapshot(self.api.get, cancelled=lambda: True)

    def test_remote_activity_changed(self):
        stamps = iter([({'all': EARLY}, 1), ({'all': LATE}, 1)])
        self.api.responses['/sync/last_activities'] = lambda _: next(stamps)
        with self.assertRaises(sync.IncompleteSnapshot): sync.fetch_snapshot(self.api.get)

    def test_account_change_mid_import_is_rejected(self):
        accounts = iter([({'user': {'ids': {'slug': 'synthetic-user'}}}, 1),
                         ({'user': {'ids': {'slug': 'another-user'}}}, 1)])
        self.api.responses['/users/settings'] = lambda _: next(accounts)
        with self.assertRaises(sync.IncompleteSnapshot): sync.fetch_snapshot(self.api.get)

    def test_network_and_rate_limit_errors_propagate_without_overwrite(self):
        def fail(_): raise TimeoutError('synthetic HTTP failure')
        self.api.responses['/sync/history/movies'] = fail
        with self.assertRaises(TimeoutError): sync.fetch_snapshot(self.api.get)

    def test_auth_failure_does_not_access_other_endpoints(self):
        def fail(_): raise PermissionError('synthetic unauthorized')
        self.api.responses['/users/settings'] = fail
        with self.assertRaises(PermissionError): sync.fetch_snapshot(self.api.get)
        self.assertEqual(len(self.api.calls), 1)

    def test_invalid_timestamp_and_nan_are_not_progress(self):
        for data in ({'progress': float('nan'), 'paused_at': LATE},
                     {'progress': 101, 'paused_at': LATE},
                     {'progress': 40, 'paused_at': 'no date'}):
            self.api.responses['/sync/playback/movies'] = ([dict(data, movie={'ids': {'tmdb': 42}})], 1)
            with self.assertRaises(sync.IncompleteSnapshot): sync.fetch_snapshot(self.api.get)

    def test_watched_without_explicit_episode_inventory_fails_closed(self):
        self.api.responses['/sync/watched/shows'][0][0].pop('seasons')
        with self.assertRaises(sync.IncompleteSnapshot): sync.fetch_snapshot(self.api.get)

    def test_initial_import_is_additive_and_does_not_mutate_local_data(self):
        local = {'unrelated': {'position': 100, 'updated_at': LATE}}
        before = copy.deepcopy(local)
        plan = self.plan(local=local)
        self.assertEqual(local, before)
        self.assertEqual(len(plan['items']), 2)
        self.assertFalse(any('delete' in i for i in plan['items']))

    def test_percent_to_seconds_requires_duration(self):
        plan = self.plan()
        self.assertEqual(plan['items'][0]['position'], 430)
        plan = self.plan([catalog(duration_seconds=None)])
        self.assertNotIn('position', plan['items'][0])
        self.assertEqual(plan['items'][0]['resume_deferred'], 'duration_unknown')

    def test_later_completion_supersedes_old_pause(self):
        self.api.responses['/sync/watched/movies'][0][0]['last_watched_at'] = LATE
        self.api.responses['/sync/playback/movies'][0][0]['paused_at'] = EARLY
        self.assertNotIn('position', self.plan()['items'][0])

    def test_newer_local_progress_is_preserved(self):
        for stamp in (None, LATE):
            plan = self.plan(local={'movie:tmdb:42': {'position': 12, 'updated_at': stamp}})
            self.assertIn('movie:tmdb:42', plan['conflicts'])
            self.assertFalse(any(i['identity']['kind'] == 'movie' for i in plan['items']))

    def test_local_explicit_unwatched_is_a_conflict(self):
        self.assertIn('movie:tmdb:42', self.plan(local={'movie:tmdb:42': {'watched': False}})['conflicts'])

    def test_unavailable_history_survives_provider_change(self):
        snapshot = sync.fetch_snapshot(self.api.get)
        self.assertEqual(len(sync.import_plan(snapshot, [], profile='1', account='synthetic-user')['unavailable']), 2)
        plan = sync.import_plan(snapshot, [catalog(provider_id='999')], profile='1', account='synthetic-user')
        self.assertEqual(plan['items'][0]['provider_id'], '999')
        self.assertEqual(len(snapshot['records']), 2)

    def test_matching_ids_do_not_override_contradictory_ids(self):
        self.assertIn('movie:tmdb:42', self.plan([catalog(ids={'tmdb': 42, 'imdb': 'tt999'})])['conflicts'])

    def test_unverified_title_match_is_not_importable(self):
        plan = self.plan([catalog(confidence='ambiguous')])
        self.assertIn('movie:tmdb:42', plan['unavailable'])

    def test_multiple_versions_are_ambiguous_not_randomly_selected(self):
        self.assertIn('movie:tmdb:42', self.plan([catalog(), catalog(provider_id='8')])['ambiguous'])

    def test_duplicate_provider_rows_do_not_duplicate_operations(self):
        self.assertEqual(len(self.plan([catalog(), catalog()])['items']), 1)

    def test_other_profile_requires_explicit_account_binding(self):
        snapshot = sync.fetch_snapshot(self.api.get)
        with self.assertRaises(ValueError):
            sync.import_plan(snapshot, [], profile='2', account='someone-else')
        with self.assertRaises(ValueError):
            sync.import_plan(snapshot, [], profile='', account='synthetic-user')

    def test_catalog_from_another_or_unknown_profile_is_not_matched(self):
        for profile in ('2', ''):
            self.assertIn('movie:tmdb:42', self.plan([catalog(profile=profile)])['unavailable'])

    def test_tvdb_is_not_a_movie_identity_even_when_other_ids_exist(self):
        self.assertEqual(sync.identity('movie', {'tmdb': 42, 'tvdb': 99})['ids'], {'tmdb': '42'})


if __name__ == '__main__':
    unittest.main()
