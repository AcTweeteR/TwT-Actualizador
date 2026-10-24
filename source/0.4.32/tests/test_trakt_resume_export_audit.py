"""Synthetic regression coverage for checksum and cross-device resume invariants."""
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[3] / 'tools/verify_trakt_resume_restore.py'
spec = importlib.util.spec_from_file_location('resume_export_audit', PATH)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class ResumeExportAuditTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.folders = [self.root / str(i) for i in range(3)]
        self.data = {'profile': '1', 'snapshot': {'account': 'synthetic', 'records': {
            'movie:tmdb:42': {'identity': {'kind': 'movie', 'ids': {'tmdb': '42'},
              'key': 'movie:tmdb:42'}, 'paused_at': '2026-10-21T10:00:00Z',
              'progress': 31.5}}, 'history': [], 'unidentified': 0}}
        for folder in self.folders:
            self.write(folder, self.data)

    def write(self, folder, data):
        folder.mkdir(exist_ok=True)
        raw = json.dumps(data).encode()
        (folder / 'snapshot.json').write_bytes(raw)
        (folder / 'manifest.json').write_text(json.dumps({'sha256': hashlib.sha256(raw).hexdigest()}))

    def test_identical_exports_are_safe(self):
        result = audit.audit(self.folders)
        self.assertEqual(result['matching_resume_records'], 1)
        self.assertEqual(result['kodi_store_writes'], 0)

    def test_tampered_export_rejected(self):
        (self.folders[1] / 'snapshot.json').write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            audit.audit(self.folders)

    def test_changed_resume_rejected(self):
        changed = json.loads(json.dumps(self.data))
        changed['snapshot']['records']['movie:tmdb:42']['progress'] = 40
        self.write(self.folders[2], changed)
        with self.assertRaisesRegex(ValueError, 'resume states differ'):
            audit.audit(self.folders)

    def test_wrong_account_rejected(self):
        changed = json.loads(json.dumps(self.data))
        changed['snapshot']['account'] = 'other'
        self.write(self.folders[1], changed)
        with self.assertRaisesRegex(ValueError, 'account/profile mismatch'):
            audit.audit(self.folders)


if __name__ == '__main__':
    unittest.main()
