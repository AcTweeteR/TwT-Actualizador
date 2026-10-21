"""Skin/template contracts; these do not claim real focus or touch validation."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SKIN = ROOT / 'addons/skin.actweeter'
sys.path.insert(0, str(ROOT / 'addons/service.actweeter/resources/lib'))
import interface_layout as layout


class CollectionsWidgetTests(unittest.TestCase):
    def test_terminal_widget_only_in_movie_and_series_hubs(self):
        root = ET.parse(SKIN / 'shortcuts/template.xml').getroot()
        widgets = root.findall(".//include[@content='AcTweeteRCollectionsWidget']")
        self.assertEqual(len(widgets), 2)
        for group, kind, identity in (('moviehub', 'movie', '6091'), ('tvshowhub', 'series', '6092')):
            submenu = root.find("./submenu[@include='%s']" % group)
            controls = list(submenu.find('controls'))
            self.assertEqual(controls[-1].get('content'), 'AcTweeteRCollectionsWidget')
            params = {node.get('name'): node.get('value') for node in controls[-1].findall('param')}
            self.assertIn('view=collections_root&stype=' + kind, params['widgetPath'])
            self.assertEqual(params['widgetid'], identity)
            # Suppress a legacy generated collection row without deleting user DATA.
            for node in submenu.findall("./items/controls/include"):
                self.assertIn("'view=collections_root' not in widgetPath", node.get('condition', ''))

    def test_defaults_have_no_standalone_collection_shortcuts(self):
        for path in (SKIN / 'shortcuts').glob('*.DATA.xml'):
            for node in ET.parse(path).getroot().findall('shortcut'):
                route = node.findtext('action', '')
                self.assertFalse(any('view=' + view in route for view in
                                     ('favorites', 'pending', 'collections_root')), path.name)

    def test_folder_widget_is_not_an_expansion_card_and_uses_native_return(self):
        root = ET.parse(SKIN / '1080i/IncludesHomeWidgets.xml').getroot()
        node = root.find("./include[@name='AcTweeteRCollectionsWidget']")
        params = {item.get('name'): item.get('value') for item in
                  node.findall("./definition/include[@content='widget_base']/param")}
        self.assertEqual(params['widgetName'], 'Mis Colecciones')
        self.assertEqual(params['widgetExpandable'], 'false')
        self.assertEqual(params['widgetTarget'], 'videos')
        self.assertEqual(params['container'], 'list')
        self.assertIn('Premium.CollectionsRefresh', (SKIN / 'shortcuts/template.xml').read_text())
        root = ET.parse(SKIN / '1080i/IncludesBingie.xml').getroot()
        actions = [n.text for n in root.iter('onclick')
                   if 'AcTweeteR.CollectionFolder' in n.get('condition', '')]
        self.assertEqual(actions, ['ActivateWindow(Videos,$INFO[Container($PARAM[widgetid]).ListItem.FileNameAndPath],return)'])

    def test_migration_from_v13_is_backed_up_and_idempotent(self):
        repo = ROOT.parents[1]
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            old_skin = base / 'old_skin'
            old_skin.mkdir()
            with zipfile.ZipFile(repo / 'repo/skin.actweeter/skin.actweeter-1.2.31.zip') as archive:
                for group in layout.GROUPS:
                    path = old_skin / 'shortcuts' / (group + '.DATA.xml')
                    path.parent.mkdir(exist_ok=True)
                    path.write_bytes(archive.read('skin.actweeter/shortcuts/' + group + '.DATA.xml'))
            with zipfile.ZipFile(repo / 'repo/service.actweeter/service.actweeter-0.4.52.zip') as archive:
                old = {}
                exec(compile(archive.read('service.actweeter/resources/lib/interface_layout.py'), 'legacy_layout.py', 'exec'), old)
            original = old['source_documents'](old_skin)
            shortcuts, service = base / 'shortcuts', base / 'service'
            shortcuts.mkdir(); service.mkdir()
            for name, data in original.items():
                (shortcuts / name).write_bytes(data)
            (service / 'interface_layout_state.json').write_text(json.dumps({
                'layout_version': 13, 'files': {name: hashlib.sha256(data).hexdigest()
                    for name, data in original.items()}, 'settings': layout.SETTINGS}))
            result = layout.apply_layout(shortcuts, service, SKIN, layout.SETTINGS)
            self.assertEqual(result['status'], 'APPLIED')
            backup = service / 'interface_backups' / result['backup']
            for name in result['changed']:
                self.assertEqual((backup / name).read_bytes(), original[name])
            self.assertEqual(layout.apply_layout(shortcuts, service, SKIN, layout.SETTINGS)['status'], 'CURRENT')
            custom = shortcuts / 'skin.actweeter-moviehub.DATA.xml'
            custom.write_bytes(custom.read_bytes().replace(b'Populares', b'Mis personalizados'))
            before = custom.read_bytes()
            conflict = layout.apply_layout(shortcuts, service, SKIN, layout.SETTINGS)
            self.assertEqual(conflict['status'], 'CONSENT_REQUIRED')
            self.assertEqual(custom.read_bytes(), before)
