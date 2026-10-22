import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/service.actweeter/resources'))
from lib.trakt_resume_bridge import existing_playback_references, stage_resume


class TraktResumeBridgeTests(unittest.TestCase):
    def setUp(self):
        self.movie = {'provider_id': '101', 'identity': {'kind': 'movie', 'ids': {'tmdb': '10'}},
            'position': 300.0, 'duration': 1800.0, 'paused_at': '2026-10-22T12:00:00Z'}
        self.episode = {'provider_id': '202', 'provider_series_id': '55',
            'provider_episode_id': '202',
            'identity': {'kind': 'episode', 'ids': {'tmdb': '70'}, 'season': 0, 'episode': 3},
            'position': 600.0, 'duration': 2400.0, 'paused_at': '2026-10-22T12:00:00Z'}
        self.references = {
            'movie:101': {'confidence': 'verified', 'profile': '2', 'kind': 'movie',
                'provider_id': '101', 'name': 'Movie', 'identity': self.movie['identity'],
                'url': 'https://provider.invalid/movie/101.mp4'},
            'episode:202': {'confidence': 'exact', 'profile': '2', 'kind': 'episode',
                'provider_id': '202', 'series_id': '55', 'ep_id': '202',
                'identity': self.episode['identity'], 'season_num': 0, 'episode_num': 3,
                'name': 'Episode', 'url': 'https://provider.invalid/episode/202.mp4'}}

    def test_stages_movie_in_xstream_format(self):
        result = stage_resume({'profile': '2', 'items': [self.movie]}, self.references, {})
        entry = result['staged']['Movie||https://provider.invalid/movie/101.mp4']
        self.assertEqual((entry['stype'], entry['position'], entry['duration']), ('movie', 300.0, 1800.0))
        self.assertEqual((result['added'], result['updated']), (1, 0))

    def test_stages_episode_with_exact_coordinates(self):
        result = stage_resume({'profile': '2', 'items': [self.episode]}, self.references, {})
        entry = result['staged']['Episode||https://provider.invalid/episode/202.mp4']
        self.assertEqual((entry['stype'], entry['series_id'], entry['season_num'],
                          entry['ep_id'], entry['episode_num']), ('series', '55', 0, '202', 3))

    def test_refuses_wrong_profile_identity_and_episode_coordinates(self):
        for profile, kind, reference in (
                ('1', 'movie', self.references['movie:101']),
                ('2', 'movie', dict(self.references['movie:101'], confidence='title_match')),
                ('2', 'episode', dict(self.references['episode:202'], episode_num=4))):
            item = self.movie if kind == 'movie' else self.episode
            result = stage_resume({'profile': profile, 'items': [item]},
                {kind + ':' + item['provider_id']: reference}, {})
            self.assertEqual(result['added'], 0)
            self.assertEqual(result['deferred'][0]['reason'], 'identity_unverified')

    def test_requires_valid_duration_progress_and_remote_timestamp(self):
        for changes, reason in (({'duration': 0}, 'duration_or_position_invalid'),
                                ({'position': 1700}, 'duration_or_position_invalid'),
                                ({'paused_at': None}, 'remote_timestamp_unknown')):
            item = dict(self.movie, **changes)
            result = stage_resume({'profile': '2', 'items': [item]}, self.references, {})
            self.assertEqual(result['added'], 0)
            self.assertEqual(result['deferred'][0]['reason'], reason)

    def test_local_newer_or_unknown_is_not_overwritten(self):
        key = 'Movie||https://provider.invalid/movie/101.mp4'
        for timestamp, reason in ((1792670401, 'local_is_not_older'),
                                  ('unknown', 'local_timestamp_unknown')):
            local = {key: {'position': 500, 'timestamp': timestamp}}
            result = stage_resume({'profile': '2', 'items': [self.movie]}, self.references, local)
            self.assertEqual(result['staged'][key]['position'], 500)
            self.assertEqual(result['deferred'][0]['reason'], reason)

    def test_newer_remote_updates_only_exact_reference(self):
        key = 'Movie||https://provider.invalid/movie/101.mp4'
        local = {key: {'position': 100, 'timestamp': 1792670399}}
        result = stage_resume({'profile': '2', 'items': [self.movie]}, self.references, local)
        self.assertEqual((result['updated'], result['staged'][key]['position']), (1, 300.0))

    def test_never_fabricates_a_url(self):
        result = stage_resume({'profile': '2', 'items': [self.movie]}, {}, {})
        self.assertEqual(result['staged'], {})
        self.assertEqual(result['deferred'][0]['reason'], 'identity_unverified')

    def test_rejects_conflicting_or_missing_external_identity(self):
        conflict = dict(self.references['movie:101'], identity={'kind': 'movie', 'ids': {'tmdb': '11'}})
        for identity, refs in ((self.movie['identity'], {'movie:101': conflict}),
                                (None, self.references), ({'kind': 'movie', 'ids': {}}, self.references)):
            item = dict(self.movie, identity=identity)
            result = stage_resume({'profile': '2', 'items': [item]}, refs, {})
            self.assertEqual(result['added'], 0)

    def test_movie_and_episode_provider_ids_do_not_collide(self):
        movie = dict(self.movie, provider_id='202')
        movie_ref = dict(self.references['movie:101'], provider_id='202')
        result = stage_resume({'profile': '2', 'items': [movie, self.episode]},
            {'movie:202': movie_ref, 'episode:202': self.references['episode:202']}, {})
        self.assertEqual(result['added'], 2)
        self.assertEqual({record['stype'] for record in result['staged'].values()}, {'movie', 'series'})

    def test_profile_playback_files_supply_only_exact_current_references(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            url = 'https://provider.invalid/movie/u/p/101.mp4'
            (root / 'resume_points_p2.json').write_text(json.dumps({
                'Movie||' + url: {'name': 'Movie', 'url': url, 'stype': 'movie'}}))
            (root / 'watch_history_p2.json').write_text('[]')
            refs, existing = existing_playback_references(folder, '2', [self.movie])
            self.assertEqual(refs['movie:101']['url'], url)
            self.assertIn('Movie||' + url, existing)
            self.assertEqual(existing_playback_references(folder, '1', [self.movie])[0], {})

    def test_episode_reference_is_bound_to_series_season_and_episode(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            url = 'https://provider.invalid/series/u/p/202.mkv'
            (root / 'resume_points_p2.json').write_text(json.dumps({
                'Episode||' + url: {'name': 'Episode', 'url': url, 'stype': 'series',
                    'series_id': '55', 'ep_id': '202', 'season_num': 0, 'episode_num': 3}}))
            (root / 'watch_history_p2.json').write_text('[]')
            refs, _ = existing_playback_references(folder, '2', [self.episode])
            self.assertEqual(refs['episode:202']['episode_num'], 3)

    def test_invalid_profile_and_symlinked_store_are_rejected(self):
        with self.assertRaises(ValueError):
            existing_playback_references('/missing', '0', [self.movie])
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as outside:
            root = Path(folder)
            (root / 'resume_points_p2.json').symlink_to(Path(outside) / 'store.json')
            with self.assertRaises(ValueError):
                existing_playback_references(folder, '2', [self.movie])

if __name__ == '__main__':
    unittest.main()
