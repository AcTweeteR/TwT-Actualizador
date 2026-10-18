"""Source-only safety gates for the approved in-place Kodi Master integration."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from xml.etree import ElementTree as ET

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "tools/integrate_master_runtime.py"
spec = importlib.util.spec_from_file_location("master_inplace", SCRIPT)
master = importlib.util.module_from_spec(spec)
spec.loader.exec_module(master)


class MasterInplaceIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = master.inventory()

    def test_versions_match_combined_master_components(self):
        for addon, required in master.EXPECTED.items():
            with self.subTest(addon=addon):
                self.assertEqual(
                    master.version(self.files[addon + "/addon.xml"]), required)

    def test_preserves_generated_skinshortcuts_and_never_writes_profile(self):
        self.assertNotIn(master.GENERATED, self.files)
        self.assertTrue(all(
            any(path.startswith(addon + "/") for addon in master.ADDONS)
            for path in self.files))
        self.assertFalse(any(path.startswith(("userdata/", "addon_data/"))
                             for path in self.files))
        self.assertTrue(any(
            path.startswith("skin.actweeter/shortcuts/") for path in self.files))

    def test_source_still_has_master_manual_spotlight_trailer_contract(self):
        candidate = self.files[
            "skin.actweeter/1080i/IncludesBingie.xml"].decode()
        for contract in master.TRAILER_ANCHORS:
            with self.subTest(contract=contract):
                self.assertIn(contract, candidate)

    def test_requires_restorable_versions_and_protected_ui(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            backup = root / "backup"
            installed = root / "kodi/addons"
            for addon in master.ADDONS:
                (installed / addon).mkdir(parents=True)
                (backup / "addons" / addon).mkdir(parents=True)
                original = b'<addon id="%b" version="old"/>' % addon.encode()
                (installed / addon / "addon.xml").write_bytes(original)
                (backup / "addons" / addon / "addon.xml").write_bytes(original)
            with self.assertRaises(RuntimeError):
                # A snapshot without the original UI is not a full backup.
                (backup / "addons/skin.actweeter/addon.xml").unlink()
                master.require_backup(backup, installed)


if __name__ == "__main__":
    unittest.main()
