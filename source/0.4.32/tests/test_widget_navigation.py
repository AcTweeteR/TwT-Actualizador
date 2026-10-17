"""Contracts needed to diagnose and navigate the same row on touch and remote."""
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET


XML = Path(__file__).resolve().parents[1] / "addons/skin.actweeter/1080i"


class WidgetNavigationTests(unittest.TestCase):
    def test_expand_folder_has_explicit_provider_navigation_with_debug_enabled(self):
        root = ET.parse(XML / "IncludesBingie.xml").getroot()
        actions = root.find("include[@name='ContainerShowInfoOnclick']").findall("onclick")
        folder = [n for n in actions if "AcTweeteR.Expand" in n.get("condition", "")]
        self.assertEqual(len(folder), 1)
        self.assertEqual(folder[0].text,
                         "ActivateWindow(Videos,$INFO[Container($PARAM[widgetid]).ListItem.FileNameAndPath],return)")
        self.assertNotIn("1508", folder[0].text)
        self.assertNotIn("AcTweeteRTouchDiagnostics", folder[0].get("condition"))

    def test_poster_focus_frame_belongs_to_selected_item(self):
        root = ET.parse(XML / "IncludesHomeWidgets.xml").getroot()
        layout = root.find("include[@name='widget_layout_poster']")
        focused = layout.find("focusedlayout[@condition='Control.HasFocus($PARAM[widgetid])']")
        border = focused.find(".//control[@type='image']")
        self.assertEqual(border.findtext("visible"), "true")
        home = ET.parse(XML / "IncludesHomeBingie.xml").getroot()
        self.assertFalse(any(n.text == "Bingie_Screens_Fixed_Focus_Frame"
                             for n in home.iter("include")))

    def test_diagnostics_expose_counts_without_content_or_paths_in_all_surfaces(self):
        root = ET.parse(XML / "IncludesTouchDiagnostics.xml").getroot()
        overlay = root.find("include[@name='AcTweeteR_TouchDiagnosticsOverlay']")
        self.assertEqual(overlay.find("control/visible").text,
                         "Skin.HasSetting(AcTweeteRTouchDiagnostics)")
        label = "".join(n.text or "" for n in overlay.iter("label"))
        for required in ("Container.NumItems", "Container.Position", "System.CurrentControlId"):
            self.assertIn(required, label)
        for private in ("ListItem.Label", "FilenameAndPath", "FileNameAndPath", "FolderPath"):
            self.assertNotIn(private, label)
        for name in ("Home.xml", "Custom_1111_Movies_Hub.xml", "Custom_1110_TVShows_Hub.xml"):
            window = ET.parse(XML / name).getroot()
            self.assertTrue(any(n.text == "AcTweeteR_TouchDiagnosticsOverlay"
                                for n in window.iter("include")))

    def test_information_actions_and_native_horizontal_movement_are_preserved(self):
        bingie = ET.parse(XML / "IncludesBingie.xml").getroot()
        actions = bingie.find("include[@name='ContainerShowInfoOnclick']").findall("onclick")
        self.assertTrue(any(n.text == "Action(info)" for n in actions))
        widgets = ET.parse(XML / "IncludesHomeWidgets.xml").getroot()
        container = widgets.find("include[@name='widget_base_normal']/control")
        self.assertEqual(container.findtext("movement"), "7")
        self.assertEqual(container.findtext("orientation"), "$PARAM[position]")


if __name__ == "__main__":
    unittest.main()
