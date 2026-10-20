import ast
import hashlib
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parents[1]


class CandidatePackageBuildTests(unittest.TestCase):
    def test_service_zip_is_reproducible_and_well_formed(self):
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / "service.actweeter-0.4.45.zip"
            subprocess.run([sys.executable, str(ROOT / "tools/build_service_package.py"),
                            "--output", str(package)], check=True,
                           cwd=ROOT, capture_output=True, text=True)
            first_hash = hashlib.sha256(package.read_bytes()).hexdigest()
            second_package = Path(temp) / "service-second.zip"
            subprocess.run([sys.executable, str(ROOT / "tools/build_service_package.py"),
                            "--output", str(second_package)], check=True,
                            cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(hashlib.sha256(second_package.read_bytes()).hexdigest(), first_hash)
            with zipfile.ZipFile(package) as archive:
                self.assertIsNone(archive.testzip())
                addon = ET.fromstring(archive.read("service.actweeter/addon.xml"))
                self.assertEqual(addon.get("version"), "0.4.45")
                self.assertIn("service.actweeter/changelog-0.4.45.txt",
                              archive.namelist())
                layout_tree = ast.parse(archive.read(
                    'service.actweeter/resources/lib/interface_layout.py'))
                retries = next(node.value.args[0] for node in layout_tree.body
                               if isinstance(node, ast.Assign)
                               and any(isinstance(target, ast.Name)
                                       and target.id == 'RETRYABLE_INTERFACE_RESULTS'
                                       for target in node.targets))
                self.assertNotIn('GENERATED_XML_PROPERTY_MISSING', ast.literal_eval(retries))
                self.assertIn('_matches_profile', archive.read(
                    'service.actweeter/resources/lib/interface_layout.py').decode())
                self.assertIn('_offer_automatic_previews', archive.read(
                    'service.actweeter/setup.py').decode())
                self.assertFalse(any(name.endswith((".pyc", ".pyo"))
                                     or "__pycache__" in name.split("/")
                                     for name in archive.namelist()))
                for name in archive.namelist():
                    if name.endswith(".py"):
                        ast.parse(archive.read(name), filename=name)

    def test_candidate_distribution_index_is_testing_only(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import build_distribution_index

        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            service = output / "service.actweeter-0.4.45.zip"
            subprocess.run([sys.executable, str(ROOT / "tools/build_service_package.py"),
                            "--output", str(service)], check=True,
                           cwd=ROOT, capture_output=True, text=True)
            skin = output / "skin.actweeter-1.2.30~beta2.zip"
            subprocess.run([sys.executable, str(ROOT / "tools/build_skin_package.py"),
                            "--output", str(skin)], check=True,
                           cwd=ROOT, capture_output=True, text=True)
            xstream = output / "plugin.video.xstream-pro-1.1.2.14.zip"
            self._write_addon_fixture(xstream, "plugin.video.xstream-pro", "1.1.2.14")
            index_path, md5_path = build_distribution_index.build(
                REPOSITORY_ROOT / "docs/testing/repo/repository.actweeter.testing/repository.actweeter.testing-1.0.2.zip",
                skin,
                service,
                xstream,
                output / "index")
            payload = index_path.read_bytes()
            versions = {node.get("id"): node.get("version")
                        for node in ET.fromstring(payload).findall("addon")}
            self.assertEqual(versions, {
                "repository.actweeter.testing": "1.0.2",
                "service.actweeter": "0.4.45",
                "skin.actweeter": "1.2.30~beta2",
                "plugin.video.xstream-pro": "1.1.2.14",
            })
            self.assertEqual(hashlib.md5(payload).hexdigest(),
                             md5_path.read_text(encoding="ascii").strip())

    @staticmethod
    def _write_addon_fixture(path, addon_id, version):
        root = ET.Element("addon", id=addon_id, version=version)
        ET.SubElement(root, "extension", point="xbmc.addon.metadata")
        payload = ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(addon_id + "/addon.xml", payload)


if __name__ == "__main__":
    unittest.main()
