from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class XStreamSeriesRecentDistributionTests(unittest.TestCase):
    def test_series_recent_is_inside_declared_patch_hunk(self):
        patch_path = ROOT / "third_party/xstream/patches/1.1.2/actweeter-runtime.patch"
        patch = patch_path.read_text(encoding="utf-8")
        section_start = patch.index("+++ b/resources/lib/series_changes.py")
        hunk_start = patch.index("@@", section_start)
        hunk_end = patch.find("diff --git ", hunk_start)
        hunk = patch[hunk_start:hunk_end if hunk_end >= 0 else len(patch)]
        declared = re.search(r"^@@ -0,0 \+1,(\d+) @@", hunk, re.MULTILINE)
        added = [line for line in hunk.splitlines()
                 if line.startswith("+") and not line.startswith("+++")]
        self.assertIsNotNone(declared)
        self.assertEqual(int(declared.group(1)), len(added))
        self.assertTrue(any(line == "+def recent(addon, profile_num, limit=24):"
                            for line in added))

    def test_manifest_locks_patch_and_patched_runtime_provider(self):
        manifest_path = ROOT / "third_party/xstream/upstream.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        patch_path = ROOT / manifest["patch"]
        expected_patch_hash = hashlib.sha256(patch_path.read_bytes()).hexdigest()
        self.assertEqual(manifest["patch_sha256"], expected_patch_hash)
        self.assertEqual(manifest["distribution_version"], "1.1.2.28~beta3")
        self.assertIn("resources/lib/series_changes.py",
                      manifest["local_runtime_sha256"])

    def test_builder_rejects_missing_series_recent_symbol(self):
        builder = (ROOT / "tools/build_xstream_package.py").read_text(encoding="utf-8")
        self.assertIn("series_changes.recent route provider is missing", builder)
        self.assertIn("premium series catalog baseline hook missing", builder)
        self.assertIn("patched runtime hash mismatch", builder)


if __name__ == "__main__":
    unittest.main()
