from __future__ import annotations

import hashlib
import json
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
    def test_beta10_manifest_matches_testing_artifacts_and_preserves_stable(self):
        manifest = json.loads((ROOT / "manifests/0.4.37-beta10.json").read_text())
        self.assertTrue(manifest["stable_untouched"])
        self.assertEqual(manifest["release"], "0.4.37-beta10")
        expected = {
            "skin.actweeter": ROOT / "docs/testing/repo/skin.actweeter/skin.actweeter-1.2.29~beta10.zip",
            "service.actweeter": ROOT / "docs/testing/repo/service.actweeter/service.actweeter-0.4.37.zip",
            "repository.actweeter.testing": ROOT / "docs/testing/bootstrap/repository.actweeter.testing-1.0.0.zip",
        }
        for addon in manifest["addons"]:
            if addon["id"] in expected:
                self.assertEqual(hashlib.sha256(expected[addon["id"]].read_bytes()).hexdigest(),
                                 addon["sha256"])
        # docs/testing is the rolling Beta feed; after Beta 11 it no longer
        # serves the historical Beta 10 index. Preserve its recorded hashes
        # in the release manifest and validate the current index in Beta 11's
        # dedicated manifest test below.
        self.assertRegex(manifest["testing_index"]["sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(manifest["testing_index"]["md5"], r"^[0-9a-f]{32}$")

    def test_beta_skin_is_only_in_testing_feed_and_does_not_change_stable(self):
        import subprocess
        stable = (ROOT / "repo/addons.xml").read_bytes()
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            service = temp_root / "service.actweeter-0.4.37.zip"
            skin = temp_root / "skin.actweeter-1.2.29~beta10.zip"
            for builder, package in (("build_service_package.py", service),
                                     ("build_skin_package.py", skin)):
                subprocess.run([sys.executable, str(ROOT / "source/0.4.32/tools" / builder),
                                "--output", str(package)], check=True, capture_output=True)
            _, index, checksum = build_test_channel.build(
                ROOT / "testing/repository.actweeter.testing", service,
                temp_root / "testing", skin)
            versions = {n.get("id"): n.get("version") for n in ET.parse(index).getroot()}
            self.assertEqual(versions["skin.actweeter"], "1.2.29~beta10")
            copied = index.parent / "skin.actweeter" / skin.name
            self.assertEqual(copied.read_bytes(), skin.read_bytes())
            self.assertEqual(checksum.read_text().strip(), hashlib.md5(index.read_bytes()).hexdigest())
            self.assertEqual((ROOT / "repo/addons.xml").read_bytes(), stable)

    def test_test_feed_is_separate_and_stable_index_remains_stable(self) -> None:
        stable_index = (ROOT / "repo" / "addons.xml").read_bytes()
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            candidate_service = temp_root / "service.actweeter-0.4.37.zip"
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
                "repository.actweeter.testing": "1.0.1",
                "service.actweeter": "0.4.37",
            })
            feed_addon = ET.parse(ROOT / "testing" / "repository.actweeter.testing" / "addon.xml").getroot()
            endpoints = [node.findtext("info", "") for node in feed_addon.findall(
                "./extension[@point='xbmc.addon.repository']/dir"
            )]
            self.assertIn("https://actweeter.github.io/TwT-Actualizador/testing/repo/addons.xml", endpoints)
            self.assertIn("https://raw.githubusercontent.com/AcTweeteR/TwT-Actualizador/main/repo/addons.xml", endpoints)
            self.assertIn("https://raw.githubusercontent.com/matke-84/repository.bingie/main/omega/addons.xml", endpoints)
            self.assertIn("https://slyguy.uk/.repo/repository.slyguy/addons.xml", endpoints)
            self.assertEqual(checksum.read_text().strip(), hashlib.md5(index.read_bytes()).hexdigest())
            self.assertEqual(ET.parse(ROOT / "repo" / "addons.xml").getroot().find("addon[@id='service.actweeter']").get("version"), "0.4.31")
            self.assertEqual((ROOT / "repo" / "addons.xml").read_bytes(), stable_index)
            with zipfile.ZipFile(bootstrap) as archive:
                self.assertIsNone(archive.testzip())
                package = ET.fromstring(archive.read("repository.actweeter.testing/addon.xml"))
                self.assertEqual(package.get("id"), "repository.actweeter.testing")
            self.assertTrue((output / "bootstrap" / "index.html").is_file())

    def test_beta_xstream_candidate_is_indexed_without_changing_stable(self) -> None:
        stable_index = (ROOT / "repo" / "addons.xml").read_bytes()
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            candidate_xstream = temp_root / "plugin.video.xstream-pro-1.1.2.8.zip"
            # Small test package proves the test-feed builder indexes/copies the
            # candidate by its embedded Kodi identity, not by a guessed filename.
            with zipfile.ZipFile(candidate_xstream, "w") as archive:
                archive.writestr(
                    "plugin.video.xstream-pro/addon.xml",
                    '<addon id="plugin.video.xstream-pro" version="1.1.2.8" name="XStream" provider-name="AcTweeteR"/>',
                )
            service = temp_root / "service.actweeter-0.4.37.zip"
            with zipfile.ZipFile(service, "w") as archive:
                archive.writestr(
                    "service.actweeter/addon.xml",
                    '<addon id="service.actweeter" version="0.4.37" name="service" provider-name="AcTweeteR"/>',
                )
            _, index, checksum = build_test_channel.build(
                ROOT / "testing/repository.actweeter.testing", service,
                temp_root / "testing", xstream_zip=candidate_xstream)
            versions = {node.get("id"): node.get("version")
                        for node in ET.parse(index).getroot().findall("addon")}
            self.assertEqual(versions["plugin.video.xstream-pro"], "1.1.2.8")
            copied = index.parent / "plugin.video.xstream-pro" / candidate_xstream.name
            self.assertEqual(copied.read_bytes(), candidate_xstream.read_bytes())
            self.assertEqual(checksum.read_text().strip(),
                             hashlib.md5(index.read_bytes()).hexdigest())
            self.assertEqual((ROOT / "repo" / "addons.xml").read_bytes(), stable_index)

    def test_existing_test_feed_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);output=root/'testing';output.mkdir()
            marker=output/'keep.txt';marker.write_text('original')
            with self.assertRaisesRegex(ValueError,'refusing to overwrite'):
                build_test_channel.build(ROOT/'testing/repository.actweeter.testing',
                                        root/'missing.zip',output)
            self.assertEqual(marker.read_text(),'original')

    def test_invalid_package_leaves_no_partial_feed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);service=root/'service.actweeter-0.4.37.zip'
            with zipfile.ZipFile(service,'w') as archive:
                archive.writestr('service.actweeter/addon.xml',
                                 '<addon id="service.actweeter" version="0.4.37"/>')
                archive.writestr('foreign/unsafe','x')
            output=root/'testing'
            with self.assertRaisesRegex(ValueError,'unsafe ZIP paths'):
                build_test_channel.build(ROOT/'testing/repository.actweeter.testing',
                                        service,output)
            self.assertFalse(output.exists())

    def test_build_failure_cleans_staging_and_preserves_stable(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);service=root/'service.actweeter-0.4.37.zip'
            with zipfile.ZipFile(service,'w') as archive:
                archive.writestr('service.actweeter/addon.xml',
                                 '<addon id="service.actweeter" version="0.4.37"/>')
            output=root/'testing'
            with patch.object(build_test_channel,'_write_test_channel',
                              side_effect=OSError('simulated disk failure')):
                with self.assertRaisesRegex(OSError,'disk failure'):
                    build_test_channel.build(ROOT/'testing/repository.actweeter.testing',
                                            service,output)
            self.assertFalse(output.exists())
            self.assertFalse(list(root.glob('.actweeter-test-feed-*')))

    def test_atomic_publication_rejects_existing_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);stage=root/'stage';stage.mkdir()
            (stage/'new.txt').write_text('new')
            output=root/'published';output.mkdir()
            with self.assertRaisesRegex(ValueError,'refusing to overwrite'):
                build_test_channel.publish_directory_no_replace(stage,output)
            self.assertTrue(stage.exists())
            self.assertEqual(list(output.iterdir()),[])

    def test_atomic_publication_rejects_existing_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);stage=root/'stage';stage.mkdir()
            original=root/'original';original.mkdir()
            output=root/'published';output.symlink_to(original)
            with self.assertRaisesRegex(ValueError,'refusing to overwrite'):
                build_test_channel.publish_directory_no_replace(stage,output)
            self.assertTrue(output.is_symlink())
            self.assertTrue(stage.exists())

    def test_atomic_publication_creates_completed_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);stage=root/'stage';stage.mkdir()
            (stage/'complete.txt').write_text('ready')
            output=root/'published'
            build_test_channel.publish_directory_no_replace(stage,output)
            self.assertFalse(stage.exists())
            self.assertEqual((output/'complete.txt').read_text(),'ready')

    def test_beta11_manifest_matches_xstream_and_index_artifacts(self):
        manifest = json.loads((ROOT / "manifests/0.4.37-beta11.json").read_text())
        self.assertTrue(manifest["stable_untouched"])
        self.assertEqual(manifest["release"], "0.4.37-beta11")
        xstream_zip = (ROOT / "docs/testing/repo/plugin.video.xstream-pro/"
                       "plugin.video.xstream-pro-1.1.2.8.zip")
        index = ROOT / "docs/testing/repo/addons.xml"
        self.assertEqual(hashlib.sha256(xstream_zip.read_bytes()).hexdigest(),
                         next(addon["sha256"] for addon in manifest["addons"]
                              if addon["id"] == "plugin.video.xstream-pro"))
        self.assertEqual(hashlib.sha256(index.read_bytes()).hexdigest(),
                         manifest["testing_index"]["sha256"])
        self.assertEqual(hashlib.md5(index.read_bytes()).hexdigest(),
                         manifest["testing_index"]["md5"])
        self.assertEqual(ET.parse(index).getroot().find(
            "addon[@id='plugin.video.xstream-pro']").get("version"), "1.1.2.8")


if __name__ == "__main__":
    unittest.main()
