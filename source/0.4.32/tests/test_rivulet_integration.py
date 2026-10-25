"""Rivulet remains a required Kodi-managed extension, not a copied add-on."""
import hashlib
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "source/0.4.32/addons/service.actweeter/resources/lib"))
import build_test_channel
import first_run
import module_catalog


class RivuletIntegrationTests(unittest.TestCase):
    def test_rivulet_is_a_required_dependency_first_native_install_on_all_targets(self):
        addons = module_catalog.all_addons()
        self.assertTrue(addons["repository.rivulet"]["required"])
        self.assertTrue(addons["plugin.video.rivulet"]["required"])
        self.assertEqual(addons["repository.rivulet"]["repositories"],
                         ("repository.actweeter",))
        self.assertEqual(addons["plugin.video.rivulet"]["repositories"],
                         ("repository.rivulet",))
        self.assertEqual(first_run.REQUIRED_EXTERNAL_ADDON_MINIMUMS["plugin.video.rivulet"],
                         "0.36.0")
        for platform in module_catalog.ALL_TARGET_PLATFORMS:
            plan = module_catalog.installation_plan(platform)
            ids = [row["id"] for row in plan]
            self.assertLess(ids.index("repository.rivulet"),
                            ids.index("plugin.video.rivulet"))
            self.assertIn("plugin.video.rivulet", first_run.REQUIRED_ADDON_IDS)

    def test_iagl_is_mandatory_native_install_and_official_repository_is_pinned(self):
        addons = module_catalog.all_addons()
        self.assertTrue(addons["repository.zachmorris"]["required"])
        self.assertTrue(addons["plugin.program.iagl"]["required"])
        self.assertEqual(addons["repository.zachmorris"]["repositories"],
                         ("repository.actweeter",))
        self.assertEqual(addons["plugin.program.iagl"]["repositories"],
                         ("repository.zachmorris",))
        self.assertEqual(first_run.REQUIRED_EXTERNAL_ADDON_MINIMUMS["plugin.program.iagl"],
                         "4.0.6")
        for platform in module_catalog.ALL_TARGET_PLATFORMS:
            ids = [row["id"] for row in module_catalog.installation_plan(platform)]
            self.assertLess(ids.index("repository.zachmorris"),
                            ids.index("plugin.program.iagl"))
            self.assertIn("plugin.program.iagl", first_run.REQUIRED_ADDON_IDS)

    def test_iagl_bootstrap_hash_identity_and_published_package(self):
        self.assertEqual(build_test_channel.IAGL_REPOSITORY_SHA256,
                         "3dde8f37dcd64f122cf1e897e139e5b8b7a3cd0ec15db6a1f5c7b59852cb661b")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            service = self._addon_zip(root / "service.actweeter-0.4.85.zip",
                                      "service.actweeter", "0.4.85")
            rivulet = ROOT / "source/0.4.32/third_party/rivulet/repository.rivulet-1.0.2.zip"
            iagl = ROOT / "source/0.4.32/third_party/iagl/repository.zachmorris-1.0.4.zip"
            _, index, checksum = build_test_channel.build(
                ROOT / "testing/repository.actweeter.testing", service,
                root / "testing", rivulet_repository_zip=rivulet,
                iagl_repository_zip=iagl)
            entry = ET.parse(index).getroot().find("addon[@id='repository.zachmorris']")
            self.assertEqual(entry.get("version"), "1.0.4")
            published = index.parent / "repository.zachmorris" / iagl.name
            self.assertEqual(published.read_bytes(), iagl.read_bytes())
            self.assertEqual(hashlib.md5(index.read_bytes()).hexdigest(),
                             checksum.read_text().strip())

    def test_bootstrap_pins_upstream_repository_hash_and_identity(self):
        self.assertEqual(build_test_channel.RIVULET_REPOSITORY_SHA256,
                         "e4aabb495d6b49f39b8ec0c828ad9fa4562c387547739e0f38351ddabac9a815")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            service = self._addon_zip(root / "service.actweeter-0.4.83.zip",
                                      "service.actweeter", "0.4.83")
            repository = ROOT / "source/0.4.32/third_party/rivulet/repository.rivulet-1.0.2.zip"
            _, index, checksum = build_test_channel.build(
                ROOT / "testing/repository.actweeter.testing", service,
                root / "testing", rivulet_repository_zip=repository)
            entry = ET.parse(index).getroot().find(
                "addon[@id='repository.rivulet']")
            self.assertEqual(entry.get("version"), "1.0.2")
            published = index.parent / "repository.rivulet" / repository.name
            self.assertEqual(published.read_bytes(), repository.read_bytes())
            self.assertEqual(hashlib.md5(index.read_bytes()).hexdigest(),
                             checksum.read_text().strip())

    def test_required_service_candidate_cannot_omit_rivulet_seed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            service = self._addon_zip(root / "service.actweeter-0.4.83.zip",
                                      "service.actweeter", "0.4.83")
            with self.assertRaisesRegex(ValueError, "pinned Rivulet repository"):
                build_test_channel.build(
                    ROOT / "testing/repository.actweeter.testing", service,
                    root / "testing")
            self.assertFalse((root / "testing").exists())

    def test_candidate_rejects_a_changed_upstream_repository_package(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            service = self._addon_zip(root / "service.actweeter-0.4.83.zip",
                                      "service.actweeter", "0.4.83")
            repository = self._addon_zip(root / "repository.rivulet-1.0.2.zip",
                                         "repository.rivulet", "1.0.2")
            with self.assertRaisesRegex(ValueError, "pinned upstream SHA-256"):
                build_test_channel.build(
                    ROOT / "testing/repository.actweeter.testing", service,
                    root / "testing", rivulet_repository_zip=repository)
            self.assertFalse((root / "testing").exists())

    def test_kodi_refreshes_repository_catalog_after_native_seed_install(self):
        setup = (ROOT / "source/0.4.32/addons/service.actweeter/setup.py").read_text()
        self.assertIn('addon_id in ("plugin.video.rivulet", "plugin.program.iagl") and not _addon_installed(addon_id)', setup)
        self.assertIn('_wait_for_installable_addon(addon_id, minimum)', setup)
        self.assertIn('"installed": False', setup)
        self.assertIn('"plugin.video.rivulet": "Rivulet"', setup)
        self.assertNotIn('InstallAddon(plugin.video.rivulet)', setup)

    @staticmethod
    def _addon_zip(path, addon_id, version):
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(f"{addon_id}/addon.xml",
                             f'<addon id="{addon_id}" version="{version}"/>')
        return path


if __name__ == "__main__":
    unittest.main()
