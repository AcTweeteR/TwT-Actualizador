import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from verify_current_stable import MANIFEST, verify  # noqa: E402


class CurrentStableManifestTests(unittest.TestCase):
    def test_current_release_matches_immutable_manifest(self):
        self.assertEqual(verify(), "7c5f5f24f0bf73ebcf800251c1183c703151c8ee3025f3efc8a61bc0b9b96589")

    def test_changed_index_hash_is_rejected(self):
        manifest = json.loads(MANIFEST.read_text())
        manifest["index_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "manifest.json"
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "Stable index differs"):
                verify(manifest_path=path)
