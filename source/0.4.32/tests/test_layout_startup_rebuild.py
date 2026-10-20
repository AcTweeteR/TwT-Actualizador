"""Isolated Kodi-adapter tests; these are not device/runtime acceptance."""
import json
from contextlib import ExitStack
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'addons/service.actweeter/resources/lib'))
import interface_layout as layout


class LayoutStartupRebuildTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.profile = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.state_path = self.profile / 'interface_layout_state.json'
        self.state = {
            'layout_version': layout.LAYOUT_VERSION, 'build_status': 'GENERATED',
            'migration_history': [{'id': layout.LAYOUT_MIGRATION_ID,
                                   'status': 'VERIFIED'}],
        }
        self.save_state()
        self.window = mock.Mock()
        self.window.getProperty.return_value = ''
        self.kodi = mock.Mock()
        self.kodi.getSkinDir.return_value = 'skin.actweeter'
        self.kodi.getCondVisibility.return_value = False
        self.kodi.getInfoLabel.side_effect = lambda label: next(
            (value for key, value in layout.SETTINGS.items()
             if label == 'Skin.String(%s)' % key), '')
        self.gui = SimpleNamespace(Window=lambda _id: self.window)
        self.vfs = SimpleNamespace(translatePath=lambda path: path)
        self.versions = {'script.skinshortcuts': '2.0.3',
                         'service.actweeter': '0.4.40',
                         'skin.actweeter': '1.2.29~beta11'}
        self.apply = self.patch('apply_layout', return_value={
            'status': 'CURRENT', 'settings': {}})
        self.patch('prepare_metadata_language', return_value={})
        self.ready = self.patch('generated_layout_ready', return_value=(True, {}))
        rows = {name: [{'provider_only': True, 'expansion_ready': True}] * count
                for name, count in (('Widgets', 6), ('moviehub', 10), ('tvshowhub', 10))}
        self.ready.return_value = (True, rows)
        self.patch('generated_rows', return_value=rows)
        self.patch('persist_generated_expandable_properties', return_value={
            'changed': False, 'rows': 26})
        self.patch('generated_shortcut_identities', return_value={})
        self.patch('verify_expandable_property_store', return_value=True)
        self.build = self.patch('request_skinshortcuts_build', return_value='BUILD_FINISHED')

    def patch(self, name, **kwargs):
        return self.stack.enter_context(mock.patch.object(layout, name, **kwargs))

    def save_state(self):
        self.state_path.write_text(json.dumps(self.state), encoding='utf-8')

    def addon(self, addon_id):
        values = {'profile': str(self.profile),
                  'path': str(ROOT / 'addons' / addon_id),
                  'version': self.versions.get(addon_id, '')}
        return SimpleNamespace(getAddonInfo=lambda key: values.get(key, ''))

    def prepare(self):
        return layout.prepare_interface(self.kodi, self.addon, self.vfs, self.gui,
                                        mock.Mock())

    def test_five_verified_startups_do_not_request_a_native_build(self):
        for _ in range(5):
            self.assertEqual(self.prepare(), 'GENERATED')
        self.build.assert_not_called()
        self.kodi.executebuiltin.assert_not_called()

    def test_first_pending_startup_builds_once_then_reuses_persisted_success(self):
        self.state['build_status'] = 'PENDING'
        self.state['migration_history'][0]['status'] = 'APPLIED_PENDING_BUILD'
        self.save_state()
        self.assertEqual(self.prepare(), 'GENERATED')
        self.assertFalse(layout.interface_migration_due(layout.load_state(self.state_path)))
        for _ in range(5):
            self.assertEqual(self.prepare(), 'GENERATED')
        self.assertEqual(self.build.call_count, 1)

    def test_legitimate_applied_change_requests_one_build(self):
        self.apply.side_effect = [{'status': 'APPLIED', 'settings': {}},
                                  {'status': 'CURRENT', 'settings': {}}]
        self.assertEqual(self.prepare(), 'GENERATED')
        self.assertEqual(self.prepare(), 'GENERATED')
        self.assertEqual(self.build.call_count, 1)

    def test_interruption_does_not_mark_pending_layout_verified(self):
        self.state['build_status'] = 'PENDING'
        self.state['migration_history'][0]['status'] = 'APPLIED_PENDING_BUILD'
        self.save_state()
        self.build.return_value = 'ABORTED'
        self.assertEqual(self.prepare(), 'ABORTED')
        self.assertTrue(layout.interface_migration_due(layout.load_state(self.state_path)))
        self.assertFalse((self.profile / 'interface-prepare.lock').exists())
        self.build.return_value = 'BUILD_FINISHED'
        self.assertEqual(self.prepare(), 'GENERATED')
        self.assertFalse(layout.interface_migration_due(layout.load_state(self.state_path)))

    def test_concurrent_prepare_is_not_queued_behind_the_owner(self):
        original = layout._prepare_interface
        nested_results = []

        def while_owned(*args, **kwargs):
            nested_results.append(self.prepare())
            return original(*args, **kwargs)

        with mock.patch.object(layout, '_prepare_interface', side_effect=while_owned):
            self.assertEqual(self.prepare(), 'GENERATED')
        self.assertEqual(nested_results, ['PREPARATION_BUSY'])
        self.build.assert_not_called()

    def test_customized_menu_is_preserved_without_a_build(self):
        self.apply.return_value = {'status': 'CONSENT_REQUIRED'}
        self.assertEqual(self.prepare(), 'CUSTOMIZATIONS_PRESERVED')
        self.build.assert_not_called()
        self.kodi.executebuiltin.assert_not_called()

    def test_service_update_does_not_force_a_build_when_layout_is_current(self):
        self.versions['service.actweeter'] = '0.4.44'
        self.assertEqual(self.prepare(), 'GENERATED')
        self.build.assert_not_called()

    def test_replaced_skin_output_is_rebuilt_once(self):
        self.versions['skin.actweeter'] = '1.2.29~beta12'
        valid = self.ready.return_value
        self.ready.side_effect = [(False, {}), valid, valid]
        self.assertEqual(self.prepare(), 'GENERATED')
        self.assertEqual(self.prepare(), 'GENERATED')
        self.assertEqual(self.build.call_count, 1)


if __name__ == '__main__':
    unittest.main()
