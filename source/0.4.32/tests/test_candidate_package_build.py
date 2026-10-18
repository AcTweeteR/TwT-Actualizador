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
            package = Path(temp) / "service.actweeter-0.4.37.zip"
            subprocess.run([sys.executable, str(ROOT / "tools/build_service_package.py"),
                            "--output", str(package)], check=True,
                           cwd=ROOT, capture_output=True, text=True)
            first_hash = hashlib.sha256(package.read_bytes()).hexdigest()
            subprocess.run([sys.executable, str(ROOT / "tools/build_service_package.py"),
                            "--output", str(package)], check=True,
                           cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(hashlib.sha256(package.read_bytes()).hexdigest(), first_hash)
            with zipfile.ZipFile(package) as archive:
                self.assertIsNone(archive.testzip())
                addon = ET.fromstring(archive.read("service.actweeter/addon.xml"))
                self.assertEqual(addon.get("version"), "0.4.37")
                self.assertIn("service.actweeter/changelog-0.4.37.txt",
                              archive.namelist())
                self.assertFalse(any(name.endswith((".pyc", ".pyo"))
                                     or "__pycache__" in name.split("/")
                                     for name in archive.namelist()))
                for name in archive.namelist():
                    if name.endswith(".py"):
                        ast.parse(archive.read(name), filename=name)

    def test_candidate_distribution_index_uses_unchanged_031_packages(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import build_distribution_index

        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            service = output / "service.actweeter-0.4.37.zip"
            subprocess.run([sys.executable, str(ROOT / "tools/build_service_package.py"),
                            "--output", str(service)], check=True,
                           cwd=ROOT, capture_output=True, text=True)
            repo = REPOSITORY_ROOT / "repo"
            index_path, md5_path = build_distribution_index.build(
                repo / "repository.actweeter/repository.actweeter-1.0.3.zip",
                repo / "skin.actweeter/skin.actweeter-1.2.28.zip",
                service,
                repo / "plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.7.zip",
                output / "index")
            payload = index_path.read_bytes()
            versions = {node.get("id"): node.get("version")
                        for node in ET.fromstring(payload).findall("addon")}
            self.assertEqual(versions["service.actweeter"], "0.4.37")
            self.assertEqual(versions["skin.actweeter"], "1.2.28")
            self.assertEqual(versions["plugin.video.xstream-pro"], "1.1.2.7")
            self.assertEqual(hashlib.md5(payload).hexdigest(),
                             md5_path.read_text(encoding="ascii").strip())


if __name__ == "__main__":
    unittest.main()
