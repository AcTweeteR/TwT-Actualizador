"""Beta35 promotion retains every functional file byte for byte."""
import importlib.util
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tools/promote_beta35_stable.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("promote_beta35_stable", SCRIPT)
PROMOTION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROMOTION)


class Beta35StablePromotionTest(unittest.TestCase):
    def test_reproducible_and_functional_bytes_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp) / "first", Path(tmp) / "second"
            manifest = PROMOTION.build(first)
            self.assertEqual(manifest, PROMOTION.build(second))
            for path in first.rglob("*"):
                if path.is_file():
                    self.assertEqual(path.read_bytes(),
                                     (second / path.relative_to(first)).read_bytes())
            for addon_id, (beta, stable) in PROMOTION.VERSIONS.items():
                source = ROOT / "docs/testing/repo" / addon_id / f"{addon_id}-{beta}.zip"
                target = first / "repo" / addon_id / f"{addon_id}-{stable}.zip"
                with zipfile.ZipFile(source) as before, zipfile.ZipFile(target) as after:
                    self.assertIsNone(after.testzip())
                    for name in before.namelist():
                        if name != f"{addon_id}/addon.xml":
                            self.assertEqual(before.read(name), after.read(name), name)
                    old = ET.fromstring(before.read(f"{addon_id}/addon.xml"))
                    new = ET.fromstring(after.read(f"{addon_id}/addon.xml"))
                    self.assertEqual((old.get("id"), old.get("version")), (addon_id, beta))
                    self.assertEqual((new.get("id"), new.get("version")), (addon_id, stable))
                    if addon_id == "service.actweeter":
                        required = new.find("requires/import[@addon='script.trakt']")
                        self.assertIsNotNone(required)
                        self.assertNotEqual(required.get("optional"), "true")
                        self.assertEqual(new.find(
                            "requires/import[@addon='plugin.video.xstream-pro']").get("version"),
                            PROMOTION.VERSIONS["plugin.video.xstream-pro"][1])
            with self.assertRaises(ValueError):
                PROMOTION.build(first)


if __name__ == "__main__":
    unittest.main()
