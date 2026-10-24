"""Private export guarantees, using synthetic account data only."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

from test_trakt_sync import API, sync

ROOT = Path(__file__).resolve().parents[1]
sys.modules['trakt_sync'] = sync
spec = importlib.util.spec_from_file_location('trakt_snapshot', ROOT / 'third_party/xstream/trakt_snapshot.py')
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


class SnapshotExportTests(unittest.TestCase):
    def setUp(self):
        self.api = API()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)

    def export(self, **kwargs):
        return exporter.export_snapshot(self.api.get, self.base, '1', **kwargs)

    def test_verified_private_export_contains_full_responses_no_credentials(self):
        self.api.responses['/users/settings'][0]['user']['email'] = 'synthetic-private-email'
        summary = self.export()
        target = next(self.base.iterdir())
        raw = (target / 'snapshot.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), summary['sha256'])
        self.assertTrue(all(path.startswith(('/users/', '/sync/'))
                            for path, _params in self.api.calls))
        self.assertEqual(json.loads(raw)['profile'], '1')
        self.assertNotIn(b'synthetic-private-email', raw)
        self.assertFalse(target.stat().st_mode & 0o077)
        self.assertFalse((target / 'snapshot.json').stat().st_mode & 0o077)
        self.assertFalse((target / 'manifest.json').stat().st_mode & 0o077)
        self.assertEqual(json.loads((target / 'manifest.json').read_text()), summary)

    def test_repeated_exports_are_immutable_and_independent(self):
        first = self.export()
        self.assertEqual(self.export(), first)
        self.assertEqual(len(list(self.base.iterdir())), 2)

    def test_failed_read_never_creates_a_verified_backup(self):
        def fail(_):
            raise TimeoutError('private URL must not leak')
        self.api.responses['/sync/history/movies'] = fail
        with self.assertRaises(TimeoutError):
            self.export()
        self.assertEqual(list(self.base.iterdir()), [])

    def test_cancellation_or_changed_profile_preserves_previous_exports(self):
        self.export()
        with self.assertRaises(sync.IncompleteSnapshot):
            self.export(cancelled=lambda: True)
        self.assertEqual(len(list(self.base.iterdir())), 1)

    def test_nonprivate_directory_is_rejected(self):
        self.base.chmod(0o755)
        with self.assertRaises(ValueError):
            self.export()

    def test_snapshot_keeps_repeated_history_events_for_recovery(self):
        row = self.api.responses['/sync/history/movies'][0][0]
        self.api.responses['/sync/history/movies'] = ([row, dict(row, id=2)], 1)
        self.export()
        data = json.loads(next(self.base.glob('*/snapshot.json')).read_text())
        page = next(p for p in data['responses'] if p['path'] == '/sync/history/movies')
        self.assertEqual(len(page['data']), 2)
        self.assertEqual(len(data['snapshot']['history']), 2)


if __name__ == '__main__':
    unittest.main()
