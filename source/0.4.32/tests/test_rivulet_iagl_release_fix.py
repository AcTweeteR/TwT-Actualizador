"""Regression coverage for Rivulet/IAGL installation in both release channels."""
import ast
import hashlib
import os
import sys
import unittest
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import Mock
ROOT = Path(__file__).resolve().parents[3]

class RivuletIaglReleaseFix(unittest.TestCase):
    def test_both_channels_expose_upstream_repository_bootstraps(self):
        for channel in ('repo', 'docs/testing/repo'):
            directory = ROOT/channel
            index_path = Path(os.environ.get('ACTWEETER_BETA_INDEX', directory/'addons.xml')) if channel != 'repo' else directory/'addons.xml'
            directory = index_path.parent
            index = index_path.read_bytes()
            self.assertEqual((directory/'addons.xml.md5').read_text().strip(),hashlib.md5(index).hexdigest())
            addons = {x.get('id'):x for x in ET.fromstring(index)}
            for aid,version in [('repository.rivulet','1.0.2'),('repository.zachmorris','1.0.4')]:
                self.assertEqual(addons[aid].get('version'),version)
                with zipfile.ZipFile(directory/aid/f'{aid}-{version}.zip') as z:
                    self.assertIsNone(z.testzip())
                    self.assertEqual(ET.fromstring(z.read(f'{aid}/addon.xml')).get('version'),version)
            self.assertEqual(addons['service.actweeter'].get('version'),
                             '0.4.94' if channel == 'repo' else '0.4.94~beta9')
    def test_native_installer_does_not_gate_on_unreliable_installable_query(self):
        source=(ROOT/'source/0.4.32/addons/service.actweeter/setup.py').read_text()
        tree=ast.parse(source)
        func=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='_request_native_addon_install')
        calls=[x for x in ast.walk(func) if isinstance(x,ast.Call) and isinstance(x.func,ast.Name)]
        self.assertNotIn('_wait_for_installable_addon',[x.func.id for x in calls])
        self.assertIn('UpdateAddonRepos',ast.get_source_segment(source,func))
    def test_new_repositories_trigger_refresh_before_dependents(self):
        source=(ROOT/'source/0.4.32/addons/service.actweeter/setup.py').read_text()
        func=next(x for x in ast.parse(source).body if isinstance(x,ast.FunctionDef) and x.name=='_install_components_once')
        text=ast.get_source_segment(source,func)
        self.assertIn('"repository.rivulet"',text)
        self.assertIn('"repository.zachmorris"',text)
        self.assertIn('UpdateAddonRepos',text)
if __name__=='__main__':unittest.main()
