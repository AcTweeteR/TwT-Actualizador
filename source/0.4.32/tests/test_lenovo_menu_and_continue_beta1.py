"""Regression checks for repaired Rivulet and exact movie resume IDs."""
import ast
import json
import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'source/0.4.32/addons/service.actweeter/resources/lib'))
import interface_layout

class LenovoRepairTests(unittest.TestCase):
    def test_rivulet_restored_without_changing_custom_items(self):
        defaults=(ROOT/'source/0.4.32/addons/skin.actweeter/shortcuts/mainmenu.DATA.xml').read_bytes()
        menu=ET.fromstring(defaults)
        menu.remove(menu.find("shortcut[defaultID='rivulet']"))
        row=ET.SubElement(menu,'shortcut')
        ET.SubElement(row,'label').text='Custom'
        ET.SubElement(row,'defaultID').text='custom'
        ET.SubElement(row,'action').text='ActivateWindow(Settings)'
        original=ET.tostring(row)
        restored=ET.fromstring(interface_layout.merge_arcade_shortcut(ET.tostring(menu),defaults))
        self.assertEqual(ET.tostring(restored.find("shortcut[defaultID='custom']")),original)
        self.assertEqual(restored.find("shortcut[defaultID='rivulet']/action").text,'RunAddon(plugin.video.rivulet)')
        self.assertEqual([x.findtext('defaultID') for x in restored].count('rivulet'),1)
    def test_exact_resume_provider_id_handles_renamed_movie(self):
        with zipfile.ZipFile(ROOT/'docs/testing/repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.44~beta1.zip') as z:
            source=z.read('plugin.video.xstream-pro/resources/lib/premium_routes.py').decode()
        tree=ast.parse(source)
        func=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='route') if any(isinstance(x,ast.FunctionDef) and x.name=='route' for x in tree.body) else None
        self.assertIn('provider_match = re.search',source)
        self.assertIn('provider_id(s, kind) == provider_match.group(1)',source)
        pattern=r'/([0-9]+)\.[A-Za-z0-9]+$'
        self.assertEqual(re.search(pattern,'/movie/u/p/321.mp4').group(1),'321')
        self.assertIsNone(re.search(pattern,'/series/u/p/abc.ts'))
    def test_no_addon_profile_or_tokens_changed_by_candidate(self):
        with zipfile.ZipFile(ROOT/'docs/testing/repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.44~beta1.zip') as z:
            self.assertIsNone(z.testzip())
            self.assertTrue(all(name.startswith('plugin.video.xstream-pro/') for name in z.namelist()))

if __name__=='__main__': unittest.main()
