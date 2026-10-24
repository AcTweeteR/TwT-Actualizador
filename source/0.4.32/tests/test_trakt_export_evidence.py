"""Snapshot transcript regressions: synthetic shapes, never private exports."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from test_trakt_sync import sync, API, EARLY, LATE
from test_trakt_snapshot import exporter


def capture(api):
    with tempfile.TemporaryDirectory() as tmp:
        summary = exporter.export_snapshot(api, tmp, '1')
        payload = json.loads(next(Path(tmp).glob('*/snapshot.json')).read_text())
    return payload, summary


def historic(history_movies, with_reference=False):
    movies = [{'movie': {'ids': {'tmdb': 10000+i}}, 'last_watched_at': EARLY} for i in range(1028)]
    shows = [{'show': {'ids': {'tmdb': 20000+i}}, 'seasons': [{'number': 1,
        'episodes': [{'number': e+1, 'last_watched_at': EARLY}
                     for e in range(47 if i < 14 else 46)]}]} for i in range(17)]
    assert sum(len(s['seasons'][0]['episodes']) for s in shows) == 796
    responses = {'/sync/watched/movies': movies, '/sync/watched/shows': shows,
                 '/sync/history/movies': [{'movie': {'ids': {'tmdb': 10000}}, 'id': i+1,
                                            'watched_at': EARLY} for i in range(history_movies)],
                 '/sync/history/episodes': [{'show': {'ids': {'tmdb': 20000}},
                    'episode': {'season': 1, 'number': 1}, 'id': 100000+i,
                    'watched_at': EARLY} for i in range(1390)],
                 '/sync/playback/movies': [{'movie': {'ids': {'tmdb': 30000+i}},
                    'progress': 40, 'paused_at': LATE} for i in range(6)],
                 '/sync/playback/episodes': []}
    def get(path, params):
        if path == '/users/settings': return {'user': {'ids': {'slug': 'synthetic-user'}}}, 1
        if path == '/sync/last_activities': return {'all': LATE}, 1
        data = responses[path]; page = params['page']
        return data[(page-1)*100:page*100], {'page': page, 'limit': 100,
            'page_count': (len(data)+99)//100, 'item_count': len(data)}
    payload, manifest = capture(get)
    reference = copy.deepcopy(payload), dict(manifest)
    payload['schema_version'] = 1; payload['snapshot'].pop('complete')
    payload['responses'] = [row for row in payload['responses'] if row['path'] != '/users/settings']
    for row in payload['responses']: row.pop('pagination', None)
    manifest = dict(manifest, responses=len(payload['responses']))
    manifest.pop('complete'); manifest.pop('contract_version')
    return (payload, manifest, reference) if with_reference else (payload, manifest)


class ExportEvidenceTests(unittest.TestCase):
    def verify(self, payload, manifest, reference=None):
        return sync.validate_export(payload, manifest, profile='1', account='synthetic-user', legacy_reference=reference)

    def test_three_historical_shapes_replay_without_mutating_originals(self):
        for events in (1844, 1845, 1845):
            with self.subTest(history=events+1390):
                payload, manifest, reference = historic(events, with_reference=True)
                before = copy.deepcopy(payload)
                result = self.verify(payload, manifest, reference)
                self.assertTrue(result['complete']); self.assertEqual(len(result['records']), 1830)
                self.assertEqual(len(result['history']), events+1390)
                self.assertEqual(len(payload['responses']), 49)
                self.assertEqual(payload, before); self.assertNotIn('complete', payload['snapshot'])

    def test_complete_flag_and_checksum_are_not_evidence(self):
        payload, manifest = capture(API().get)
        payload['responses'] = []
        manifest['responses'] = 0
        with self.assertRaises(sync.IncompleteSnapshot): self.verify(payload, manifest)

    def test_missing_duplicate_or_reordered_pages_fail(self):
        original, manifest = historic(1845)
        for mode in ('missing', 'duplicate', 'reorder'):
            with self.subTest(mode=mode):
                payload = copy.deepcopy(original)
                if mode == 'missing': payload['responses'].pop(4)
                if mode == 'duplicate': payload['responses'][4] = copy.deepcopy(payload['responses'][3])
                if mode == 'reorder': payload['responses'][3:5] = payload['responses'][3:5][::-1]
                with self.assertRaises(sync.IncompleteSnapshot): self.verify(payload, manifest)

    def test_snapshot_and_manifest_must_match_replayed_data(self):
        original, manifest = capture(API().get)
        for mode in ('data', 'count', 'complete', 'pages'):
            with self.subTest(mode=mode):
                payload, summary = copy.deepcopy(original), dict(manifest)
                if mode == 'data': payload['snapshot']['records'].clear()
                if mode == 'count': summary['history'] += 1
                if mode == 'complete': summary['complete'] = False
                if mode == 'pages': next(row for row in payload['responses'] if row.get('pagination'))['pages'] = 7
                with self.assertRaises(sync.IncompleteSnapshot): self.verify(payload, summary)

    def test_actual_applied_limit_and_item_total_detect_truncated_last_page(self):
        api = API()
        base = api.get
        def truncated(path, params):
            rows, metadata = base(path, params)
            if path == '/sync/history/movies': metadata['item_count'] = 2
            return rows, metadata
        with self.assertRaises(sync.IncompleteSnapshot): capture(truncated)

    def test_account_and_profile_binding_are_not_inferred_from_manifest(self):
        payload, manifest = capture(API().get)
        for field, value in [('account', 'different-user'), ('profile', '2')]:
            with self.subTest(field=field):
                args = dict(profile='1', account='synthetic-user'); args[field] = value
                with self.assertRaises(PermissionError): sync.validate_export(payload, manifest, **args)

    def test_failed_json_does_not_create_empty_verified_export(self):
        def malformed(path, params):
            if path == '/users/settings': return {'user': {'ids': {'slug': 'synthetic-user'}}}, 1
            if path == '/sync/last_activities': return {'all': LATE}, 1
            raise json.JSONDecodeError('invalid', '', 0)
        with self.assertRaises(json.JSONDecodeError): capture(malformed)

    def test_page_metadata_is_required_for_new_exports(self):
        api = API()
        def legacy(path, params):
            rows, pages = api.get(path, params)
            return rows, pages.get('page_count') if isinstance(pages, dict) else pages
        with self.assertRaises(sync.IncompleteSnapshot): capture(legacy)

    def test_legacy_terminal_counts_need_fresh_proof_not_a_manifest_flag(self):
        payload, manifest, reference = historic(1845, with_reference=True)
        with self.assertRaises(sync.IncompleteSnapshot): self.verify(payload, manifest)
        mismatched = copy.deepcopy(reference)
        mismatched[0]['snapshot']['activity'] = EARLY
        with self.assertRaises(sync.IncompleteSnapshot): self.verify(payload, manifest, mismatched)

    def test_repeated_page_body_is_not_complete_even_with_valid_total_headers(self):
        api = API()
        row = api.responses['/sync/history/movies'][0][0]
        api.responses['/sync/history/movies'] = lambda params: ([row], 2)
        with self.assertRaises(sync.IncompleteSnapshot): capture(api.get)
