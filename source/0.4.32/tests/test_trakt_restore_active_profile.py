"""Restore preview is bound to XStream's selected profile, not a fixed ID."""
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
import importlib.util
import ast

ROOT = Path(__file__).resolve().parents[1] / 'addons/service.actweeter/resources/lib'
sys.path.insert(0, str(ROOT.parent))
sys.path.insert(0, str(ROOT))
from lib import trakt_restore_ui as ui


class Item:
    def __init__(self, label):
        self.label = label

    def setProperty(self, *_):
        pass


class TraktRestoreProfileTests(unittest.TestCase):
    def test_profile_setting_matches_xstream_profile_manager(self):
        addon = types.SimpleNamespace(getSetting=lambda _: 'Profile 7')
        self.assertEqual(ui.active_xstream_profile(addon), '7')

    def test_empty_setting_uses_xstream_default_profile(self):
        addon = types.SimpleNamespace(getSetting=lambda _: '')
        self.assertEqual(ui.active_xstream_profile(addon), '1')

    def test_render_uses_selected_profile_for_export_and_preview(self):
        addon = types.SimpleNamespace(
            getSetting=lambda _: 'Profile 4',
            getAddonInfo=lambda _: '/private/xstream-profile')
        plugin = types.SimpleNamespace(
            setPluginCategory=lambda *_: None,
            setContent=lambda *_: None,
            addDirectoryItem=lambda *_: None,
            endOfDirectory=lambda *_args, **_kwargs: None)
        with patch.object(ui, 'startup_restore_status', return_value={'pending': 0, 'safe': True}), \
             patch.object(ui, 'summarize_exports', return_value=[{
                 'name': 'snapshot-a', 'account': 'acct', 'watched_movies': 1,
                 'watched_episodes': 2, 'resume_pending': 0}]) as summary, \
             patch.object(ui, 'prepare_restore', return_value={}) as prepare, \
             patch.object(ui, 'stage_restore', return_value={'movies': 1, 'episodes': 2}) as stage:
            ui.render(1, gui=types.SimpleNamespace(ListItem=Item), plugin=plugin,
                      vfs=types.SimpleNamespace(translatePath=lambda path: path),
                      xstream_addon=addon, params={'operation': ['prepare']})

        self.assertEqual(summary.call_args.kwargs['profile'], '4')
        self.assertEqual(prepare.call_args.kwargs['profile'], '4')
        self.assertEqual(stage.call_args.kwargs['profile'], '4')
        self.assertEqual(stage.call_args.kwargs['movie_source'].name, 'watched_movies_p4.json')
        self.assertEqual(stage.call_args.kwargs['episode_source'].name, 'watched_episodes_p4.json')

    def test_render_offers_native_snapshot_and_refresh_links(self):
        addon = types.SimpleNamespace(
            getSetting=lambda _: 'Profile 2',
            getAddonInfo=lambda key: '/private/xstream-profile' if key == 'profile' else '1.1.2.22~beta1')
        links = []
        plugin = types.SimpleNamespace(
            setPluginCategory=lambda *_: None,
            setContent=lambda *_: None,
            addDirectoryItem=lambda _handle, url, _item, folder: links.append((url, folder)),
            endOfDirectory=lambda *_args, **_kwargs: None)
        with patch.object(ui, 'startup_restore_status', return_value={'pending': 0, 'safe': True}), \
             patch.object(ui, 'summarize_exports', return_value=[]):
            ui.render(1, gui=types.SimpleNamespace(ListItem=Item), plugin=plugin,
                      vfs=types.SimpleNamespace(translatePath=lambda path: path),
                      xstream_addon=addon)
        self.assertIn((ui.XSTREAM_SNAPSHOT, True), links)
        self.assertIn((ui.ROOT + '&operation=refresh', True), links)

    def test_old_xstream_does_not_offer_a_broken_snapshot_route(self):
        addon = types.SimpleNamespace(
            getSetting=lambda _: 'Profile 1',
            getAddonInfo=lambda key: '/private/xstream-profile' if key == 'profile' else '1.1.2.19')
        links = []
        plugin = types.SimpleNamespace(
            setPluginCategory=lambda *_: None,
            setContent=lambda *_: None,
            addDirectoryItem=lambda _handle, url, item, folder: links.append((url, item.label, folder)),
            endOfDirectory=lambda *_args, **_kwargs: None)
        with patch.object(ui, 'startup_restore_status', return_value={'pending': 0, 'safe': True}), \
             patch.object(ui, 'summarize_exports', return_value=[]):
            ui.render(1, gui=types.SimpleNamespace(ListItem=Item), plugin=plugin,
                      vfs=types.SimpleNamespace(translatePath=lambda path: path),
                      xstream_addon=addon)
        self.assertFalse(any(url == ui.XSTREAM_SNAPSHOT for url, _, _ in links))

    def test_diagnostic_plugin_routes_restore_action_to_ui(self):
        root = Path(__file__).resolve().parents[1] / 'addons/service.actweeter/resources'
        source = root / 'lib/diagnostic_plugin.py'
        tree = ast.parse(source.read_text('utf-8'))
        self.assertIsNotNone(tree)
        calls = []
        fake_ui = types.SimpleNamespace(render=lambda *args, **kwargs: calls.append((args, kwargs)))
        api = types.SimpleNamespace(Addon=lambda *_args: types.SimpleNamespace(
            getAddonInfo=lambda _: str(root.parent)))
        plugin = types.SimpleNamespace(endOfDirectory=lambda *_args, **_kwargs: None)
        modules = {
            'xbmc': types.SimpleNamespace(), 'xbmcaddon': api,
            'xbmcgui': types.SimpleNamespace(), 'xbmcplugin': plugin,
            'xbmcvfs': types.SimpleNamespace(translatePath=lambda path: path),
            'diagnostics': types.SimpleNamespace(encode_report_chunks=lambda _: [], report_payload=lambda **_: {}),
            'interface_layout': types.SimpleNamespace(interface_report=lambda *_: {}, backup_interface=lambda *_: None,
                                                      prepare_interface=lambda *_: None),
            'platform_support': types.SimpleNamespace(detect_platform=lambda *_: 'macos'),
            'slyguy_bridge_install': types.SimpleNamespace(install=lambda *_: None, rollback=lambda *_: None),
            'lib.trakt_restore_ui': fake_ui,
        }
        spec = importlib.util.spec_from_file_location('diagnostic_plugin_restore_test', source)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(module)
            module.main(['diagnostic_plugin.py', '1', '?action=trakt_restore'])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1]['params'], {'action': ['trakt_restore']})


if __name__ == '__main__':
    unittest.main()
