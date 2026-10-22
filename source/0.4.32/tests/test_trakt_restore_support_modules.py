"""Restore support modules are packaged and operate only on staged files."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

LIB = Path(__file__).resolve().parents[1] / 'addons/service.actweeter/resources/lib'
sys.path.insert(0, str(LIB.parent))
from lib.trakt_provider_index import verified_vod_records  # noqa: E402
from lib.trakt_restore_transaction import stage_restore  # noqa: E402


class RestoreSupportModuleTests(unittest.TestCase):
    def test_vod_index_requires_cache_identity_to_match_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            good = {'info': {'tmdb_id': 123, 'duration_secs': 3600},
                    'movie_data': {'stream_id': 45}}
            stale = {'info': {'tmdb_id': 999}, 'movie_data': {'stream_id': 99}}
            (root / 'data_cache_p1_vod_info_45.json').write_text(json.dumps(good))
            (root / 'data_cache_p1_vod_info_46.json').write_text(json.dumps(stale))
            records = verified_vod_records(root, profile='1')
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['provider_id'], '45')
        self.assertEqual(records[0]['ids'], {'tmdb': '123'})

    def test_restore_stages_watched_states_without_touching_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            movie_source = root / 'watched_movies_p1.json'
            episode_source = root / 'watched_episodes_p1.json'
            movie_source.write_text('{"old": true}')
            episode_source.write_text('{"7": {"1": ["8"]}}')
            original_movie, original_episode = movie_source.read_bytes(), episode_source.read_bytes()
            staging = root / 'stage'
            staging.mkdir()
            plan = {'profile': '1', 'account': 'acct', 'items': [
                {'identity': {'kind': 'movie'}, 'provider_id': '45', 'watched': True},
                {'identity': {'kind': 'episode', 'season': 1}, 'provider_id': '99',
                 'provider_series_id': '7', 'provider_episode_id': '99', 'watched': True}]}

            result = stage_restore(plan, profile='1', account='acct',
                                   movie_source=movie_source, episode_source=episode_source,
                                   staging_directory=staging)
            staged_movie = json.loads(Path(result['movie_path']).read_text())
            staged_episode = json.loads(Path(result['episode_path']).read_text())

            self.assertEqual(result['movies'], 1)
            self.assertEqual(result['episodes'], 1)
            self.assertTrue(staged_movie['45'])
            self.assertEqual(staged_episode['7']['1'], ['8', '99'])
            self.assertEqual(movie_source.read_bytes(), original_movie)
            self.assertEqual(episode_source.read_bytes(), original_episode)


if __name__ == '__main__':
    unittest.main()
