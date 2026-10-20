import json
import unittest
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
                         ("service.actweeter", "0.4.46"))
        self.assertEqual((skin.get("id"), skin.get("version")),
                         ("skin.actweeter", "1.2.30~beta3"))
        self.assertEqual((repository.get("id"), repository.get("version")),
                         ("repository.actweeter", "1.0.3"))
        self.assertEqual(xstream["distribution_version"], "1.1.2.14")

    def test_migration_is_versioned_after_official_0_4_31_layout(self):
        sys_path = ROOT / "addons/service.actweeter/resources/lib"
        import sys
        sys.path.insert(0, str(sys_path))
        import interface_layout
        self.assertEqual(interface_layout.LAYOUT_VERSION, 13)
        self.assertEqual(interface_layout.LAYOUT_MIGRATION_ID,
                         "interface-layout-v13-default-navigation")
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
