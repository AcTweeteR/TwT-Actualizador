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
        container = widgets.find("include[@name='widget_base_normal']/definition/control")
        self.assertEqual(container.findtext("movement"), "7")
        self.assertEqual(container.findtext("orientation"), "$PARAM[position]")

    def test_home_vertical_scroll_uses_bounded_native_viewport_without_row_translation(self):
        home = ET.parse(XML / "IncludesHomeBingie.xml").getroot()
        viewport = home.find("include[@name='HomeVerticalScrollViewport']")
        self.assertEqual((viewport.findtext("top"), viewport.findtext("bottom")),
                         ("0", "0"))

        window = home.find("include[@name='HomeBingie']")
        group = window.find(".//control[@type='grouplist'][@id='77777']")
        self.assertEqual(group.findtext("top"), "564")
        self.assertEqual(group.findtext("bottom"), "0")
        self.assertTrue(any(node.text == "HomeVerticalScrollViewport"
                            and node.get("condition") == "Window.IsActive(Home)"
                            for node in group.findall("include")))
        bottom_overrides = [node for node in group.findall("include")
                            if node.text == "Fixed_Focus_Bottom"]
        self.assertEqual(len(bottom_overrides), 1)
        self.assertEqual(bottom_overrides[0].get("condition"),
                         "$EXP[IsBingieHubsActive]")

        children = list(group)
        spacer = group.find("control[@type='image'][@id='77776']")
        spotlight = group.find("include[@content='BingieSpotlightWidget']")
        self.assertIsNotNone(spacer)
        self.assertEqual(spacer.findtext("visible"), "Window.IsActive(Home)")
        self.assertEqual((spacer.findtext("top"), spacer.findtext("height"),
                          spacer.findtext("texture")),
                         ("0", "564", "colors/color_transparent.png"))
        self.assertLess(children.index(spacer), children.index(spotlight))

        scrollbar = window.find(".//control[@type='scrollbar'][@id='317']")
        self.assertTrue(any(node.text == "HomeVerticalScrollViewport"
                            and node.get("condition") == "Window.IsActive(Home)"
                            for node in scrollbar.findall("include")))

        bingie = ET.parse(XML / "IncludesBingie.xml").getroot()
        factory = bingie.find("include[@name='Fixed_Focus_Navigation_Factory']")
        hub_animations = factory.findall("include[@content='Fixed_Focus_Navigation']")
        self.assertEqual(len(hub_animations), 3)
        self.assertTrue(all("!Window.IsActive(Home)" in node.get("condition", "")
                            for node in hub_animations))
        home_animations = factory.find(
            "include[@content='Fixed_Focus_Navigation_Home']")
        self.assertEqual(home_animations.get("condition"), "Window.IsActive(Home)")
        home_fades = bingie.find("include[@name='Fixed_Focus_Navigation_Home']")
        self.assertEqual(len(home_fades.findall("animation")), 3)
        self.assertTrue(all(node.get("effect") == "fade"
                            for node in home_fades.findall("animation")))

    def test_expansion_literal_selects_21_without_infolabel_lookup(self):
        root = ET.parse(XML / "IncludesHomeWidgets.xml").getroot()
        base = root.find("include[@name='widget_base_normal']")
        self.assertEqual(base.find("param[@name='widgetExpandable']").get("default"), "false")
        container = base.find("definition/control")
        branches = [n for n in container.findall("include")
                    if n.get("content", "").startswith("widget_base_content_")]
        self.assertEqual([(n.get("content"), n.get("condition")) for n in branches], [
            ("widget_base_content_expandable", "$PARAM[widgetExpandable]"),
            ("widget_base_content_$PARAM[contentStyle]", "!$PARAM[widgetExpandable]")])
        self.assertEqual(root.find("include[@name='widget_base_content_expandable']/content").get("limit"), "21")
        self.assertEqual(root.find("include[@name='widget_base_content_normal']/content").get("limit"), "20")
        template = ET.parse(XML.parent / "shortcuts/template.xml").getroot()
        flags = list(template.iterfind(".//param[@name='widgetExpandable']"))
        self.assertEqual(len(flags), 3)
        for flag in flags:
            self.assertEqual(flag.get("value"), "$SKINSHORTCUTS[widgetExpandable]")
        for group in template:
            declarations = group.findall("property[@name='widgetExpandable']")
            if declarations:
                self.assertEqual(len(declarations), 2)
                self.assertEqual(declarations[0].get("tag"), "property")
                self.assertIsNone(declarations[1].get("tag"))
                self.assertEqual(declarations[1].text, "false")


if __name__ == "__main__":
    unittest.main()
