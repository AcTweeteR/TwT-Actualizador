import hashlib
import json
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1]
REPO = SOURCE.parents[1]
MANIFEST = json.loads((REPO / "manifests/0.4.29.json").read_text(encoding="utf-8"))


class DistributionArtifactTests(unittest.TestCase):
    def test_candidate_feed_checksum_and_versions(self):
        payload = (REPO / "repo/addons.xml").read_bytes()
        expected_md5 = (REPO / "repo/addons.xml.md5").read_text(encoding="ascii").strip()
        self.assertEqual(hashlib.md5(payload).hexdigest(), expected_md5)
        root = ET.fromstring(payload)
        versions = {node.get("id"): node.get("version") for node in root.findall("addon")}
        self.assertEqual(versions["repository.actweeter"], "1.0.3")
        self.assertEqual(versions["skin.actweeter"], "1.2.28")
        self.assertEqual(versions["plugin.video.xstream-pro"], "1.1.2.7")
        service_version = tuple(map(int, versions["service.actweeter"].split(".")))
        self.assertGreaterEqual(service_version, (0, 4, 29))

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
        self.assertTrue((REPO / "repo/service.actweeter/service.actweeter-0.4.28.zip").is_file())

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
