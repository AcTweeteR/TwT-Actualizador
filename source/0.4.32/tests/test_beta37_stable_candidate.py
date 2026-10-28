import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
import promote_beta37_stable as promotion


class Beta37StableCandidateTest(unittest.TestCase):
    def test_reproducible_and_source_commit_pinned(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / "first", Path(directory) / "second"
            manifest = promotion.build(first)
            promotion.build(second)
            self.assertEqual(manifest["source_commit"], "23d3da2d303d166659f08c1e3c8e113a0c12daeb")
            files = sorted(p.relative_to(first) for p in first.rglob("*") if p.is_file())
            self.assertEqual(files, sorted(p.relative_to(second) for p in second.rglob("*") if p.is_file()))
            for relative in files:
                self.assertEqual((first / relative).read_bytes(), (second / relative).read_bytes(), str(relative))
            with self.assertRaises(ValueError):
                promotion.build(first)

    def test_rejects_changed_source_manifest(self):
        original = promotion.source_bytes
        def changed(path):
            data = original(path)
            return data + b" " if str(path) == "docs/testing/repo/addons.xml" else data
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(promotion, "source_bytes", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "index hash mismatch"):
                promotion.build(Path(directory) / "candidate")
