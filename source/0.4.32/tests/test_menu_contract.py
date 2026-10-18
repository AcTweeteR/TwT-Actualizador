"""Default AcTweeteR navigation contract for clean profiles."""
import unittest
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET
from unittest.mock import patch


ADDON = (Path(__file__).resolve().parents[1] /
         "addons/skin.actweeter")
SERVICE_LIB = Path(__file__).resolve().parents[1] / "addons/service.actweeter/resources/lib"
sys.path.insert(0, str(SERVICE_LIB))
import interface_layout


def shortcuts(filename):
    root = ET.parse(ADDON / "shortcuts" / filename).getroot()
    return [
        (item.findtext("label"), item.findtext("action"),
         item.findtext("defaultID"), item.findtext("icon"))
        for item in root.findall("shortcut")
    ]


class MenuContractTests(unittest.TestCase):
    def test_main_menu_has_exactly_the_five_requested_destinations(self):
        self.assertEqual(
            shortcuts("mainmenu.DATA.xml"),
            [
                ("INICIO", "ActivateWindow(home,return)", "home", "shortcuts/home.png"),
                ("TV", "ActivateWindow(TVGuide,return)", "livetv", "shortcuts/tv.png"),
                ("PELÍCULAS", "ActivateWindow(1111,return)", "movies", "shortcuts/clapperboard.png"),
                ("SERIES", "ActivateWindow(1110,return)", "shows", "shortcuts/tv.png"),
                ("BUSCAR", "ActivateWindow(1109,return)", "search", "shortcuts/search.png"),
            ],
        )

    def test_bottom_menu_has_exactly_settings_catalog_refresh_and_skin_reload(self):
        self.assertEqual(
            shortcuts("powermenu.DATA.xml"),
            [
                ("AJUSTES", "ActivateWindow(Settings)", "5", "common/settings1.png"),
                ("RECARGAR CATÁLOGO", "RunScript(service.actweeter,catalog_refresh)",
                 "actweeter-catalog-refresh", "shortcuts/new.png"),
                ("RECARGAR", "ReloadSkin()", "31501", "common/reload-skin.png"),
            ],
        )

    def test_bottom_menu_geometry_fits_three_native_55_pixel_rows(self):
        root = ET.parse(ADDON / "1080i/IncludesBingie.xml").getroot()
        control = root.find(".//control[@type='list'][@id='40003']")
        self.assertIsNotNone(control)
        top, height = int(control.findtext("top")), int(control.findtext("height"))
        row_heights = {
            int(layout.get("height"))
            for layout in control.findall("itemlayout") + control.findall("focusedlayout")
        }
        self.assertEqual(row_heights, {55})
        self.assertGreaterEqual(height, 3 * 55)
        self.assertLessEqual(top + height, 1080)

    def test_refresh_actions_are_owned_by_the_bottom_menu_only(self):
        main = shortcuts("mainmenu.DATA.xml")
        bottom = shortcuts("powermenu.DATA.xml")
        self.assertFalse(any("catalog_refresh" in action or "ReloadSkin" in action
                             for _, action, _, _ in main))
        self.assertEqual(sum("catalog_refresh" in action
                             for _, action, _, _ in bottom), 1)
        self.assertEqual(sum("ReloadSkin" in action
                             for _, action, _, _ in bottom), 1)

    def test_last_main_menu_item_routes_down_to_power_menu(self):
        root = ET.parse(ADDON / "1080i/IncludesBingie.xml").getroot()
        main = root.find(".//control[@type='list'][@id='900']")
        self.assertIsNotNone(main)
        down = [(node.get("condition", ""), node.text or "")
                for node in main.findall("ondown")]
        self.assertIn((
            "$EXP[IsBingieViewsActive] + String.IsEmpty(Container(900).ListItemNoWrap(1).Label)",
            "40003",
        ), down)
        self.assertIn("!String.IsEmpty", down[1][0])
        self.assertEqual(down[1][1], "77777")
        self.assertIn("!String.IsEmpty", down[3][0])
        self.assertEqual(down[3][1], "noop")

    def test_power_menu_returns_to_main_menu_and_keeps_native_item_navigation(self):
        root = ET.parse(ADDON / "1080i/IncludesBingie.xml").getroot()
        power = root.find(".//control[@type='list'][@id='40003']")
        self.assertIsNotNone(power)
        self.assertEqual(power.findtext("onup"), "900")
        self.assertEqual(power.findtext("ondown"), "noop")
        self.assertEqual(power.findtext("content/include"),
                         "skinshortcuts-group-powermenu")

    def test_layout_migration_tracks_power_menu_as_profile_data(self):
        self.assertIn("powermenu", interface_layout.GROUPS)
        manifest = json.loads((Path(__file__).resolve().parents[1] /
                               "addons/service.actweeter/resources/structural_manifest.json").read_text())
        self.assertIn({
            "source": "addon_data/script.skinshortcuts/skin.actweeter-powermenu.DATA.xml",
            "target": "addon_data/script.skinshortcuts/skin.actweeter-powermenu.DATA.xml",
        }, manifest["files"])

    def test_legacy_fingerprints_are_the_verified_beta8_defaults(self):
        self.assertEqual(
            interface_layout.LEGACY_DEFAULT_DIGESTS[
                "skin.actweeter-mainmenu.DATA.xml"],
            frozenset({"b192494c629248385a11590e3a74671da0cc2ea35cf5b587d5e56abc065f3323"}),
        )
        self.assertEqual(
            interface_layout.LEGACY_DEFAULT_DIGESTS[
                "skin.actweeter-powermenu.DATA.xml"],
            frozenset({"b7e095f1a53aa510ce0e2150d134b871bedebbc8980e9514ab94f449bd4f646c"}),
        )

    def test_clean_profile_seeds_both_menus_and_backups_the_absence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shortcuts = root / "profile"
            service = root / "service"
            shortcuts.mkdir()
            service.mkdir()
            result = interface_layout.apply_layout(
                shortcuts, service, ADDON, interface_layout.SETTINGS)
            self.assertEqual(result["status"], "APPLIED")
            for group in ("mainmenu", "powermenu"):
                profile_file = shortcuts / ("skin.actweeter-" + group + ".DATA.xml")
                expected = (ADDON / "shortcuts" / (group + ".DATA.xml")).read_bytes()
                self.assertEqual(profile_file.read_bytes(), expected)
            backup = service / "interface_backups" / result["backup"]
            backup_manifest = json.loads((backup / "MANIFEST.json").read_text())
            for group in ("mainmenu", "powermenu"):
                name = "skin.actweeter-" + group + ".DATA.xml"
                self.assertFalse(backup_manifest["files"][name]["exists"])

    def test_beta8_defaults_migrate_with_verified_backup_and_repeat_idempotently(self):
        previous_main = b"<shortcuts><shortcut><label>legacy-main</label></shortcut></shortcuts>"
        previous_power = b"<shortcuts><shortcut><label>legacy-power</label></shortcut></shortcuts>"
        legacy_hashes = {
            "skin.actweeter-mainmenu.DATA.xml": hashlib.sha256(previous_main).hexdigest(),
            "skin.actweeter-powermenu.DATA.xml": hashlib.sha256(previous_power).hexdigest(),
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shortcuts = root / "userdata/addon_data/script.skinshortcuts"
            service = root / "service"
            shortcuts.mkdir(parents=True)
            (shortcuts / "skin.actweeter-mainmenu.DATA.xml").write_bytes(previous_main)
            (shortcuts / "skin.actweeter-powermenu.DATA.xml").write_bytes(previous_power)
            service.mkdir()
            (service / "interface_layout_state.json").write_text(json.dumps({
                "layout_version": 12, "files": {}, "settings": interface_layout.SETTINGS,
            }))
            with patch.dict(interface_layout.LEGACY_DEFAULT_DIGESTS, {
                name: frozenset({value}) for name, value in legacy_hashes.items()
            }, clear=False):
                result = interface_layout.apply_layout(
                    shortcuts, service, ADDON, interface_layout.SETTINGS)
                self.assertEqual(result["status"], "APPLIED")
                self.assertEqual(interface_layout.LAYOUT_VERSION, 13)
                for name, wanted in (("skin.actweeter-mainmenu.DATA.xml",
                                      (ADDON / "shortcuts/mainmenu.DATA.xml").read_bytes()),
                                     ("skin.actweeter-powermenu.DATA.xml",
                                      (ADDON / "shortcuts/powermenu.DATA.xml").read_bytes())):
                    self.assertEqual((shortcuts / name).read_bytes(), wanted)
                backup = service / "interface_backups" / result["backup"]
                manifest = json.loads((backup / "MANIFEST.json").read_text())
                for name, old in (("skin.actweeter-mainmenu.DATA.xml", previous_main),
                                  ("skin.actweeter-powermenu.DATA.xml", previous_power)):
                    saved = (backup / name).read_bytes()
                    self.assertEqual(saved, old)
                    self.assertEqual(manifest["files"][name]["sha256"],
                                     hashlib.sha256(old).hexdigest())
                repeated = interface_layout.apply_layout(
                    shortcuts, service, ADDON, interface_layout.SETTINGS)
                self.assertEqual(repeated["status"], "CURRENT")

    def test_customized_power_menu_is_preserved_and_reported(self):
        original = b"<shortcuts><shortcut><label>user custom</label></shortcut></shortcuts>"
        known_default = b"<shortcuts><shortcut><label>legacy power</label></shortcut></shortcuts>"
        name = "skin.actweeter-powermenu.DATA.xml"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shortcuts = root / "profile"
            service = root / "service"
            shortcuts.mkdir()
            service.mkdir()
            target = shortcuts / name
            target.write_bytes(original)
            (service / "interface_layout_state.json").write_text(json.dumps({
                "layout_version": 12, "files": {}, "settings": interface_layout.SETTINGS,
            }))
            with patch.dict(interface_layout.LEGACY_DEFAULT_DIGESTS, {
                name: frozenset({hashlib.sha256(known_default).hexdigest()})
            }, clear=False):
                result = interface_layout.apply_layout(
                    shortcuts, service, ADDON, interface_layout.SETTINGS)
            self.assertEqual(result["status"], "CONSENT_REQUIRED")
            self.assertIn(name, result["conflicts"])
            self.assertEqual(target.read_bytes(), original)

    def test_migration_write_failure_restores_original_menu_files(self):
        original = b"<shortcuts><shortcut><label>legacy</label></shortcut></shortcuts>"
        names = ("skin.actweeter-mainmenu.DATA.xml", "skin.actweeter-powermenu.DATA.xml")
        legacy = {name: frozenset({hashlib.sha256(original).hexdigest()}) for name in names}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shortcuts = root / "profile"
            service = root / "service"
            shortcuts.mkdir()
            service.mkdir()
            for name in names:
                (shortcuts / name).write_bytes(original)
            (service / "interface_layout_state.json").write_text(json.dumps({
                "layout_version": 12, "files": {}, "settings": interface_layout.SETTINGS,
            }))
            calls = {"count": 0}

            def fail_after_first(path, data):
                calls["count"] += 1
                if calls["count"] == 2:
                    raise OSError("simulated disk failure")
                interface_layout.atomic_write(path, data)

            with patch.dict(interface_layout.LEGACY_DEFAULT_DIGESTS, legacy, clear=False):
                with self.assertRaisesRegex(OSError, "simulated disk failure"):
                    interface_layout.apply_layout(
                        shortcuts, service, ADDON, interface_layout.SETTINGS,
                        writer=fail_after_first)
            for name in names:
                self.assertEqual((shortcuts / name).read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
