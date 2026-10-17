from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
import build_test_channel  # noqa: E402


class OfficialTestChannelTests(unittest.TestCase):
    def test_beta_skin_is_only_in_testing_feed_and_does_not_change_stable(self):
        import subprocess
        stable = (ROOT / "repo/addons.xml").read_bytes()
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            service = temp_root / "service.actweeter-0.4.33.zip"
            skin = temp_root / "skin.actweeter-1.2.29~beta4.zip"
            for builder, package in (("build_service_package.py", service),
                                     ("build_skin_package.py", skin)):
                subprocess.run([sys.executable, str(ROOT / "source/0.4.32/tools" / builder),
                                "--output", str(package)], check=True, capture_output=True)
            _, index, checksum = build_test_channel.build(
                ROOT / "testing/repository.actweeter.testing", service,
                temp_root / "testing", skin)
            versions = {n.get("id"): n.get("version") for n in ET.parse(index).getroot()}
            self.assertEqual(versions["skin.actweeter"], "1.2.29~beta4")
            copied = index.parent / "skin.actweeter" / skin.name
            self.assertEqual(copied.read_bytes(), skin.read_bytes())
            self.assertEqual(checksum.read_text().strip(), hashlib.md5(index.read_bytes()).hexdigest())
            self.assertEqual((ROOT / "repo/addons.xml").read_bytes(), stable)

    def test_test_feed_is_separate_and_stable_index_remains_stable(self) -> None:
        stable_index = (ROOT / "repo" / "addons.xml").read_bytes()
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            candidate_service = temp_root / "service.actweeter-0.4.33.zip"
            # Build the same deterministic service ZIP that the test-feed builder publishes.
            import subprocess
            subprocess.run([
                sys.executable,
                str(ROOT / "source" / "0.4.32" / "tools" / "build_service_package.py"),
                "--output", str(candidate_service),
            ], check=True, capture_output=True, text=True)
            output = temp_root / "testing"
            bootstrap, index, checksum = build_test_channel.build(
                ROOT / "testing" / "repository.actweeter.testing", candidate_service, output
            )
            root = ET.parse(index).getroot()
            versions = {node.get("id"): node.get("version") for node in root.findall("addon")}
            self.assertEqual(versions, {
                "repository.actweeter.testing": "1.0.0",
                "service.actweeter": "0.4.33",
            })
            feed_addon = ET.parse(ROOT / "testing" / "repository.actweeter.testing" / "addon.xml").getroot()
            endpoints = [node.findtext("info", "") for node in feed_addon.findall(
                "./extension[@point='xbmc.addon.repository']/dir"
            )]
            self.assertIn("https://actweeter.github.io/TwT-Actualizador/testing/repo/addons.xml", endpoints)
            self.assertIn("https://raw.githubusercontent.com/AcTweeteR/TwT-Actualizador/main/repo/addons.xml", endpoints)
            self.assertEqual(checksum.read_text().strip(), hashlib.md5(index.read_bytes()).hexdigest())
            self.assertEqual(ET.parse(ROOT / "repo" / "addons.xml").getroot().find("addon[@id='service.actweeter']").get("version"), "0.4.31")
            self.assertEqual((ROOT / "repo" / "addons.xml").read_bytes(), stable_index)
            with zipfile.ZipFile(bootstrap) as archive:
                self.assertIsNone(archive.testzip())
                package = ET.fromstring(archive.read("repository.actweeter.testing/addon.xml"))
                self.assertEqual(package.get("id"), "repository.actweeter.testing")
            self.assertTrue((output / "bootstrap" / "index.html").is_file())


if __name__ == "__main__":
    unittest.main()
