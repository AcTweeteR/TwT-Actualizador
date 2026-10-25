"""Static safety contracts for the two Kodi information-dialog trailer controls.

These assertions do not establish touch hit-testing or playback success.
"""
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET


XML = Path(__file__).resolve().parents[1] / "addons/skin.actweeter/1080i"


class TrailerTouchContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.info = ET.parse(XML / "IncludesDialogVideoInfo.xml").getroot()

    def _trailer(self, layout):
        root = self.info.find(f"include[@name='{layout}']")
        self.assertIsNotNone(root, layout)
        controls = [node for node in root.iter("control")
                    if node.get("id") == "54"]
        self.assertEqual(len(controls), 1, f"{layout}: expected one trailer control")
        return controls[0]

    def test_both_layouts_have_opt_in_action_diagnostics(self):
        for layout in ("BingieInfo", "BingieAltInfo"):
            with self.subTest(layout=layout):
                button = self._trailer(layout)
                snapshot = next((node for node in button.findall("include")
                                 if node.get("content") == "AcTweeteR_Touch_ActionSnapshot"), None)
                self.assertIsNotNone(snapshot)
                params = {node.get("name"): node.get("value")
                          for node in snapshot.findall("param")}
                self.assertEqual(params, {"sourceid": "54", "action": "trailer"})

    def test_both_layouts_keep_a_single_shared_primary_trailer_action(self):
        for layout in ("BingieInfo", "BingieAltInfo"):
            with self.subTest(layout=layout):
                button = self._trailer(layout)
                actions = [node for node in button.findall("include")
                           if node.text == "AcTweeteR_Primary_Trailer_Action"]
                self.assertEqual(len(actions), 1)

    def test_both_layouts_have_actual_click_actions(self):
        for layout in ("BingieInfo", "BingieAltInfo"):
            with self.subTest(layout=layout):
                button = self._trailer(layout)
                self.assertGreater(len(button.findall("onclick")), 0)
                self.assertEqual(button.get("type"), "radiobutton")

    def test_layout_selection_is_exclusive(self):
        dialog = ET.parse(XML / "DialogVideoInfo.xml").getroot()
        includes = {node.text: node.get("condition") for node in dialog.iter("include")}
        self.assertEqual(includes["BingieInfo"],
                         "Skin.HasSetting(UseBingieInfoDialog)")
        self.assertEqual(includes["BingieAltInfo"],
                         "!Skin.HasSetting(UseBingieInfoDialog)")

    def test_playback_visibility_is_dynamic_for_both_layouts(self):
        dialog = ET.parse(XML / "DialogVideoInfo.xml").getroot()
        groups = dialog.findall("controls/control[@type='group']")
        group = next(node for node in groups
                     if any(child.text == "BingieInfo" for child in node.findall("include")))
        self.assertEqual({node.text for node in group.findall("include")},
                         {"BingieInfo", "BingieAltInfo"})
        self.assertEqual(group.findtext("visible"),
                         "!Player.HasVideo | String.IsEmpty(Window(Home).Property(SLYGUY_TRAILER_RETURN_PENDING))")
        # A wrapper must not translate, resize, or intercept the existing controls.
        self.assertEqual(set(node.tag for node in group), {"visible", "include"})
        self.assertEqual(group.attrib, {"type": "group"})


if __name__ == "__main__":
    unittest.main()
