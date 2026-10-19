"""Synthetic installer/bridge tests; no Kodi process or production profile."""
import ast
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'addons/service.actweeter/resources/lib'))
import slyguy_bridge_install as bridge


class PreviewSetupConsentTests(unittest.TestCase):
    def test_installer_offer_uses_existing_consent_gate_and_reports_failures(self):
        tree = ast.parse((ROOT / 'addons/service.actweeter/setup.py').read_text())
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == '_offer_automatic_previews')
        kodi, addon, vfs, dialog = Mock(), Mock(), Mock(), Mock()
        namespace = dict(xbmc=kodi, xbmcaddon=addon, xbmcvfs=vfs)
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'setup.py', 'exec'), namespace)
        for result in ('CURRENT', 'INSTALLED_NOT_RUNTIME_VERIFIED', 'DECLINED'):
            with patch.object(bridge, 'install', return_value=result) as install:
                self.assertEqual(namespace[node.name](dialog), result)
                install.assert_called_once_with(kodi, addon.Addon, vfs, dialog,
                                                allow_prompt=True)
                self.assertNotIn('consent', install.call_args.kwargs)
        dialog.ok.assert_not_called()
        with patch.object(bridge, 'install', side_effect=OSError('private path')):
            self.assertEqual(namespace[node.name](dialog), 'ERROR')
        self.assertNotIn('private path', str(kodi.log.call_args_list))
        dialog.ok.assert_called_once()

    def test_first_run_and_maintenance_reach_offer_without_layout_dependency(self):
        tree = ast.parse((ROOT / 'addons/service.actweeter/setup.py').read_text())
        functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        called = lambda name: [n.func.id for n in ast.walk(functions[name])
                               if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
        self.assertIn('_install_slyguy_stack', called('_run_onboarding'))
        self.assertIn('_install_slyguy_stack', called('_wizard'))
        self.assertIn('_offer_automatic_previews', called('_install_slyguy_stack'))
        layout = (ROOT / 'addons/service.actweeter/resources/lib/interface_layout.py').read_text()
        self.assertNotIn('install_preview_bridge', layout)

    def fixture(self, directory):
        base = Path(directory)
        state, source = base / 'private-state', base / 'slyguy'
        state.mkdir()
        originals = {'service.py': b'# synthetic service fixture\n',
                     'resources/lib/youtube.py': b"def play_yt_dlp(video_id):\n    path = 'special://temp/yt.mpd'\n    return path\n"}
        for name, data in originals.items():
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        def factory(name):
            values = ({'profile': str(state)} if name == 'service.actweeter'
                      else {'version': '0.2.1', 'path': str(source)})
            addon = Mock()
            addon.getAddonInfo.side_effect = values.__getitem__
            return addon
        kodi, vfs, dialog = Mock(), Mock(), Mock()
        kodi.getCondVisibility.return_value = False
        kodi.executeJSONRPC.return_value = '{"result":"OK"}'
        vfs.translatePath.side_effect = lambda value: value
        return state, source, originals, kodi, factory, vfs, dialog

    def test_no_consent_never_writes_or_restarts_slyguy(self):
        with tempfile.TemporaryDirectory() as directory:
            state, source, originals, kodi, factory, vfs, dialog = self.fixture(directory)
            self.assertEqual(bridge.install(kodi, factory, vfs, dialog), 'CONSENT_REQUIRED')
            dialog.yesno.return_value = False
            self.assertEqual(bridge.install(kodi, factory, vfs, dialog, allow_prompt=True), 'DECLINED')
            dialog.yesno.assert_called_once()
            kodi.executeJSONRPC.assert_not_called()
            self.assertEqual(list(state.iterdir()), [])
            for name, data in originals.items():
                self.assertEqual((source / name).read_bytes(), data)

    def test_consented_synthetic_install_is_backed_up_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            state, source, originals, kodi, factory, vfs, dialog = self.fixture(directory)
            hashes = {name: hashlib.sha256(data).hexdigest() for name, data in originals.items()}
            dialog.yesno.return_value = True
            with patch.dict(bridge.ORIGINAL_HASHES, hashes, clear=True):
                self.assertEqual(bridge.install(kodi, factory, vfs, dialog, allow_prompt=True),
                                 'INSTALLED_NOT_RUNTIME_VERIFIED')
                report = json.loads((state / 'slyguy_bridge_integration.json').read_text())
                for name, data in originals.items():
                    self.assertEqual((state / 'slyguy_bridge_backups' / report['backup'] / name).read_bytes(), data)
                before = {name: (source / name).read_bytes() for name in originals}
                kodi.executeJSONRPC.reset_mock()
                dialog.yesno.reset_mock()
                self.assertEqual(bridge.install(kodi, factory, vfs, dialog, allow_prompt=True), 'CURRENT')
                kodi.executeJSONRPC.assert_not_called()
                dialog.yesno.assert_not_called()
                self.assertEqual(before, {name: (source / name).read_bytes() for name in originals})

    def test_active_playback_is_never_interrupted_to_offer_bridge(self):
        kodi = Mock()
        kodi.getCondVisibility.return_value = True
        factory, dialog = Mock(), Mock()
        self.assertEqual(bridge.install(kodi, factory, Mock(), dialog, allow_prompt=True),
                         'PLAYER_ACTIVE')
        factory.assert_not_called()
        dialog.yesno.assert_not_called()
        kodi.executeJSONRPC.assert_not_called()


if __name__ == '__main__':
    unittest.main()
