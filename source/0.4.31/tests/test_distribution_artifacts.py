import hashlib
import json
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1]
REPO = SOURCE.parents[1]
MANIFEST = json.loads((REPO / "manifests/0.4.31.json").read_text(encoding="utf-8"))


class DistributionArtifactTests(unittest.TestCase):
    def test_historical_versions_and_current_stable_manifest_are_distinct(self):
        # Historical ZIPs are immutable, but the live Stable feed advances.
        historical = {a["id"]: a["version"] for a in MANIFEST["addons"]}
        self.assertEqual(historical, {
            "repository.actweeter": "1.0.3",
            "skin.actweeter": "1.2.28",
            "service.actweeter": "0.4.31",
            "plugin.video.xstream-pro": "1.1.2.7",
        })
        previous = json.loads((REPO / "manifests/unified-stable-20261020.json").read_text())
        historical_release = json.loads((REPO / "manifests/actweeter-stable-20261021.json").read_text())
        release = json.loads((REPO / "manifests/actweeter-stable-rivulet-iagl-20261025.json").read_text())
        self.assertEqual(historical_release["previous_stable_index_sha256"], previous["index_sha256"])
        self.assertNotEqual(release["index_sha256"], historical_release["index_sha256"])
        payload = (REPO / "repo/addons.xml").read_bytes()
        self.assertEqual(hashlib.sha256(payload).hexdigest(), release["index_sha256"])
        self.assertEqual(hashlib.md5(payload).hexdigest(), release["index_md5"])
        self.assertEqual(
            (REPO / "repo/addons.xml.md5").read_text(encoding="ascii").strip(),
            release["index_md5"])
        current = {a.get("id"): a.get("version") for a in ET.fromstring(payload)}
        self.assertEqual(current, {a["id"]: a["version"] for a in release["addons"]})

    def test_candidate_and_rollback_packages_have_valid_crc_and_manifest_hashes(self):
        for addon in MANIFEST["addons"]:
            package = REPO / addon["file"]
            self.assertTrue(package.is_file(), package)
            self.assertEqual(hashlib.sha256(package.read_bytes()).hexdigest(), addon["sha256"])
            with zipfile.ZipFile(package) as archive:
                self.assertIsNone(archive.testzip())
                root = f"{addon['id']}/addon.xml"
                self.assertIn(root, archive.namelist())
                metadata = ET.fromstring(archive.read(root))
                self.assertEqual(metadata.get("id"), addon["id"])
                self.assertEqual(metadata.get("version"), addon["version"])
        self.assertTrue((REPO / "repo/skin.actweeter/skin.actweeter-1.2.27.zip").is_file())
        self.assertTrue((REPO / "repo/service.actweeter/service.actweeter-0.4.30.zip").is_file())

    def test_xstream_package_retains_noncommercial_license_notice(self):
        package = REPO / "repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.7.zip"
        with zipfile.ZipFile(package) as archive:
            texts = [archive.read(name).decode("utf-8", "ignore") for name in archive.namelist()
                     if name.lower().endswith(("license", "licence", "license.txt",
                                               "licence.txt", "license.md", "licence.md"))]
        self.assertTrue(any("CC BY-NC 4.0" in text or "Attribution-NonCommercial 4.0" in text
                            for text in texts))


if __name__ == "__main__":
    unittest.main()
