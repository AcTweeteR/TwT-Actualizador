"""Generated multi-profile includes must be checked against one profile store."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'addons/service.actweeter/resources/lib'))
import interface_layout as layout


class LayoutProfileScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.generated = self.root / 'includes.xml'
        self.properties = self.root / 'skin.actweeter.properties'
        self.documents = layout.source_documents(ROOT / 'addons/skin.actweeter')
        self.default_id = next(iter(layout.expandable_shortcut_ids(self.documents)))
        tree = ET.Element('includes')
        for group, count in (('Widgets', 7), ('moviehub', 10), ('tvshowhub', 10)):
            entry = ET.SubElement(tree, 'include', name='skinshortcuts-template-' + group)
            for profile in ('Active', 'Other'):
                name = group + '-' + profile
                ET.SubElement(entry, 'include', condition=self.selector(profile)).text = name
                target = ET.SubElement(tree, 'include', name=name)
                for index in range(count):
                    widget = ET.SubElement(target, 'include', content='widget_base')
                    values = {'widgetPath': 'plugin://plugin.video.xstream-pro/?mode=premium&'
                              'view=recent&stype=movie&actweeter_expand=1&limit=20',
                              'widgetExpandable': 'true' if profile == 'Active' else ''}
                    if group == 'Widgets' and index in (2, 3, 4):
                        values['widgetName'] = ('Tendencias', 'Popular', 'Recomendaciones')[index - 2]
                    for key, value in values.items():
                        ET.SubElement(widget, 'param', name=key, value=value)
        for profile in ('Active', 'Other'):
            item = ET.SubElement(tree, 'item')
            ET.SubElement(item, 'visible').text = self.selector(profile) + ' + [Control.HasFocus(900)]'
            for key, value in (('defaultID', self.default_id),
                               ('group', 'inicio.1'), ('labelID', profile + '-widget')):
                ET.SubElement(item, 'property', name=key).text = value
        self.tree = tree
        self.generated.write_bytes(ET.tostring(tree))
        self.properties.write_text(json.dumps([
            ['inicio.1', 'Active-widget', 'widgetExpandable', 'true'],
            ['custom', 'user-widget', 'custom-property', 'preserve'],
        ], ensure_ascii=False, indent=4), encoding='utf-8')

    @staticmethod
    def selector(profile):
        return 'String.IsEqual(System.ProfileName,%s)' % profile

    def visible(self, expression):
        return expression == self.selector('Active')

    def test_foreign_rows_do_not_fail_current_profile_readiness(self):
        self.assertFalse(layout.generated_layout_ready(
            self.generated, self.root, self.documents)[0])
        ready, rows = layout.generated_layout_ready(
            self.generated, self.root, self.documents, condition_visible=self.visible)
        self.assertTrue(ready)
        self.assertEqual({group: len(values) for group, values in rows.items()},
                         {'Widgets': 7, 'moviehub': 10, 'tvshowhub': 10})

    def test_foreign_identity_does_not_conflict_or_enter_current_property_store(self):
        before = self.properties.read_bytes()
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            layout.generated_shortcut_identities(self.generated, {self.default_id})
        identities = layout.generated_shortcut_identities(
            self.generated, {self.default_id}, condition_visible=self.visible)
        self.assertEqual(identities, {self.default_id: ('inicio.1', 'Active-widget')})
        result = layout.persist_generated_expandable_properties(
            self.root, self.root / 'service', self.generated, self.documents,
            condition_visible=self.visible)
        self.assertFalse(result['changed'])
        self.assertEqual(self.properties.read_bytes(), before)

    def test_invalid_active_row_is_not_hidden_by_profile_filter(self):
        target = self.tree.find("include[@name='moviehub-Active']")
        target.find("include/param[@name='widgetExpandable']").set('value', '')
        self.generated.write_bytes(ET.tostring(self.tree))
        ready, _rows = layout.generated_layout_ready(
            self.generated, self.root, self.documents, condition_visible=self.visible)
        self.assertFalse(ready)

    def test_switching_profile_checks_that_profiles_output(self):
        ready, rows = layout.generated_layout_ready(
            self.generated, self.root, self.documents,
            condition_visible=lambda condition: condition == self.selector('Other'))
        self.assertFalse(ready)
        self.assertEqual(len(rows['Widgets']), 7)
        self.assertTrue(all(not row['expansion_ready'] for row in rows['Widgets']))


if __name__ == '__main__':
    unittest.main()
