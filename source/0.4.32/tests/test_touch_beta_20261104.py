"""Skin-only touch Beta: input isolation, UI navigation, package reproducibility."""
from __future__ import annotations
import hashlib
import importlib.util
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "source/0.4.32/addons/skin.actweeter"
STABLE = ROOT / "repo/skin.actweeter/skin.actweeter-1.2.40.zip"
BETA = ROOT / "docs/testing/repo/skin.actweeter/skin.actweeter-1.2.41~beta1.zip"
TOUCH = SOURCE / "1080i/IncludesTouchMode.xml"


class TouchBetaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "build_touch_skin_beta", ROOT / "tools/build_touch_skin_beta.py")
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def test_touch_ui_works_only_when_explicitly_enabled(self):
        root = ET.parse(TOUCH).getroot()
        toolbar = root.find("include[@name='AcTweeteRTouchToolbar']/control")
        self.assertIn("Skin.HasSetting(AcTweeteRTouchMode)",
                      toolbar.findtext("visible"))
        self.assertEqual(toolbar.find("visible").text.count("AcTweeteRTouchMode"), 1)
        side = root.find("include[@name='AcTweeteRInputModeSideMenu']/control")
        self.assertEqual(side.findtext("onclick"),
                         "Skin.ToggleSetting(AcTweeteRTouchMode)")
        self.assertEqual(side.findtext("visible"), "$EXP[IsMainMenuOpened]")
        settings = root.find("include[@name='AcTweeteRInputModeSettings']")
        modes = {node.findtext("onclick") for node in settings.findall("control")}
        self.assertIn("Skin.SetBool(AcTweeteRTouchMode)", modes)
        self.assertIn("Skin.Reset(AcTweeteRTouchMode)", modes)
        self.assertEqual(list(SOURCE.rglob("keymaps/*.xml")), [])

    def test_recovery_from_touch_to_remote_does_not_require_touch_toolbar(self):
        root = ET.parse(TOUCH).getroot()
        side = root.find("include[@name='AcTweeteRInputModeSideMenu']/control")
        self.assertNotIn("Skin.HasSetting(AcTweeteRTouchMode)",side.findtext("visible"))
        setting = root.find("include[@name='AcTweeteRInputModeSettings']")
        self.assertTrue(any(x.findtext("selected") == "!Skin.HasSetting(AcTweeteRTouchMode)"
                            for x in setting.findall("control")))
        self.assertIn('AcTweeteRInputModeSideMenu',
                      (SOURCE/'1080i/IncludesBingie.xml').read_text())

    def test_toolbar_uses_real_touch_targets_without_stealing_entire_view(self):
        toolbar = ET.parse(TOUCH).getroot().find(
            "include[@name='AcTweeteRTouchToolbar']/control")
        controls = toolbar.findall("control")
        self.assertEqual({x.get("id") for x in controls},
                         {str(i) for i in range(43871,43878)})
        self.assertEqual((toolbar.findtext("width"),toolbar.findtext("height")),
                         ("1920","1080"))
        for item in controls:
            self.assertGreaterEqual(int(item.findtext("width")),74)
            self.assertGreaterEqual(int(item.findtext("height")),74)
            self.assertIsNotNone(item.find("onclick"))
            self.assertEqual(item.get("type"), "button")

    def test_touch_actions_are_supported_kodi_native_controls(self):
        root = ET.parse(TOUCH).getroot()
        actions = [action.text for action in root.iter("onclick")]
        self.assertIn("SetFocus(900)",actions)
        self.assertIn("ActivateWindow(1109)",actions)
        self.assertIn("ActivateWindow(Home)",actions)
        # The refined touch-only scroller targets Kodi's real pagecontrol.
        self.assertIn("PageUp(317)",actions)
        self.assertIn("PageDown(317)",actions)
        self.assertIn("Control.Move(1508,-1)",actions)
        self.assertIn("Control.Move(1508,1)",actions)
        self.assertIn("Dialog.Close(movieinformation)",actions)
        self.assertFalse(any("System.Exec(" in action or "RunScript(plugin.video." in action
                             for action in actions))

    def test_no_external_addon_actions_are_modified_for_touch(self):
        touched = {name for name in self.module.OVERLAY}
        self.assertTrue(all(name.startswith(("1080i/", "language/")) for name in touched))
        self.assertFalse(any("pvr" in name.lower() or "trakt" in name.lower()
                             or "rivulet" in name.lower() for name in touched))
        settings = (SOURCE/'1080i/IncludesSkinSettings.xml').read_text()
        self.assertIn('<include>AcTweeteRInputModeSettings</include>',settings)
        self.assertIn('Skin.HasSetting(AcTweeteRTouchMode)',
                      (SOURCE/'1080i/IncludesHomeWidgets.xml').read_text())

    def test_info_button_and_existing_remote_navigation_are_isolated(self):
        root = ET.parse(TOUCH).getroot()
        close = root.find("include[@name='AcTweeteRTouchInfoClose']/control")
        self.assertEqual(close.findtext("visible"),
                         "Skin.HasSetting(AcTweeteRTouchMode)")
        self.assertIn('<include>AcTweeteRTouchInfoClose</include>',
                      (SOURCE/'1080i/DialogVideoInfo.xml').read_text())
        home = (SOURCE/'1080i/IncludesHomeBingie.xml').read_text()
        self.assertIn("<onleft condition=\"$EXP[IsBingieViewsActive]\"",
                      home)
        self.assertIn("<include>AcTweeteRTouchToolbar</include>",home)

    def test_all_included_skin_xml_is_well_formed(self):
        count=0
        for path in (SOURCE/"1080i").glob("*.xml"):
            ET.parse(path)
            count+=1
        self.assertGreater(count,150)
        includes=ET.parse(SOURCE/"1080i/Includes.xml")
        self.assertEqual(len(includes.findall("include[@file='IncludesTouchMode.xml']")),1)

    def test_all_strings_exist_in_supported_locales_without_duplicates(self):
        for locale in ("es_es","en_gb"):
            content=(SOURCE/f"language/resource.language.{locale}/strings.po").read_text()
            for key in range(32019,32026):
                self.assertEqual(content.count(f'msgctxt "#{key}"'),1,
                                 (locale,key))

    def test_beta_archive_changes_only_skin_contents(self):
        with zipfile.ZipFile(STABLE) as old,zipfile.ZipFile(BETA) as new:
            before={name:old.read(name) for name in old.namelist()
                    if not name.endswith("/")}
            after={name:new.read(name) for name in new.namelist()
                   if not name.endswith("/")}
            changes={name for name in after if before.get(name)!=after[name]}
            expected={f"skin.actweeter/{relative}" for relative in self.module.OVERLAY}
            expected|={"skin.actweeter/addon.xml",
                       "skin.actweeter/changelog-1.2.41~beta1.txt"}
            self.assertEqual(changes,expected)
            self.assertEqual(set(before)-set(after),set())
            self.assertEqual(ET.fromstring(new.read("skin.actweeter/addon.xml")).get("version"),
                             "1.2.41~beta1")
            self.assertIsNone(new.testzip())

    def test_beta_reproducible_and_stable_baseline_unchanged(self):
        self.assertEqual(hashlib.sha256(STABLE.read_bytes()).hexdigest(),
                         self.module.BASE_DIGEST)
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/BETA.name
            result=self.module.build(output)
            self.assertEqual(output.read_bytes(),BETA.read_bytes())
            self.assertEqual(result["version"],self.module.BETA)
            with self.assertRaises(FileExistsError):
                self.module.build(output)

    def test_testing_feed_only_skin_version_advanced(self):
        feed=ET.parse(ROOT/"docs/testing/repo/addons.xml").getroot()
        versions={x.get("id"):x.get("version") for x in feed}
        # The live Testing feed advances independently of the immutable
        # 2026-11-04 Beta1 archive, which remains reproducible above.
        self.assertEqual(versions["skin.actweeter"],"1.2.43~beta2")
        self.assertEqual(versions["service.actweeter"],"0.4.103~beta1")
        self.assertEqual(versions["plugin.video.xstream-pro"],"1.1.2.44~beta8")
        self.assertEqual(versions["repository.rivulet"],"1.0.2")
        self.assertEqual(versions["repository.zachmorris"],"1.0.4")
        stable={x.get("id"):x.get("version") for x in
                ET.parse(ROOT/"repo/addons.xml").getroot()}
        self.assertEqual(stable["skin.actweeter"],"1.2.42")
        self.assertEqual(stable["service.actweeter"],"0.4.102")
        self.assertEqual(stable["plugin.video.xstream-pro"],"1.1.2.45")
        for addon_id in ("service.actweeter","plugin.video.xstream-pro",
                         "repository.rivulet","repository.zachmorris"):
            a=ROOT/f"docs/testing/repo/{addon_id}/{addon_id}-{versions[addon_id]}.zip"
            self.assertTrue(a.is_file())
            self.assertIsNone(zipfile.ZipFile(a).testzip())

if __name__=="__main__":
    unittest.main()
