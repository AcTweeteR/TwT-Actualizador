import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'addons/service.actweeter/resources'))
sys.path.insert(0, str(ROOT / 'addons/service.actweeter/resources/lib'))
sys.path.insert(0, str(ROOT / 'third_party/xstream'))
from lib.trakt_restore_importer import prepare_tmdb_restore, preview_tmdb_changes
from trakt_snapshot import export_snapshot


class TmdbProjectionTests(unittest.TestCase):
    def export(self, root):
        activity_calls = 0

        def get(path, params):
            nonlocal activity_calls
            if path == '/users/settings':
                return {'user': {'ids': {'slug': 'test-account'}}}, 1
            if path == '/sync/last_activities':
                activity_calls += 1
                return {'all': '2026-10-23T10:00:00Z'}, 1
            rows = []
            if path == '/sync/watched/movies':
                rows = [
                    {'movie': {'ids': {'tmdb': 10, 'imdb': 'tt10'}},
                     'last_watched_at': '2026-10-22T10:00:00Z'},
                    {'movie': {'ids': {'imdb': 'tt11'}},
                     'last_watched_at': '2026-10-22T10:00:00Z'},
                ]
            elif path == '/sync/watched/shows':
                rows = [{'show': {'ids': {'tmdb': 20}}, 'seasons': [
                    {'number': 0, 'episodes': [{'number': 1,
                     'last_watched_at': '2026-10-22T10:00:00Z'}]},
                    {'number': 1, 'episodes': [{'number': 2,
                     'last_watched_at': '2026-10-22T10:00:00Z'}]},
                ]}]
            elif path == '/sync/playback/movies':
                rows = [{'movie': {'ids': {'tmdb': 30}}, 'progress': 24.0,
                         'paused_at': '2026-10-22T10:00:00Z'}]
            elif path == '/sync/playback/episodes':
                rows = [{'show': {'ids': {'tmdb': 20}},
                         'episode': {'season': 1, 'number': 3},
                         'progress': 31.0, 'paused_at': '2026-10-22T10:00:00Z'}]
            return rows, {'page': params['page'], 'limit': 100,
                          'page_count': 1, 'item_count': len(rows)}

        return export_snapshot(get, root, '1')

    def test_watched_projection_needs_tmdb_only_and_defers_playback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.export(root / 'exports')
            export = next((root / 'exports').glob('snapshot-*'))
            plan = prepare_tmdb_restore(export, profile='1', account='test-account')
            self.assertEqual(plan['summary']['watched_tmdb_records'], 3)
            self.assertEqual(plan['summary']['missing_tmdb_identity'], 1)
            self.assertEqual(plan['summary']['playback_deferred_without_provider_url'], 2)
            self.assertEqual({item['identity']['kind'] for item in plan['items']},
                             {'movie', 'episode'})
            preview = preview_tmdb_changes(plan, root / 'no-provider', profile='1')
            self.assertEqual((preview['movies_new'], preview['episodes_new']), (1, 2))
            self.assertEqual((preview['already_local'], preview['conflicts']), (0, 0))

    def test_preview_preserves_existing_local_marks_and_reports_tombstones(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.export(root / 'exports')
            export = next((root / 'exports').glob('snapshot-*'))
            plan = prepare_tmdb_restore(export, profile='1', account='test-account')
            (root / 'watched_movies_p1.json').write_text(json.dumps({
                'tmdb:movie:10': True,
                'tmdb:episode:20:s0:e1': False,
            }))
            (root / 'watched_episodes_p1.json').write_text(json.dumps({
                '20': {'1': ['2']},
            }))
            before = {path.name: path.read_bytes() for path in root.glob('*.json')}
            preview = preview_tmdb_changes(plan, root, profile='1')
            self.assertEqual(preview['movies_new'], 0)
            self.assertEqual(preview['episodes_new'], 1)
            self.assertEqual(preview['already_local'], 1)
            self.assertEqual(preview['conflicts'], 1)
            self.assertEqual(preview['episodes_new'], 1)
            self.assertEqual(before, {path.name: path.read_bytes()
                                      for path in root.glob('*.json')})

    def test_provider_numeric_ids_do_not_count_as_tmdb_watched(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.export(root / 'exports')
            export = next((root / 'exports').glob('snapshot-*'))
            plan = prepare_tmdb_restore(export, profile='1', account='test-account')
            (root / 'watched_movies_p1.json').write_text(json.dumps({'10': True}))
            (root / 'watched_episodes_p1.json').write_text(json.dumps({
                '20': {'1': ['2']},
            }))
            preview = preview_tmdb_changes(plan, root, profile='1')
            self.assertEqual((preview['movies_new'], preview['episodes_new']), (1, 2))
            self.assertEqual((preview['already_local'], preview['conflicts']), (0, 0))


if __name__ == '__main__':
    unittest.main()
