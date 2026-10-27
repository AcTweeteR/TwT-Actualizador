"""Default AcTweeteR navigation contract for clean profiles."""
import ast
import unittest
import hashlib
import json
import os
import sys
import tempfile
import zipfile
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
    def test_main_menu_has_trakt_and_keeps_arcade_below_rivulet(self):
        self.assertEqual(
            shortcuts("mainmenu.DATA.xml"),
            [
                ("INICIO", "ActivateWindow(home,return)", "home", "shortcuts/home.png"),
                ("TV", "ActivateWindow(TVGuide,return)", "livetv", "shortcuts/tv.png"),
                ("PELÍCULAS", "ActivateWindow(1111,return)", "movies", "shortcuts/clapperboard.png"),
                ("SERIES", "ActivateWindow(1110,return)", "shows", "shortcuts/tv.png"),
                ("BUSCAR", "ActivateWindow(1109,return)", "search", "shortcuts/search.png"),
                ("TRAKT", "ActivateWindow(Videos,plugin://plugin.video.xstream-pro/?mode=xstream_tmdb_trakt_menu,return)",
                 "trakt", "special://home/addons/plugin.video.xstream-pro/resources/icons/trakt.png"),
                ("RIVULET", "RunAddon(plugin.video.rivulet)",
                 "rivulet", "shortcuts/rivulet.png"),
                ("ARCADE", "RunAddon(plugin.program.iagl)",
                 "arcade", "shortcuts/arcade.png"),
            ],
        )

    def test_menu_icons_are_in_kodi_texture_search_path(self):
        # Kodi resolves shortcut textures against media/, not shortcuts/.
        for name in ('rivulet', 'arcade'):
            icon = ADDON / 'media' / 'shortcuts' / (name + '.png')
            self.assertTrue(icon.is_file(), name)
            self.assertEqual(icon.read_bytes()[:8], b'\x89PNG\r\n\x1a\n')

    def test_rivulet_has_its_own_icon_and_visual_separator(self):
        self.assertTrue((ADDON / "shortcuts/rivulet.png").is_file())
        xml = (ADDON / "1080i/IncludesBingie.xml").read_text()
        self.assertIn("String.IsEqual(ListItem.Label,RIVULET)", xml)
        self.assertIn("shortcuts/rivulet-separator.png", xml)

    def test_arcade_icon_and_profile_merge_preserve_custom_menu_rows(self):
        self.assertTrue((ADDON / "shortcuts/arcade.png").is_file())
        custom = b'<shortcuts><shortcut><label>RIVULET</label><defaultID>rivulet</defaultID></shortcut><shortcut><label>Mi acceso</label><defaultID>user-item</defaultID></shortcut></shortcuts>'
        merged = ET.fromstring(interface_layout.merge_arcade_shortcut(
            custom, (ADDON / "shortcuts/mainmenu.DATA.xml").read_bytes()))
        self.assertEqual([node.findtext("defaultID") for node in merged.findall("shortcut")],
                         ["trakt", "rivulet", "arcade", "user-item"])
        self.assertEqual(merged.find("shortcut[defaultID='arcade']/action").text,
                         "RunAddon(plugin.program.iagl)")

    def test_trakt_migrates_into_existing_profile_and_preserves_custom_rows(self):
        defaults = (ADDON / "shortcuts/mainmenu.DATA.xml").read_bytes()
        old = ET.fromstring(defaults)
        trakt = old.find("shortcut[defaultID='trakt']")
        if trakt is not None:
            old.remove(trakt)
        custom = ET.SubElement(old, "shortcut")
        ET.SubElement(custom, "label").text = "Mi acceso"
        ET.SubElement(custom, "defaultID").text = "user-item"
        ET.SubElement(custom, "action").text = "ActivateWindow(Settings)"
        original = ET.tostring(old, encoding="utf-8", xml_declaration=True) + b"\n"
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            profile, service = base / "profile", base / "service"
            profile.mkdir(); service.mkdir()
            path = profile / "skin.actweeter-mainmenu.DATA.xml"
            path.write_bytes(original)
            (service / "interface_layout_state.json").write_text(json.dumps({
                "layout_version": 16,
                "files": {path.name: interface_layout.digest(original)},
                "settings": interface_layout.SETTINGS,
                "build_status": "GENERATED",
            }))
            result = interface_layout.apply_layout(
                profile, service, ADDON, interface_layout.SETTINGS)
            self.assertEqual(result["status"], "APPLIED")
            after = ET.parse(path).getroot()
            ids = [node.findtext("defaultID") for node in after.findall("shortcut")]
            self.assertLess(ids.index("search"), ids.index("trakt"))
            self.assertEqual(ids.index("trakt"), ids.index("rivulet") - 1)
            self.assertEqual(ET.tostring(after.find("shortcut[defaultID='user-item']")),
                             ET.tostring(custom))
            backup = service / "interface_backups" / result["backup"] / path.name
            self.assertEqual(backup.read_bytes(), original)
            self.assertEqual(interface_layout.apply_layout(
                profile, service, ADDON, interface_layout.SETTINGS)["status"], "CURRENT")

    @unittest.skipUnless(all(os.environ.get(name) for name in (
            "ACTWEETER_SKIN_LIVE_ZIP", "ACTWEETER_SERVICE_LIVE_ZIP",
            "ACTWEETER_XSTREAM_LIVE_ZIP")),
        "requires exact candidate ZIPs for the full Trakt menu contract")
    def test_candidate_zips_keep_trakt_menu_migration_and_route_connected(self):
        with zipfile.ZipFile(os.environ["ACTWEETER_SKIN_LIVE_ZIP"]) as archive:
            menu = ET.fromstring(archive.read("skin.actweeter/shortcuts/mainmenu.DATA.xml"))
            trakt = menu.find("shortcut[defaultID='trakt']")
            self.assertIsNotNone(trakt)
            self.assertEqual(trakt.findtext("label"), "TRAKT")
            self.assertEqual(trakt.findtext("action"),
                "ActivateWindow(Videos,plugin://plugin.video.xstream-pro/?mode=xstream_tmdb_trakt_menu,return)")
        with zipfile.ZipFile(os.environ["ACTWEETER_SERVICE_LIVE_ZIP"]) as archive:
            layout = archive.read(
                "service.actweeter/resources/lib/interface_layout.py").decode()
            self.assertIn("interface-layout-v18-trakt-home-recommendations", layout)
            self.assertIn("current_root.find(\"shortcut[defaultID='trakt']\")", layout)
        with zipfile.ZipFile(os.environ["ACTWEETER_XSTREAM_LIVE_ZIP"]) as archive:
            addon = archive.read(
                "plugin.video.xstream-pro/resources/lib/addon.py").decode()
            routes = archive.read(
                "plugin.video.xstream-pro/resources/lib/tmdb_routes.py").decode()
            self.assertIn('mode == "xstream_tmdb_trakt_menu"', addon)
            trakt_menu = next(node for node in ast.parse(routes).body
                              if isinstance(node, ast.FunctionDef)
                              and node.name == "trakt_menu")
            self.assertFalse(any(isinstance(node, ast.Call)
                                and isinstance(node.func, ast.Name)
                                and node.func.id == "_trakt_guard"
                                for node in ast.walk(trakt_menu)))
            self.assertIn("Authorize Trakt", ast.get_source_segment(routes, trakt_menu))

    def test_shipped_launcher_upgrade_preserves_custom_rows_and_is_idempotent(self):
        defaults = (ADDON / "shortcuts/mainmenu.DATA.xml").read_bytes()
        old = ET.fromstring(defaults)
        old.find("shortcut[defaultID='rivulet']/action").text = (
            "ActivateWindow(Videos,plugin://plugin.video.rivulet/,return)")
        arcade = old.find("shortcut[defaultID='arcade']")
        arcade.find('action').text = "ActivateWindow(Programs,plugin://plugin.program.iagl/,return)"
        arcade.find('icon').text = 'shortcuts/rivulet.png'
        custom = ET.SubElement(old, 'shortcut')
        ET.SubElement(custom, 'defaultID').text = 'user-item'
        ET.SubElement(custom, 'label').text = 'Mi acceso'
        ET.SubElement(custom, 'action').text = 'ActivateWindow(Settings)'
        old.remove(arcade)
        old.insert(0, arcade)
        original = ET.tostring(old)
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            profile, service = base / 'profile', base / 'service'
            profile.mkdir(); service.mkdir()
            path = profile / 'skin.actweeter-mainmenu.DATA.xml'
            path.write_bytes(original)
            (service / 'interface_layout_state.json').write_text(json.dumps({
                'layout_version': 15, 'files': {}, 'settings': interface_layout.SETTINGS,
            }))
            result = interface_layout.apply_layout(profile, service, ADDON, interface_layout.SETTINGS)
            self.assertEqual(result['status'], 'APPLIED')
            after = ET.parse(path).getroot()
            ids = [node.findtext('defaultID') for node in after.findall('shortcut')]
            self.assertEqual(ids.index('arcade'), ids.index('rivulet') + 1)
            self.assertEqual(after.find("shortcut[defaultID='rivulet']/action").text,
                             'RunAddon(plugin.video.rivulet)')
            self.assertEqual(after.find("shortcut[defaultID='arcade']/action").text,
                             'RunAddon(plugin.program.iagl)')
            self.assertEqual(after.find("shortcut[defaultID='arcade']/icon").text,
                             'shortcuts/arcade.png')
            self.assertEqual(ET.tostring(after.find("shortcut[defaultID='user-item']")),
                             ET.tostring(custom))
            backup = service / 'interface_backups' / result['backup'] / path.name
            self.assertEqual(backup.read_bytes(), original)
            self.assertEqual(interface_layout.apply_layout(
                profile, service, ADDON, interface_layout.SETTINGS)['status'], 'CURRENT')

    def test_custom_launcher_actions_labels_and_icons_are_preserved(self):
        defaults = (ADDON / "shortcuts/mainmenu.DATA.xml").read_bytes()
        root = ET.fromstring(defaults)
        root.find("shortcut[defaultID='rivulet']/action").text = 'RunScript(user.rivulet)'
        arcade = root.find("shortcut[defaultID='arcade']")
        arcade.find('action').text = 'RunScript(user.games)'
        arcade.find('label').text = 'Mis juegos'
        arcade.find('icon').text = '/custom/gamepad.png'
        root.remove(arcade)
        root.insert(0, arcade)
        current = ET.tostring(root)
        self.assertEqual(interface_layout.merge_arcade_shortcut(current, defaults), current)

    def test_custom_arcade_icon_survives_shipped_action_repair(self):
        defaults = (ADDON / "shortcuts/mainmenu.DATA.xml").read_bytes()
        root = ET.fromstring(defaults)
        arcade = root.find("shortcut[defaultID='arcade']")
        arcade.find('action').text = 'ActivateWindow(Programs,plugin://plugin.program.iagl/,return)'
        arcade.find('icon').text = '/custom/gamepad.png'
        after = ET.fromstring(interface_layout.merge_arcade_shortcut(ET.tostring(root), defaults))
        self.assertEqual(after.find("shortcut[defaultID='arcade']/icon").text,
                         '/custom/gamepad.png')
        self.assertEqual(after.find("shortcut[defaultID='arcade']/action").text,
                         'RunAddon(plugin.program.iagl)')

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
                self.assertEqual(interface_layout.LAYOUT_VERSION, 18)
                expected_main = interface_layout.merge_arcade_shortcut(
                    previous_main, (ADDON / "shortcuts/mainmenu.DATA.xml").read_bytes())
                for name, wanted in (("skin.actweeter-mainmenu.DATA.xml", expected_main),
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

    def test_arcade_migration_appends_to_customized_main_menu_without_consent(self):
        original = (ADDON / "shortcuts/mainmenu.DATA.xml").read_bytes()
        root_xml = ET.fromstring(original)
        custom = ET.SubElement(root_xml, "shortcut")
        ET.SubElement(custom, "label").text = "Mi acceso"
        ET.SubElement(custom, "label2")
        ET.SubElement(custom, "defaultID").text = "user-item"
        ET.SubElement(custom, "icon").text = "shortcuts/search.png"
        ET.SubElement(custom, "action").text = "ActivateWindow(Settings)"
        profile_bytes = ET.tostring(root_xml, encoding="utf-8", xml_declaration=True)
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            shortcuts, service = base / "profile", base / "service"
            shortcuts.mkdir(); service.mkdir()
            path = shortcuts / "skin.actweeter-mainmenu.DATA.xml"
            path.write_bytes(profile_bytes)
            (service / "interface_layout_state.json").write_text(json.dumps({
                "layout_version": 14, "files": {}, "settings": interface_layout.SETTINGS,
            }))
            result = interface_layout.apply_layout(
                shortcuts, service, ADDON, interface_layout.SETTINGS)
            self.assertEqual(result["status"], "APPLIED")
            after = ET.parse(path).getroot()
            ids = [node.findtext("defaultID") for node in after.findall("shortcut")]
            self.assertLess(ids.index("rivulet"), ids.index("arcade"))
            self.assertEqual(ids[-1], "user-item")
            self.assertEqual(after.find("shortcut[defaultID='arcade']/action").text,
                             "RunAddon(plugin.program.iagl)")
            backup = service / "interface_backups" / result["backup"]
            self.assertEqual((backup / path.name).read_bytes(), profile_bytes)

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
