"""Kodi touch Beta3: audit exact action parity, modal state and selectable focus."""
from __future__ import annotations
import hashlib
import importlib.util
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
UI = ROOT / "source/0.4.32/addons/skin.actweeter/1080i"
ORIGINAL = ET.parse(UI / "IncludesDialogVideoInfo.xml").getroot()
TOUCH = ET.parse(UI / "IncludesTouchInfoActions.xml").getroot()
NAV = ET.parse(UI / "IncludesTouchVideoNavigation.xml").getroot()
BETA2 = ROOT / "docs/testing/repo/skin.actweeter/skin.actweeter-1.2.41~beta2.zip"
BETA3 = ROOT / "docs/testing/repo/skin.actweeter/skin.actweeter-1.2.41~beta3.zip"
TARGETS = (
    80, 90, 51, 8181, 52, 53, 54, 541, 56, 57, 561, 562,
    60, 64, 61, 63, 62, 611, 631, 622, 14, 10, 1040, 6, 612,
    7001, 7002, 7003, 7004, 7011, 7033, 7055,
)
MODES = {
    "BingieInfo": "Skin.HasSetting(UseBingieInfoDialog)",
    "BingieAltInfo": "!Skin.HasSetting(UseBingieInfoDialog)",
}


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    item = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(item)
    return item


