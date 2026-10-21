"""XML contracts: a modal item's missing metadata never means 'use Home's item'."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


SKIN = Path(__file__).resolve().parents[1] / "addons/skin.actweeter/1080i"


class DialogContextTests(unittest.TestCase):
    def test_retained_home_submenu_is_not_a_modal_item_context(self):
        root = ET.parse(SKIN / "Includes.xml").getroot()
        expression = root.find("./expression[@name='IsMainMenuOpened']").text
        self.assertEqual(expression,
            "!Window.IsVisible(DialogVideoInfo.xml) + [ControlGroup(9001).HasFocus() | "
            "Control.HasFocus(900) | String.IsEqual(Window(Home).Property(ShowViewSubMenu),show)]")

    def test_missing_dialog_fanart_stops_before_container_and_home_fallbacks(self):
        root = ET.parse(SKIN / "IncludesBackgroundBuilding.xml").getroot()
        first = root.find("./variable[@name='fanartBackground']/value")
        self.assertEqual(first.get("condition"), "Window.IsVisible(DialogVideoInfo.xml)")
        self.assertEqual(first.text, "$INFO[ListItem.Art(fanart)]")

    def test_shared_metadata_fallbacks_require_scoped_home_context(self):
        root = ET.parse(SKIN / "IncludesBingie.xml").getroot()
        for name in ("BingieInfoClearlogo", "GetYear", "GetDuration", "GetGenres",
                     "GetResolution", "GetAudioChannels", "TVShowTitle"):
            with self.subTest(variable=name):
                values = root.find("./variable[@name='%s']" % name).findall("value")
                home = [v for v in values if "Window(Home).Property(ListItem." in ET.tostring(v, encoding="unicode")]
                self.assertTrue(home)
                for value in home:
                    self.assertIn("$EXP[IsMainMenuOpened]", value.get("condition", ""))

    def test_sd_alternatives_cannot_bypass_the_home_context_guard(self):
        root = ET.parse(SKIN / "IncludesBingie.xml").getroot()
        values = root.find("./variable[@name='GetResolution']").findall("value")
        condition = next(v.get("condition") for v in values
                         if v.text == "SD" and "Window(Home)" in v.get("condition", ""))
        self.assertTrue(condition.startswith("$EXP[IsMainMenuOpened] + ["))
        self.assertTrue(condition.endswith("]"))


if __name__ == "__main__":
    unittest.main()
