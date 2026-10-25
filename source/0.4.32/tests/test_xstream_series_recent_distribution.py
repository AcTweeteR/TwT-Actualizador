from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class XStreamSeriesRecentDistributionTests(unittest.TestCase):
    def test_series_recent_is_inside_declared_patch_hunk(self):
        source = (ROOT / "third_party/xstream/series_changes.py").read_text(encoding="utf-8")
        self.assertIn("def recent(addon, profile_num, limit=24):", source)
        self.assertIn("STATE_VERSION = 2", source)
        self.assertNotIn("MAX_EVENTS", source)
        self.assertIn("complete=True", source)
        self.assertIn("provider=None", source)

    def test_manifest_locks_patch_and_patched_runtime_provider(self):
        manifest_path = ROOT / "third_party/xstream/upstream.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        patch_path = ROOT / manifest["patch"]
        expected_patch_hash = hashlib.sha256(patch_path.read_bytes()).hexdigest()
        self.assertEqual(manifest["patch_sha256"], expected_patch_hash)
        self.assertEqual(manifest["distribution_version"], "1.1.2.34~beta2")
        self.assertIn("resources/lib/series_changes.py",
                      manifest["local_runtime_sha256"])

    def test_builder_rejects_missing_series_recent_symbol(self):
        builder = (ROOT / "tools/build_xstream_package.py").read_text(encoding="utf-8")
        self.assertIn("series_changes.recent route provider is missing", builder)
        self.assertIn("validate_series_changes_contract(archive)", builder)
        self.assertIn("premium series catalog baseline hook missing", builder)
        self.assertIn("patched runtime hash mismatch", builder)


if __name__ == "__main__":
    unittest.main()