class TouchNativeActionsBeta3(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder = module("build_touch_native_beta3", "tools/build_touch_native_beta3.py")
        cls.wiring = module("wire_touch_info_actions", "tools/wire_touch_info_actions.py")

    def test_direct_actions_no_modal_sendclick_forwarding(self):
        clicks = [(n.text or "") for n in TOUCH.iter("onclick")]
        self.assertFalse(any("SendClick(" in x for x in clicks))
        self.assertGreaterEqual(len(clicks), 350)
        self.assertGreaterEqual(sum("RunScript(" in x for x in clicks), 30)
        self.assertIn("Dialog.Close(movieinformation)", clicks)

    def test_every_native_script_for_both_info_layouts_has_a_touch_equivalent(self):
        self.assertEqual(len(TARGETS), 32)
        for i, target in enumerate(TARGETS):
            mirror = TOUCH.find(f'.//control[@id="{44100+i}"]')
            self.assertIsNotNone(mirror)
            self.assertEqual(mirror.findtext("visible"), f"Control.IsVisible({target})")
            pairs = {((n.text or "").strip(), n.get("condition", ""))
                     for n in mirror.findall("onclick")}
            for layout, gate in MODES.items():
                original = next(
                    (c for c in ORIGINAL.find(f'include[@name="{layout}"]').iter("control")
                     if c.get("id") == str(target)), None)
                if original is None:
                    continue
                native_actions = original.findall("onclick")
                if not native_actions:
                    for action in (f"SetFocus({target})", "Action(Select)"):
                        self.assertIn((action, gate), pairs, (layout,target,action))
                for action in native_actions:
                    cond = gate
                    if action.get("condition"):
                        cond += f' + [{action.get("condition").strip()}]'
                    self.assertIn(((action.text or "").strip(), cond), pairs,
                                  (layout,target,(action.text or "")[:80]))
        self.assertEqual(hashlib.sha256((UI/"IncludesDialogVideoInfo.xml").read_bytes()).hexdigest(),
                         self.wiring.NATIVE_SOURCE_SHA)

    def test_primary_actions_are_direct_and_available(self):
        for target,button_id in zip((80,90,51,8181,53,54),range(44001,44007)):
            c = TOUCH.find(f'.//control[@id="{button_id}"]')
            self.assertEqual(c.findtext("visible"), f"Control.IsVisible({target})")
            self.assertGreaterEqual(len(c.findall("onclick")), 2)
        drawer = TOUCH.find('.//control[@id="44007"]')
        self.assertEqual(drawer.findtext("onclick"),
                         "SetProperty(AcTweeteRTouchInfoActions,1,Home)")
        close = TOUCH.find('.//control[@id="44008"]')
        self.assertEqual(close.findtext("onclick"),"Dialog.Close(movieinformation)")

    def test_drawer_property_stays_on_home_across_modal_windows(self):
        dialog=ET.parse(UI/"DialogVideoInfo.xml").getroot()
        clears=[x.text for x in dialog if x.tag in ("onload","onunload")]
        self.assertEqual(clears.count("ClearProperty(AcTweeteRTouchInfoActions,Home)"),2)
        drawer=TOUCH.find('.//control[@id="44190"]')
        self.assertEqual(drawer.findtext("visible"),
            "!String.IsEmpty(Window(Home).Property(AcTweeteRTouchInfoActions))")
        self.assertEqual(TOUCH.find('.//control[@id="44191"]').findtext("onclick"),
                         "ClearProperty(AcTweeteRTouchInfoActions,Home)")
        for id_ in range(44100,44132):
            control=TOUCH.find(f'.//control[@id="{id_}"]')
            self.assertEqual(control.find("onclick").text,
                             "ClearProperty(AcTweeteRTouchInfoActions,Home)")

    def test_native_media_view_focus_not_nonselectable_parent(self):
        focus = NAV.find('include[@name="AcTweeteRTouchFocusSelectedMedia"]')
        items = focus.findall("onclick")
        self.assertEqual(len(items),24)
        self.assertEqual(set(x.text for x in items),
                         {f"SetFocus({v})" for v in (
                             50,51,52,501,502,503,53,54,55,56,57,507,
                             509,510,511,512,513,514,523,524,525,526,527,528)})
        self.assertFalse(any(x.text=="SetFocus(5000)" for x in NAV.iter("onclick")))
        for id_,action in ((44202,"Action(Info)"),(44203,"Action(ContextMenu)")):
            button=NAV.find(f'.//control[@id="{id_}"]')
            self.assertEqual(button.find("include").text, "AcTweeteRTouchFocusSelectedMedia")
            self.assertEqual(button.findtext("onclick"),action)

    def test_remote_native_actions_and_unrelated_components_unchanged(self):
        with zipfile.ZipFile(BETA2) as before,zipfile.ZipFile(BETA3) as after:
            original={k:before.read(k) for k in before.namelist() if not k.endswith("/")}
            current={k:after.read(k) for k in after.namelist() if not k.endswith("/")}
            changed={k for k,v in current.items() if original.get(k)!=v}
            expected={f"skin.actweeter/{k}" for k in self.builder.OVERLAY}
            expected|={"skin.actweeter/addon.xml","skin.actweeter/changelog-1.2.41~beta3.txt"}
            self.assertEqual(changed,expected)
            self.assertEqual(set(original)-set(current),set())
            self.assertEqual(current["skin.actweeter/1080i/IncludesDialogVideoInfo.xml"],
                             original["skin.actweeter/1080i/IncludesDialogVideoInfo.xml"])
            self.assertIsNone(after.testzip())
            self.assertEqual(ET.fromstring(after.read("skin.actweeter/addon.xml")).get("version"),
                             self.builder.BETA_VERSION)

    def test_reproducible_create_only_package(self):
        self.assertEqual(hashlib.sha256(BETA2.read_bytes()).hexdigest(),
                         self.builder.BASE_SHA256)
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/BETA3.name
            self.assertEqual(self.builder.build(output)["version"],self.builder.BETA_VERSION)
            self.assertEqual(output.read_bytes(),BETA3.read_bytes())
            with self.assertRaises(FileExistsError):
                self.builder.build(output)

    def test_skin_valid_and_channel_isolated(self):
        all_xml=list(UI.glob("*.xml"))
        self.assertGreater(len(all_xml),170)
        for path in all_xml: ET.parse(path)
        versions={e.get("id"):e.get("version") for e in
                  ET.parse(ROOT/"docs/testing/repo/addons.xml").getroot()}
        self.assertEqual(versions["skin.actweeter"],"1.2.41~beta4")
        self.assertEqual(versions["service.actweeter"],"0.4.101~beta1")
        self.assertEqual(versions["plugin.video.xstream-pro"],"1.1.2.44~beta4")
        stable={e.get("id"):e.get("version") for e in
                ET.parse(ROOT/"repo/addons.xml").getroot()}
        self.assertEqual(stable["skin.actweeter"],"1.2.41")
