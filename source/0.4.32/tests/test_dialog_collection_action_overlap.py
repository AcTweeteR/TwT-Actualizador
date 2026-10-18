"""Static contract preventing the expanded collection panel covering actions.

This protects the layout geometry; it is not a runtime touch test.
"""
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET


XML = (Path(__file__).resolve().parents[1] /
       "addons/skin.actweeter/1080i/IncludesDialogVideoInfo.xml")


class DialogCollectionActionOverlapTests(unittest.TestCase):
    def test_expanded_collection_moves_clear_of_action_column(self):
        root = ET.parse(XML).getroot()
        layout = root.find("include[@name='BingieInfo']")
        self.assertIsNotNone(layout)
        parents = {child: parent for parent in layout.iter() for child in parent}

        collection = next(node for node in layout.iter("control")
                          if node.get("id") == "353")
        collection_group = parents[collection]
        while collection_group is not layout:
            slide = next((animation for animation in collection_group.findall("animation")
                          if animation.get("effect") == "slide"
                          and animation.get("condition") == "Control.HasFocus(353)"), None)
            if slide is not None:
                break
            collection_group = parents[collection_group]
        else:
            self.fail("collection list has no focus-state slide animation")

        self.assertEqual(slide.get("start"), "0,0")
        self.assertEqual(slide.get("end"), "550,-312")
        self.assertEqual(slide.get("time"), "300")

        action_list = next(node for node in layout.iter("control")
                           if node.get("id") == "8000"
                           and node.findtext("orientation") == "vertical")
        self.assertEqual(action_list.findtext("width"), "550")
        self.assertEqual(action_list.findtext("height"), "320")


if __name__ == "__main__":
    unittest.main()
