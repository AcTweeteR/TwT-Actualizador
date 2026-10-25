import hashlib
import json
import unittest
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CandidateSourceMetadataTests(unittest.TestCase):
    def test_beta_skin_preserves_verified_service_and_dependencies(self):
        service = ET.parse(ROOT / "addons/service.actweeter/addon.xml").getroot()
        skin = ET.parse(ROOT / "addons/skin.actweeter/addon.xml").getroot()
        repository = ET.parse(ROOT / "addons/repository.actweeter/addon.xml").getroot()
        xstream = json.loads((ROOT / "third_party/xstream/upstream.json").read_text())
        self.assertEqual((service.get("id"), service.get("version")),
                         ("service.actweeter", "0.4.85"))
        self.assertEqual((skin.get("id"), skin.get("version")),
                         ("skin.actweeter", "1.2.32~beta9"))
        self.assertEqual((repository.get("id"), repository.get("version")),
                         ("repository.actweeter", "1.0.3"))
        self.assertEqual(xstream["distribution_version"], "1.1.2.28~beta20")
        rivulet = json.loads((ROOT / "third_party/rivulet/upstream.json").read_text())
        self.assertEqual(rivulet["version"], "1.0.2")
        self.assertEqual(rivulet["sha256"],
                         "e4aabb495d6b49f39b8ec0c828ad9fa4562c387547739e0f38351ddabac9a815")
        iagl = json.loads((ROOT / "third_party/iagl/upstream.json").read_text())
        iagl_zip = ROOT / "third_party/iagl/repository.zachmorris-1.0.4.zip"
        self.assertEqual(hashlib.sha256(iagl_zip.read_bytes()).hexdigest(), iagl["sha256"])
        with zipfile.ZipFile(iagl_zip) as archive:
            self.assertIsNone(archive.testzip())
            iagl_addon = ET.fromstring(archive.read("repository.zachmorris/addon.xml"))
        self.assertEqual((iagl_addon.get("id"), iagl_addon.get("version")),
                         ("repository.zachmorris", "1.0.4"))
        rivulet_zip = ROOT / "third_party/rivulet/repository.rivulet-1.0.2.zip"
        self.assertEqual(hashlib.sha256(rivulet_zip.read_bytes()).hexdigest(),
                         rivulet["sha256"])
        with zipfile.ZipFile(rivulet_zip) as archive:
            self.assertIsNone(archive.testzip())
            repository_addon = ET.fromstring(
                archive.read("repository.rivulet/addon.xml"))
        self.assertEqual((repository_addon.get("id"), repository_addon.get("version")),
                         ("repository.rivulet", "1.0.2"))
        required = service.find("requires/import[@addon='plugin.video.xstream-pro']")
        self.assertIsNotNone(required)
        self.assertEqual(required.get("version"), xstream["distribution_version"])

    def test_migration_is_versioned_after_official_0_4_31_layout(self):
        sys_path = ROOT / "addons/service.actweeter/resources/lib"
        import sys
        sys.path.insert(0, str(sys_path))
        import interface_layout
        self.assertEqual(interface_layout.LAYOUT_VERSION, 15)
        self.assertEqual(interface_layout.LAYOUT_MIGRATION_ID,
                         "interface-layout-v15-arcade-menu")
        self.assertTrue(interface_layout.interface_migration_due({"layout_version": 12}))

    def test_candidate_manifest_does_not_claim_runtime_or_publication(self):
        repository = ROOT.parents[1]
        manifest = json.loads((repository / "manifests/0.4.32.json").read_text())
        self.assertEqual(manifest["release_kind"], "private candidate; not published")
        self.assertEqual(manifest["runtime_status"]["candidate_build"],
                         "NOT_TESTED_ON_LENOVO")
        self.assertEqual(manifest["publication_status"],
                         "NOT_PUBLISHED; stable release blocked until candidate runtime gates pass")


if __name__ == "__main__":
    unittest.main()
