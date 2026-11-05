"""AcTweeteR Beta2 touch accessibility and remote/published add-on isolation."""
from __future__ import annotations
import hashlib
import importlib.util
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
SRC=ROOT/"source/0.4.32/addons/skin.actweeter"
UI=SRC/"1080i"
OLD=ROOT/"docs/testing/repo/skin.actweeter/skin.actweeter-1.2.41~beta1.zip"
NEW=ROOT/"docs/testing/repo/skin.actweeter/skin.actweeter-1.2.41~beta2.zip"
NATIVE=ET.parse(UI/"IncludesDialogVideoInfo.xml").getroot()
INFO=ET.parse(UI/"IncludesTouchInfoActions.xml").getroot()
NAV=ET.parse(UI/"IncludesTouchVideoNavigation.xml").getroot()

def clone(xml_bytes):
    return ET.fromstring(xml_bytes)

class TouchRefinementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location("touch_refinement_builder",ROOT/"tools/build_touch_refinement_beta.py")
        cls.builder=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.builder)

    def test_original_info_action_ids_all_exist(self):
        native_ids={c.get("id") for name in ("BingieInfo","BingieAltInfo")
                    for c in NATIVE.find(f"./include[@name='{name}']").iter("control")}
        targets=(80,90,51,8181,52,53,54,541,56,57,561,562,60,64,61,
                 63,62,611,631,622,14,10,1040,6,612,7001,7002,
                 7003,7004,7011,7033,7055)
        self.assertEqual(len(targets),32)
        for number,target in enumerate(targets):
            button=INFO.find(f".//control[@id='{44100+number}']")
            self.assertIsNotNone(button)
            self.assertIn(str(target),native_ids)
            self.assertEqual(button.findtext("visible"),f"Control.IsVisible({target})")
            self.assertGreaterEqual(len(button.findall("onclick")),2)

    def test_info_forwarding_preserves_original_onclick(self):
        # Forwarded native controls are unchanged even when that source layout
        # has complex conditional multi-click handlers.
        with zipfile.ZipFile(OLD) as before,zipfile.ZipFile(NEW) as after:
            member="skin.actweeter/1080i/IncludesDialogVideoInfo.xml"
            self.assertEqual(after.read(member),before.read(member))
        info_clicks=[c.text for c in INFO.iter("onclick")]
        self.assertFalse(any(c and c.startswith("SendClick(") for c in info_clicks))
        self.assertGreaterEqual(sum(1 for c in info_clicks if c and "RunScript(" in c),30)

    def test_touch_gate_and_info_modes(self):
        parent=INFO.find("./include[@name='AcTweeteRTouchVideoInfoActions']/control")
        self.assertEqual(parent.findtext("visible"),"Skin.HasSetting(AcTweeteRTouchMode)")
        quick=parent.find("control[@id='44000']")
        self.assertEqual(quick.findtext("orientation"),"horizontal")
        for id_ in range(44001,44009):
            control=quick.find(f"control[@id='{id_}']")
            self.assertIsNotNone(control)
            self.assertGreaterEqual(int(control.findtext("width")),180)
            self.assertGreaterEqual(int(control.findtext("height")),74)
        drawer=parent.find("control[@id='44190']")
        self.assertIn("AcTweeteRTouchInfoActions",drawer.findtext("visible"))
        scroller=drawer.find("control[@id='44192']")
        self.assertEqual(scroller.findtext("pagecontrol"),"44193")
        self.assertEqual(len(scroller.findall("control[@type='button']")),32)
        self.assertEqual(drawer.find("control[@id='44194']").findtext("onclick"),"PageUp(44193)")
        self.assertEqual(drawer.find("control[@id='44195']").findtext("onclick"),"PageDown(44193)")

    def test_all_touch_actions_are_only_on_touch_visible_controls(self):
        for fname in ("IncludesTouchInfoActions.xml","IncludesTouchVideoNavigation.xml"):
            root=ET.parse(UI/fname).getroot()
            for include in root.findall("include"):
                if include.get("name") in ("AcTweeteRTouchVideoInfoActions","AcTweeteRTouchVideoNavigation"):
                    self.assertEqual(include.find("control").findtext("visible"),
                                     "Skin.HasSetting(AcTweeteRTouchMode)")
        original=(UI/"IncludesTouchMode.xml").read_text()
        self.assertIn("PageUp(317)",original)
        self.assertIn("PageDown(317)",original)

    def test_video_list_toolbar_can_reach_info_context_and_scroll(self):
        v=NAV.find("include[@name='AcTweeteRTouchVideoNavigation']")
        actions=[c.text for c in v.iter("onclick")]
        self.assertIn("Action(Info)",actions)
        self.assertIn("Action(ContextMenu)",actions)
        self.assertIn("PreviousMenu",actions)
        up=NAV.find("include[@name='AcTweeteRTouchVideoPageUp']")
        down=NAV.find("include[@name='AcTweeteRTouchVideoPageDown']")
        self.assertEqual(len(up.findall("onclick")),24)
        self.assertEqual(len(down.findall("onclick")),24)
        self.assertEqual([c.get("condition") for c in up.findall("onclick")],
                         [c.get("condition") for c in down.findall("onclick")])
        for tag in ("525","527","50"):
            self.assertIn(f"Control.Message({tag},pageup)",[c.text for c in up.findall("onclick")])
            self.assertIn(f"Control.Message({tag},pagedown)",[c.text for c in down.findall("onclick")])

    def test_touch_only_synopsis_close_and_scroll(self):
        viewer=ET.parse(UI/"DialogTextViewer.xml").getroot()
        grp=[g for g in viewer.iter("control")
             if g.get("type")=="group" and g.findtext("visible")=="Skin.HasSetting(AcTweeteRTouchMode)"]
        self.assertEqual(len(grp),1)
        actions=[c.text for c in grp[0].iter("onclick")]
        self.assertIn("PageUp(60)",actions)
        self.assertIn("PageDown(60)",actions)
        self.assertIn("PreviousMenu",actions)

    def test_remote_mode_original_controls_equal_published_beta(self):
        # For every modified window, strip ONLY newly added touch controls and
        # dialog-property lifecycle events; original remote controls remain identical.
        with zipfile.ZipFile(OLD) as archive:
            for name in ("DialogTextViewer.xml","MyVideoNav.xml","DialogVideoInfo.xml","Includes.xml"):
                member=f"skin.actweeter/1080i/{name}"
                before=clone(archive.read(member))
                after=ET.parse(UI/name).getroot()
                if name=="DialogTextViewer.xml":
                    container=after.find("controls")
                    for child in list(container):
                        if child.tag=="control" and child.findtext("visible")=="Skin.HasSetting(AcTweeteRTouchMode)":
                            container.remove(child)
                if name=="MyVideoNav.xml":
                    container=after.find("controls")
                    for child in list(container):
                        if child.tag=="include" and child.text=="AcTweeteRTouchVideoNavigation":
                            container.remove(child)
                if name=="DialogVideoInfo.xml":
                    for child in list(after):
                        if child.tag in ("onload","onunload") and child.text in ("ClearProperty(AcTweeteRTouchInfoActions)",
                                            "ClearProperty(AcTweeteRTouchInfoActions,Home)"):
                            after.remove(child)
                    container=after.find("controls")
                    for child in list(container):
                        if child.tag=="include" and child.text=="AcTweeteRTouchVideoInfoActions":
                            container.remove(child)
                if name=="Includes.xml":
                    for child in list(after):
                        if child.tag=="include" and child.get("file") in (
                            "IncludesTouchInfoActions.xml","IncludesTouchVideoNavigation.xml"):
                            after.remove(child)
                # Ignore blank whitespace left behind when removing touch-only
                # nodes, not any attribute, action, label or original element.
                self.assertEqual(
                    ET.canonicalize(ET.tostring(before), strip_text=True),
                    ET.canonicalize(ET.tostring(after), strip_text=True), name)

    def test_zip_and_historical_beta_immutable(self):
        self.assertEqual(hashlib.sha256(OLD.read_bytes()).hexdigest(),self.builder.EXPECTED_PARENT_SHA)
        with zipfile.ZipFile(OLD) as prev,zipfile.ZipFile(NEW) as cur:
            before={n:prev.read(n) for n in prev.namelist() if not n.endswith("/")}
            after={n:cur.read(n) for n in cur.namelist() if not n.endswith("/")}
            changed={n for n,data in after.items() if before.get(n)!=data}
            allowed={f"skin.actweeter/{name}" for name in self.builder.OVERLAY}
            allowed.update({"skin.actweeter/addon.xml","skin.actweeter/changelog-1.2.41~beta2.txt"})
            self.assertEqual(changed,allowed)
            self.assertEqual(set(before)-set(after),set())
            self.assertIsNone(cur.testzip())
            self.assertEqual(ET.fromstring(cur.read("skin.actweeter/addon.xml")).get("version"),"1.2.41~beta2")

    def test_reproducible_build_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            candidate=Path(td)/NEW.name
            output=self.builder.build(candidate)
            self.assertEqual(candidate.read_bytes(),NEW.read_bytes())
            self.assertEqual(output["version"],"1.2.41~beta2")
            with self.assertRaises(FileExistsError): self.builder.build(candidate)

    def test_all_skin_xml_and_translations_valid(self):
        files=list(UI.glob("*.xml"))
        for path in files:ET.parse(path)
        self.assertGreater(len(files),170)
        for locale in ("es_es","en_gb"):
            text=(SRC/f"language/resource.language.{locale}/strings.po").read_text()
            for key in [*range(32019,32037),*range(32100,32132)]:
                self.assertEqual(text.count(f'msgctxt "#{key}"'),1,(locale,key))

    def test_current_feed_only_skin_new_version(self):
        feed={e.get("id"):e.get("version") for e in
              ET.parse(ROOT/"docs/testing/repo/addons.xml").getroot()}
        self.assertEqual(feed["skin.actweeter"],"1.2.41~beta4")
        self.assertEqual(feed["service.actweeter"],"0.4.99~beta2")
        self.assertEqual(feed["plugin.video.xstream-pro"],"1.1.2.40~beta2")
        self.assertEqual(feed["repository.actweeter.testing"],"1.0.2")
