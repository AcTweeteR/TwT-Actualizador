"""The Stable promotion may change metadata, never Beta34's functional files."""
import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tools/promote_beta34_stable.py"
SPEC = importlib.util.spec_from_file_location("promote_beta34_stable", SCRIPT)
PROMOTION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROMOTION)


class Beta34StablePromotionTest(unittest.TestCase):
    def test_reproducible_and_metadata_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp) / "first", Path(tmp) / "second"
            manifest = PROMOTION.build(first)
            self.assertEqual(manifest, PROMOTION.build(second))
            for file in first.rglob("*"):
                if file.is_file():
                    self.assertEqual(file.read_bytes(), (second / file.relative_to(first)).read_bytes())
            for asset in manifest["assets"]:
                self.assertEqual(PROMOTION.sha((first / asset["path"]).read_bytes()),
                                 asset["sha256"])
            for addon_id, (beta, stable) in PROMOTION.VERSIONS.items():
                source_path = ROOT / "docs/testing/repo" / addon_id / f"{addon_id}-{beta}.zip"
                target_path = first / "repo" / addon_id / f"{addon_id}-{stable}.zip"
                with zipfile.ZipFile(source_path) as source, zipfile.ZipFile(target_path) as target:
                    self.assertIsNone(target.testzip())
                    new_note = f"{addon_id}/changelog-{stable}.txt"
                    expected = set(source.namelist()) | ({new_note} if addon_id in PROMOTION.NOTES else set())
                    self.assertEqual(set(target.namelist()), expected)
                    for name in source.namelist():
                        if name != f"{addon_id}/addon.xml":
                            self.assertEqual(source.read(name), target.read(name), name)
                    old = source.read(f"{addon_id}/addon.xml")
                    expected_xml = old.replace(f'version="{beta}"'.encode(), f'version="{stable}"'.encode())
                    if addon_id == "service.actweeter":
                        expected_xml = expected_xml.replace(
                            b'<import addon="plugin.video.xstream-pro" version="1.1.2.36~beta3" />',
                            b'<import addon="plugin.video.xstream-pro" version="1.1.2.36" />')
                        self.assertIn(b'<import addon="script.trakt" version="3.9.0" />', expected_xml)
                    if addon_id in PROMOTION.NOTES:
                        expected_xml = expected_xml.replace(
                            f"<news>changelog-{beta}.txt</news>".encode(),
                            f"<news>changelog-{stable}.txt</news>".encode())
                    self.assertEqual(target.read(f"{addon_id}/addon.xml"), expected_xml)
            with self.assertRaises(ValueError):
                PROMOTION.build(first)


if __name__ == "__main__":
    unittest.main()
