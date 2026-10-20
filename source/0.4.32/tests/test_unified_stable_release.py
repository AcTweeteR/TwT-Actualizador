"""Release contract for the unified Stable distribution, not a runtime assertion."""
from __future__ import annotations

import hashlib
import json
import sys
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from build_stable_channel import (  # noqa: E402
    BETA_VERSION, STABLE_VERSION, STABLE_NEWS, EXPECTED_INPUT_SHA256,
    _sha, build, promote_skin,
)


class UnifiedStableReleaseTests(unittest.TestCase):
    def test_release_versions_hashes_and_checksum(self):
        m = json.loads((ROOT / "manifests/unified-stable-20261020.json").read_text())
        stable = ROOT / "repo"
        data = (stable / "addons.xml").read_bytes()
        self.assertEqual(m["index_sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(m["index_md5"], hashlib.md5(data).hexdigest())
        self.assertEqual((stable / "addons.xml.md5").read_text().strip(),
                         hashlib.md5(data).hexdigest())
        addons = ET.fromstring(data)
        self.assertEqual([(a.get("id"), a.get("version")) for a in addons],
                         [("repository.actweeter", "1.0.3"),
                          ("skin.actweeter", STABLE_VERSION),
                          ("service.actweeter", "0.4.45"),
                          ("plugin.video.xstream-pro", "1.1.2.10")])
        self.assertEqual(len(m["addons"]), 4)
        for addon in m["addons"]:
            p = stable / addon["id"] / f'{addon["id"]}-{addon["version"]}.zip'
            self.assertEqual(_sha(p), addon["sha256"])
            with zipfile.ZipFile(p) as z:
                self.assertIsNone(z.testzip())
                x = ET.fromstring(z.read(addon["id"] + "/addon.xml"))
                self.assertEqual((x.get("id"), x.get("version")),
                                 (addon["id"], addon["version"]))

    def test_stable_skin_matches_tested_beta_except_version_and_changelog(self):
        beta = ROOT / "docs/testing/repo/skin.actweeter" / (
            f"skin.actweeter-{BETA_VERSION}.zip")
        stable = ROOT / "repo/skin.actweeter" / f"skin.actweeter-{STABLE_VERSION}.zip"
        self.assertEqual(_sha(beta), EXPECTED_INPUT_SHA256["skin"])
        with zipfile.ZipFile(beta) as a, zipfile.ZipFile(stable) as b:
            original, released = set(a.namelist()), set(b.namelist())
            self.assertEqual(released - original, {
                f"skin.actweeter/changelog-{STABLE_VERSION}.txt"})
            self.assertEqual(original - released, set())
            self.assertEqual(b.read(f"skin.actweeter/changelog-{STABLE_VERSION}.txt"),
                             STABLE_NEWS)
            differences = [name for name in original
                           if hashlib.sha256(a.read(name)).digest()
                           != hashlib.sha256(b.read(name)).digest()]
            self.assertEqual(differences, ["skin.actweeter/addon.xml"])

    def test_no_testing_packages_or_index_modified_by_stable_promotion(self):
        manifest = json.loads((ROOT / "manifests/unified-stable-20261020.json").read_text())
        self.assertEqual(_sha(ROOT / "docs/testing/repo/addons.xml"),
                         manifest["testing_feed_sha256_at_publication"])
        for kind, path in [
            ("repository", "repo/repository.actweeter/repository.actweeter-1.0.3.zip"),
            ("skin", f"docs/testing/repo/skin.actweeter/skin.actweeter-{BETA_VERSION}.zip"),
            ("service", "docs/testing/repo/service.actweeter/service.actweeter-0.4.45.zip"),
            ("xstream", "docs/testing/repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.10.zip"),
        ]:
            self.assertEqual(_sha(ROOT / path), EXPECTED_INPUT_SHA256[kind])

    def test_stable_package_builder_deterministic_and_create_only(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp:
            dest = Path(tmp) / "release"
            skin, xml, md5 = build(dest)
            self.assertEqual(skin.read_bytes(),
                             (ROOT / "repo/skin.actweeter/skin.actweeter-1.2.30.zip").read_bytes())
            self.assertEqual(xml.read_bytes(), (ROOT / "repo/addons.xml").read_bytes())
            self.assertEqual(md5.read_bytes(), (ROOT / "repo/addons.xml.md5").read_bytes())
            with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                build(dest)

    def test_skin_promotion_rejects_changed_beta_source(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "modified.zip"
            candidate.write_bytes(b"not an approved skin ZIP")
            with self.assertRaisesRegex(ValueError, "unverified skin"):
                promote_skin(candidate, Path(tmp) / "new-skin.zip")


if __name__ == "__main__":
    unittest.main()
