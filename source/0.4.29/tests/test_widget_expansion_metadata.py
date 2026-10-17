import sys
import tempfile
import unittest
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addons/service.actweeter/resources/lib"))
import interface_layout  # noqa: E402


class ExpandableWidgetMetadataTests(unittest.TestCase):
    def test_supported_provider_list_route_gets_expansion_without_rewriting_reload(self):
        route = (
            "plugin://plugin.video.xstream-pro/?mode=premium&view=continue&"
            "stype=movie&reload=$INFO[Window(Home).Property(Refresh)]"
        )
        expanded, enabled = interface_layout.expandable_widget_action(route)
        self.assertTrue(enabled)
        self.assertTrue(expanded.startswith(route + "&"))
        self.assertIn("actweeter_expand=1&limit=20", expanded)
        self.assertEqual(interface_layout.expandable_widget_action(expanded), (expanded, True))

    def test_non_list_and_non_provider_routes_are_not_expandable(self):
        routes = (
            "plugin://plugin.video.xstream-pro/?mode=movies_menu",
            "plugin://plugin.video.xstream-pro/?mode=premium&view=collections_root&stype=movie",
            "plugin://plugin.video.xstream-pro/?mode=xstream_trakt_list&section=recommendations&tmdb_type=movie",
            "plugin://plugin.video.youtube/?video_id=example",
        )
        for route in routes:
            with self.subTest(route=route):
                self.assertEqual(interface_layout.expandable_widget_action(route), (route, False))

    def test_source_documents_marks_only_supported_default_rows_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            skin = Path(temp)
            shortcuts = skin / "shortcuts"
            shortcuts.mkdir()
            rows = {
                "mainmenu": [("Inicio", "ActivateWindow(Home)")],
                "inicio-1": [
                    ("Continue", "plugin://plugin.video.xstream-pro/?mode=premium&view=continue&stype=both&reload=$INFO[Window(Home).Property(R)]"),
                    ("Movies", "plugin://plugin.video.xstream-pro/?mode=premium&stype=movie"),
                    ("Collections", "plugin://plugin.video.xstream-pro/?mode=premium&view=collections_root&stype=movie"),
                ],
                "10000-1": [("Series", "plugin://plugin.video.xstream-pro/?mode=premium&stype=series")],
                "moviehub": [("Popular", "plugin://plugin.video.xstream-pro/?mode=premium&view=popular&stype=movie")],
                "tvshowhub": [("Recommendations", "plugin://plugin.video.xstream-pro/?mode=xstream_trakt_list&section=recommendations&tmdb_type=tv")],
            }
            for group, items in rows.items():
                root = ET.Element("shortcuts")
                for label, action in items:
                    shortcut = ET.SubElement(root, "shortcut")
                    ET.SubElement(shortcut, "label").text = label
                    ET.SubElement(shortcut, "label2")
                    ET.SubElement(shortcut, "action").text = action
                (shortcuts / (group + ".DATA.xml")).write_bytes(ET.tostring(root))

            output = interface_layout.source_documents(skin)
            self.assertEqual(output, interface_layout.source_documents(skin))
            home = ET.fromstring(output["skin.actweeter-inicio-1.DATA.xml"])
            first = home.find("shortcut")
            route = first.findtext("action")
            self.assertIn("reload=$INFO[Window(Home).Property(R)]&amp;actweeter_expand=1&amp;limit=20", ET.tostring(first, encoding="unicode"))
            self.assertEqual(first.findtext("property"), "true")
            self.assertIn("actweeter_expand=1", route)

            movies = ET.fromstring(output["skin.actweeter-moviehub.DATA.xml"])
            popular = movies.find("shortcut")
            self.assertEqual(popular.findtext("property"), "true")

            series = ET.fromstring(output["skin.actweeter-tvshowhub.DATA.xml"])
            self.assertNotIn("actweeter_expand=1", series.findtext("shortcut/action"))
            self.assertIsNone(series.find("shortcut/property"))

    def test_upgrade_migrates_owned_shortcuts_with_backup(self):
        old_skin = ROOT.parent / "0.4.28/addons/skin.actweeter"
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            shortcuts = temp / "userdata/addon_data/script.skinshortcuts"
            service = temp / "service"
            shortcuts.mkdir(parents=True)
            old_docs = {
                "skin.actweeter-" + group + ".DATA.xml":
                    (old_skin / "shortcuts" / (group + ".DATA.xml")).read_bytes()
                for group in interface_layout.GROUPS
            }
            old_hashes = {}
            for name, data in old_docs.items():
                (shortcuts / name).write_bytes(data)
                old_hashes[name] = hashlib.sha256(data).hexdigest()
            (service / "interface_layout_state.json").parent.mkdir(parents=True)
            (service / "interface_layout_state.json").write_text(json.dumps({
                "layout_version": 8,
                "files": old_hashes,
                "settings": interface_layout.SETTINGS,
            }), encoding="utf-8")

            result = interface_layout.apply_layout(
                shortcuts, service, ROOT / "addons/skin.actweeter",
                interface_layout.SETTINGS)
            self.assertEqual(result["status"], "APPLIED")
            migrated = ET.parse(shortcuts / "skin.actweeter-moviehub.DATA.xml").getroot()
            self.assertIn("actweeter_expand=1", migrated.findtext("shortcut/action"))
            manifest = json.loads((service / "interface_backups" / result["backup"] / "MANIFEST.json").read_text())
            self.assertTrue(manifest["files"]["skin.actweeter-moviehub.DATA.xml"]["exists"])

    def test_upgrade_refuses_to_overwrite_customized_shortcuts_without_consent(self):
        old_skin = ROOT.parent / "0.4.28/addons/skin.actweeter"
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            shortcuts = temp / "userdata/addon_data/script.skinshortcuts"
            service = temp / "service"
            shortcuts.mkdir(parents=True)
            old_docs = {
                "skin.actweeter-" + group + ".DATA.xml":
                    (old_skin / "shortcuts" / (group + ".DATA.xml")).read_bytes()
                for group in interface_layout.GROUPS
            }
            old_hashes = {}
            for name, data in old_docs.items():
                old_hashes[name] = hashlib.sha256(data).hexdigest()
                (shortcuts / name).write_bytes(data)
            target = shortcuts / "skin.actweeter-moviehub.DATA.xml"
            customized = target.read_bytes() + b"\n<!-- user edit -->\n"
            target.write_bytes(customized)
            service.mkdir()
            (service / "interface_layout_state.json").write_text(json.dumps({
                "layout_version": 8,
                "files": old_hashes,
                "settings": interface_layout.SETTINGS,
            }), encoding="utf-8")

            result = interface_layout.apply_layout(
                shortcuts, service, ROOT / "addons/skin.actweeter",
                interface_layout.SETTINGS)
            self.assertEqual(result["status"], "CONSENT_REQUIRED")
            self.assertEqual(target.read_bytes(), customized)

    def test_skin_templates_use_explicit_flag_not_full_plugin_url_condition(self):
        include_file = ROOT / "addons/skin.actweeter/1080i/IncludesHomeWidgets.xml"
        template_file = ROOT / "addons/skin.actweeter/shortcuts/template.xml"
        include_text = include_file.read_text(encoding="utf-8")
        template_text = template_file.read_text(encoding="utf-8")
        self.assertNotIn("String.Contains($PARAM[widgetPath]", include_text)
        self.assertIn('String.IsEqual($PARAM[widgetExpandable],true)', include_text)
        self.assertIn('name="widgetExpandable"', template_text)

    def test_generated_layout_requires_route_and_template_expansion_metadata(self):
        route = "plugin://plugin.video.xstream-pro/?mode=premium&view=popular&stype=movie&actweeter_expand=1&limit=20"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "generated.xml"
            root = ET.Element("includes")
            include = ET.SubElement(root, "include", name="skinshortcuts-template-moviehub")
            row = ET.SubElement(include, "include", content="widget_base")
            ET.SubElement(row, "param", name="widgetPath", value=route)
            ET.SubElement(row, "param", name="widgetName", value="Populares")
            ET.SubElement(row, "param", name="widgetExpandable", value="true")
            path.write_bytes(ET.tostring(root))
            row_data = interface_layout.generated_rows(path)["moviehub"][0]
            self.assertTrue(row_data["provider_only"])
            self.assertTrue(row_data["expandable"])
            self.assertTrue(row_data["expansion_ready"])

            row.find("param[@name='widgetExpandable']").set("value", "false")
            path.write_bytes(ET.tostring(root))
            row_data = interface_layout.generated_rows(path)["moviehub"][0]
            self.assertFalse(row_data["expansion_ready"])


if __name__ == "__main__":
    unittest.main()
