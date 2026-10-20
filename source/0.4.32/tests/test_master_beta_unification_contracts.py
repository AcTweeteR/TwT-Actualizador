"""Regression contracts for behavior recovered from Master and Lenovo Beta."""
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MasterBetaUnificationContracts(unittest.TestCase):
    def test_manual_trailer_primary_action_supports_movies_and_series(self):
        root = ET.parse(ROOT / "addons/skin.actweeter/1080i/IncludesFunctions.xml").getroot()
        include = root.find("./include[@name='AcTweeteR_Primary_Trailer_Action']")
        actions = [node for node in include.findall("onclick")
                   if "slyguy.trailers" in node.get("condition", "")
                   and node.text != "RunScript(slyguy.trailers)"]
        self.assertEqual(len(actions), 8)
        for action in actions:
            condition = action.get("condition", "")
            self.assertIn("String.IsEqual(ListItem.DBType,movie)", condition)
            self.assertIn("String.IsEqual(ListItem.DBType,tvshow)", condition)
        self.assertTrue(any(node.text == "RunScript(service.actweeter,preview_manual)"
                            for node in actions))
        self.assertTrue(any(node.text == "RunScript(slyguy.trailers)"
                            for node in include.findall("onclick")))

    def test_automatic_preview_remains_opt_in_per_surface(self):
        skin = ROOT / "addons/skin.actweeter/1080i"
        for filename, include_name, setting in (
                ("IncludesBingie.xml", "BingieSpotlightWidget", "SpotLightTrailers"),
                ("IncludesHomeWidgets.xml", "WidgetBaseBingieIncludes", "BingieAutoTrailer")):
            root = ET.parse(skin / filename).getroot()
            node = root.find("./include[@name='%s']" % include_name)
            if filename == "IncludesBingie.xml":
                node = node.find("control")
            action = next(n for n in node.findall("onfocus")
                          if "preview_focus" in (n.text or ""))
            self.assertIn("Skin.HasSetting(%s)" % setting, action.get("condition", ""))

    def test_xstream_premium_catalog_records_unfiltered_series_once_per_profile_window(self):
        patch = (ROOT / "third_party/xstream/patches/1.1.2/actweeter-runtime.patch").read_text()
        start = patch.index("+++ b/resources/lib/premium_routes.py")
        end_match = re.search(r"^diff --git ", patch[start:], re.MULTILINE)
        end = start + end_match.start() if end_match else -1
        section = patch[start:end if end >= 0 else len(patch)]
        catalog = section[section.index("+def catalog("):]
        hook = "g['series_changes'].record_catalog(g['addon'], pnum, items)"
        self.assertIn("+    if stype == 'series' and items and host and user and password:", catalog)
        self.assertIn("+            " + hook, catalog)
        self.assertLess(catalog.index(hook), catalog.index("+    categories ="))
        start = patch.index("+++ b/resources/lib/series_changes.py")
        end_match = re.search(r"^diff --git ", patch[start:], re.MULTILINE)
        end = start + end_match.start() if end_match else -1
        changes = patch[start:end if end >= 0 else len(patch)]
        self.assertIn("+CATALOG_INTERVAL = 6 * 3600", changes)
        self.assertIn("+    if not force and now - float(data.get(\"catalog_checked\", 0) or 0) < CATALOG_INTERVAL:", changes)

    def test_service_does_not_override_kodi_wide_addon_update_preference(self):
        service = (ROOT / "addons/service.actweeter/service.py").read_text()
        self.assertNotIn("addon_update_policy", service)
        self.assertNotIn("ADDON_UPDATE_POLICY", service)
        self.assertFalse((ROOT / "addons/service.actweeter/resources/lib/addon_update_policy.py").exists())

    def test_xstream_setup_accepts_installed_beta_and_candidate_versions(self):
        source = (ROOT / "addons/service.actweeter/resources/lib/xstream_setup.py").read_text()
        self.assertIn('"1.1.2.9"', source)
        self.assertIn('"1.1.2.10"', source)


if __name__ == "__main__":
    unittest.main()
