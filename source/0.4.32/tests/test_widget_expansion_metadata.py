import sys
import tempfile
import unittest
from unittest import mock
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addons/service.actweeter/resources/lib"))
import interface_layout  # noqa: E402


class ExpandableWidgetMetadataTests(unittest.TestCase):
    def test_metadata_report_postwrite_failure_recovers_all_owned_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service, profile = root/'service', root/'profile'
            service.mkdir()
            profile.mkdir()
            cache = profile/'data_cache_p1_premium_meta_movie_5_es.json'
            cache.write_bytes(b'old metadata')
            report = service/'metadata_preferences.json'
            report.write_bytes(b'{"schema":0}')
            settings = {'tmdb_language':'en-US', 'interface_language':'English'}
            addon = mock.Mock()
            addon.getSetting.side_effect = settings.get
            addon.setSetting.side_effect = settings.__setitem__
            addon.getAddonInfo.return_value = str(profile)
            vfs = mock.Mock()
            vfs.translatePath.side_effect = lambda path: path
            original_write = interface_layout.atomic_write
            failed = [False]
            def fail_after_write(path, data):
                original_write(path, data)
                if Path(path)==report and not failed[0]:
                    failed[0]=True
                    raise OSError('simulated postwrite failure')
            with mock.patch.object(interface_layout,'atomic_write',side_effect=fail_after_write):
                with self.assertRaises(OSError):
                    interface_layout.prepare_metadata_language(lambda _:addon,vfs,service)
            self.assertEqual(settings,{'tmdb_language':'en-US','interface_language':'English'})
            self.assertEqual(cache.read_bytes(),b'old metadata')
            self.assertEqual(report.read_bytes(),b'{"schema":0}')

    def test_metadata_cache_concurrent_replacement_is_not_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service, profile = root/'service', root/'profile'
            service.mkdir()
            profile.mkdir()
            cache = profile/'data_cache_p1_premium_meta_movie_5_es.json'
            cache.write_bytes(b'old metadata')
            settings = {'tmdb_language':'en-US', 'interface_language':'English'}
            addon = mock.Mock()
            addon.getSetting.side_effect = settings.get
            def change_setting(key,value):
                settings[key]=value
                cache.write_bytes(b'new metadata from other process')
            addon.setSetting.side_effect = change_setting
            addon.getAddonInfo.return_value = str(profile)
            vfs = mock.Mock()
            vfs.translatePath.side_effect = lambda path: path
            with self.assertRaisesRegex(OSError,'metadata cache changed'):
                interface_layout.prepare_metadata_language(lambda _:addon,vfs,service)
            self.assertEqual(cache.read_bytes(),b'new metadata from other process')
            self.assertEqual(settings,{'tmdb_language':'en-US','interface_language':'English'})

    def test_metadata_preflight_rejects_symlinked_state_and_backup_root(self):
        for linked in ('metadata_preferences.json', 'metadata_backups'):
            with self.subTest(linked=linked), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                service = root / 'service'
                service.mkdir()
                outside = root / 'outside'
                if linked == 'metadata_backups':
                    outside.mkdir()
                    (service / linked).symlink_to(outside, target_is_directory=True)
                else:
                    outside.write_text('{}')
                    (service / linked).symlink_to(outside)
                addon = mock.Mock()
                addon.getSetting.side_effect = lambda key: 'en-US' if key == 'tmdb_language' else 'English'
                addon.getAddonInfo.return_value = str(root / 'profile')
                vfs = mock.Mock()
                vfs.translatePath.side_effect = lambda path: path
                with self.assertRaises(ValueError):
                    interface_layout.prepare_metadata_language(
                        lambda _name: addon, vfs, service)
                addon.setSetting.assert_not_called()

    def test_metadata_preflight_refuses_linked_cache_without_setting_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = root / 'service'
            profile = root / 'profile'
            service.mkdir()
            profile.mkdir()
            outside = root / 'private'
            outside.write_bytes(b'private')
            cache = profile / 'data_cache_p1_premium_meta_movie_5_es.json'
            cache.symlink_to(outside)
            addon = mock.Mock()
            addon.getSetting.side_effect = lambda key: 'en-US' if key == 'tmdb_language' else 'English'
            addon.getAddonInfo.return_value = str(profile)
            vfs = mock.Mock()
            vfs.translatePath.side_effect = lambda path: path
            with self.assertRaises(ValueError):
                interface_layout.prepare_metadata_language(lambda _name: addon, vfs, service)
            addon.setSetting.assert_not_called()
            self.assertEqual(outside.read_bytes(), b'private')

    def test_property_persistence_refuses_linked_state_or_backup_root(self):
        for linked in ('interface_layout_state.json', 'interface_backups'):
            with self.subTest(linked=linked), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                shortcuts = root / 'shortcuts'
                service = root / 'service'
                shortcuts.mkdir()
                service.mkdir()
                outside = root / 'outside'
                if linked == 'interface_backups':
                    outside.mkdir()
                    (service / linked).symlink_to(outside, target_is_directory=True)
                else:
                    outside.write_text('{}')
                    (service / linked).symlink_to(outside)
                with self.assertRaises(ValueError):
                    interface_layout.persist_generated_expandable_properties(
                        shortcuts, service, root / 'generated.xml', {})
                self.assertFalse((shortcuts / 'skin.actweeter.properties').exists())

    def test_property_persistence_postwrite_failure_restores_state_and_properties(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shortcuts = root / 'shortcuts'
            service = root / 'service'
            shortcuts.mkdir()
            service.mkdir()
            properties = shortcuts / 'skin.actweeter.properties'
            original_properties = b'[["custom", "id", "user", "keep"]]'
            properties.write_bytes(original_properties)
            state = service / 'interface_layout_state.json'
            original_state = b'{"layout_version":12,"build_status":"PENDING"}'
            state.write_bytes(original_state)
            documents = {'skin.actweeter-moviehub.DATA.xml': b'data'}
            real_write = interface_layout.atomic_write
            failed = [False]
            def postwrite_failure(path, data):
                real_write(path, data)
                if Path(path) == state and not failed[0]:
                    failed[0] = True
                    raise OSError('simulated state readback failure')
            with mock.patch.object(interface_layout, 'expandable_shortcut_ids',
                                   return_value={'default': 'moviehub'}), \
                 mock.patch.object(interface_layout, 'generated_shortcut_identities',
                                   return_value={'default': ('moviehub.1', 'label')}), \
                 mock.patch.object(interface_layout, 'atomic_write',
                                   side_effect=postwrite_failure):
                with self.assertRaises(OSError):
                    interface_layout.persist_generated_expandable_properties(
                        shortcuts, service, root / 'generated.xml', documents)
            self.assertEqual(properties.read_bytes(), original_properties)
            self.assertEqual(state.read_bytes(), original_state)

    def test_apply_refuses_directory_shortcut_without_partial_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shortcuts = root / 'shortcuts'
            service = root / 'service'
            shortcuts.mkdir()
            service.mkdir()
            name = sorted(interface_layout.source_documents(ROOT / 'addons/skin.actweeter'))[-1]
            (shortcuts / name).mkdir()
            with self.assertRaises(ValueError):
                interface_layout.apply_layout(shortcuts, service,
                    ROOT / 'addons/skin.actweeter', interface_layout.SETTINGS)
            self.assertTrue((shortcuts / name).is_dir())
            self.assertEqual(sorted(p.name for p in shortcuts.iterdir()), [name])

    def test_apply_refuses_traversal_or_duplicate_snapshot_names(self):
        for name in ('../outside', 'nested/entry', 'skin.actweeter.properties',
                     'previous-state.json'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                shortcuts = root / 'shortcuts'
                service = root / 'service'
                shortcuts.mkdir()
                service.mkdir()
                victim = root / 'outside'
                victim.write_bytes(b'preserve')
                with self.assertRaises(ValueError):
                    interface_layout.apply_layout(shortcuts, service,
                        ROOT / 'addons/skin.actweeter', interface_layout.SETTINGS,
                        snapshots={name: victim})
                self.assertEqual(victim.read_bytes(), b'preserve')
                self.assertEqual(list(shortcuts.iterdir()), [])

    def test_apply_then_rollback_restores_exact_original_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shortcuts = root / 'shortcuts'
            service = root / 'service'
            shortcuts.mkdir()
            service.mkdir()
            old = b'{"layout_version": 0, "files": {}}'
            state = service / 'interface_layout_state.json'
            state.write_bytes(old)
            result = interface_layout.apply_layout(shortcuts, service,
                ROOT / 'addons/skin.actweeter', interface_layout.SETTINGS)
            self.assertEqual(result['status'], 'APPLIED')
            self.assertTrue(result['changed'])
            self.assertEqual(interface_layout.rollback_layout(shortcuts, service),
                             interface_layout.SETTINGS)
            self.assertEqual(state.read_bytes(), old)
            self.assertEqual(list(shortcuts.iterdir()), [])

    def test_rollback_refuses_linked_state_before_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = root / 'service'
            shortcuts = root / 'shortcuts'
            service.mkdir()
            shortcuts.mkdir()
            external = root / 'external.json'
            external.write_text('{"backup":"outside","files":{}}')
            (service / 'interface_layout_state.json').symlink_to(external)
            with self.assertRaises(ValueError):
                interface_layout.rollback_layout(shortcuts, service)
            self.assertEqual(external.read_text(), '{"backup":"outside","files":{}}')

    def test_rollback_rejects_unsafe_manifest_names_before_backup_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = root / 'service'
            shortcuts = root / 'shortcuts'
            service.mkdir()
            shortcuts.mkdir()
            state = {'backup': 'valid-backup', 'files': {'../outside': 'abc'}}
            (service / 'interface_layout_state.json').write_text(json.dumps(state))
            backup = service / 'interface_backups' / 'valid-backup'
            backup.mkdir(parents=True)
            (backup / 'MANIFEST.json').write_text(json.dumps({'files': {}}))
            with self.assertRaises(ValueError):
                interface_layout.rollback_layout(shortcuts, service)
            self.assertEqual(list(shortcuts.iterdir()), [])

    def test_rollback_properties_hash_cannot_authorize_other_shortcut(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = root / 'service'
            shortcuts = root / 'shortcuts'
            service.mkdir()
            shortcuts.mkdir()
            name = 'skin.actweeter-moviehub.DATA.xml'
            current = b'user changed shortcut'
            (shortcuts / name).write_bytes(current)
            state = {'backup': 'valid-backup', 'files': {name: 'wrong-hash'},
                     'properties_hash': interface_layout.digest(current)}
            (service / 'interface_layout_state.json').write_text(json.dumps(state))
            backup = service / 'interface_backups' / 'valid-backup'
            backup.mkdir(parents=True)
            (backup / 'MANIFEST.json').write_text(json.dumps({'files': {
                name: {'exists': False}, 'skin.actweeter.properties': {'exists': False},
                'previous-state.json': {'exists': False},
            }}))
            self.assertIsNone(interface_layout.rollback_layout(shortcuts, service))
            self.assertEqual((shortcuts / name).read_bytes(), current)

    def test_apply_layout_recovers_state_after_postwrite_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shortcuts = root / 'shortcuts'
            service = root / 'service'
            shortcuts.mkdir()
            service.mkdir()
            state = service / 'interface_layout_state.json'
            previous = b'{"layout_version": 0, "files": {}}'
            state.write_bytes(previous)
            real_write = interface_layout.atomic_write
            failed = [False]
            def fail_after_state_write(path, data):
                real_write(path, data)
                if Path(path) == state and not failed[0]:
                    failed[0] = True
                    raise OSError('simulated failed state readback')
            with mock.patch.object(interface_layout, 'atomic_write', side_effect=fail_after_state_write):
                with self.assertRaises(OSError):
                    interface_layout.apply_layout(shortcuts, service,
                        ROOT / 'addons/skin.actweeter', interface_layout.SETTINGS)
            self.assertEqual(state.read_bytes(), previous)
            self.assertEqual(list(shortcuts.iterdir()), [])

    def test_rollback_refuses_linked_backup_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shortcuts = root / 'shortcuts'
            service = root / 'service'
            shortcuts.mkdir()
            service.mkdir()
            (service / 'interface_layout_state.json').write_text(json.dumps({
                'backup': 'some-backup', 'files': {},
            }))
            external = root / 'external'
            external.mkdir()
            (service / 'interface_backups').symlink_to(external, target_is_directory=True)
            with self.assertRaises(ValueError):
                interface_layout.rollback_layout(shortcuts, service)
            self.assertEqual(list(external.iterdir()), [])

    def test_backup_interface_refuses_linked_destinations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = root / 'service'
            service.mkdir()
            skin = root / 'skin'
            skin.mkdir()
            external = root / 'external'
            external.mkdir()
            addon = mock.Mock()
            addon.getAddonInfo.side_effect = lambda key: str(service if key == 'profile' else skin)
            factory = mock.Mock(return_value=addon)
            vfs = mock.Mock()
            vfs.translatePath.side_effect = lambda path: path
            vfs.listdir.return_value = ([], [])
            for name in ('interface_backups', 'interface_backup_only.json'):
                with self.subTest(name=name):
                    link = service / name
                    link.symlink_to(external, target_is_directory=True)
                    with self.assertRaises(ValueError):
                        interface_layout.backup_interface(factory, vfs)
                    link.unlink()
            self.assertEqual(list(external.iterdir()), [])

    def test_apply_layout_refuses_linked_state_and_backup_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shortcuts = root / 'shortcuts'
            service = root / 'service'
            shortcuts.mkdir()
            service.mkdir()
            victim = root / 'external.json'
            victim.write_text('{"private": true}')
            for linked_name in ('interface_layout_state.json', 'interface_backups'):
                with self.subTest(linked_name=linked_name):
                    linked = service / linked_name
                    linked.symlink_to(victim)
                    with self.assertRaises(ValueError):
                        interface_layout.apply_layout(
                            shortcuts, service, ROOT / 'addons/skin.actweeter',
                            interface_layout.SETTINGS)
                    self.assertEqual(victim.read_text(), '{"private": true}')
                    self.assertEqual(list(shortcuts.iterdir()), [])
                    linked.unlink()

    def test_rollback_preserves_user_deleted_owned_shortcut(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shortcuts = root / 'shortcuts'
            service = root / 'service'
            shortcuts.mkdir()
            backup_id = '20261019T000000Z-abcdef12'
            backup = service / 'interface_backups' / backup_id
            backup.mkdir(parents=True)
            name = 'skin.actweeter-moviehub.DATA.xml'
            original = b'previous shortcut'
            (backup / name).write_bytes(original)
            (backup / 'MANIFEST.json').write_text(json.dumps({'files': {
                name: {'exists': True, 'sha256': interface_layout.digest(original)},
                'skin.actweeter.properties': {'exists': False},
                'previous-state.json': {'exists': False},
            }}))
            state = service / 'interface_layout_state.json'
            state.write_text(json.dumps({'backup': backup_id, 'files': {
                name: interface_layout.digest(b'new shortcut'),
            }}))
            before = state.read_bytes()
            self.assertIsNone(interface_layout.rollback_layout(shortcuts, service))
            self.assertFalse((shortcuts / name).exists())
            self.assertEqual(state.read_bytes(), before)

    def test_rollback_write_failure_restores_previous_shortcut_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shortcuts = root / 'shortcuts'
            service = root / 'service'
            shortcuts.mkdir()
            backup_id = '20261019T000000Z-abcdef12'
            backup = service / 'interface_backups' / backup_id
            backup.mkdir(parents=True)
            names = ['skin.actweeter-a.DATA.xml', 'skin.actweeter-b.DATA.xml']
            state_files, entries = {}, {}
            for i, name in enumerate(names):
                current = ('current-%d' % i).encode()
                (shortcuts / name).write_bytes(current)
                state_files[name] = interface_layout.digest(current)
                old = ('previous-%d' % i).encode()
                (backup / name).write_bytes(old)
                entries[name] = {'exists': True, 'sha256': interface_layout.digest(old)}
            entries['skin.actweeter.properties'] = {'exists': False}
            entries['previous-state.json'] = {'exists': False}
            (backup / 'MANIFEST.json').write_text(json.dumps({'files': entries}))
            state = service / 'interface_layout_state.json'
            state.write_text(json.dumps({'backup': backup_id, 'files': state_files}))
            before_state = state.read_bytes()
            real_write = interface_layout.atomic_write
            failed = [False]
            def fail_second_once(path, data):
                if Path(path).name == names[1] and not failed[0]:
                    failed[0] = True
                    raise OSError('simulated disk error')
                return real_write(path, data)
            with mock.patch.object(interface_layout, 'atomic_write', side_effect=fail_second_once):
                with self.assertRaises(OSError):
                    interface_layout.rollback_layout(shortcuts, service)
            for i, name in enumerate(names):
                self.assertEqual((shortcuts / name).read_bytes(), ('current-%d' % i).encode())
            self.assertEqual(state.read_bytes(), before_state)

    def test_rollback_corrupt_later_backup_preserves_all_shortcuts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shortcuts = root / 'shortcuts'
            service = root / 'service'
            shortcuts.mkdir()
            backup_id = '20261019T000000Z-abcdef12'
            backup = service / 'interface_backups' / backup_id
            backup.mkdir(parents=True)
            names = ['skin.actweeter-a.DATA.xml', 'skin.actweeter-b.DATA.xml']
            state_files, entries = {}, {}
            for i, name in enumerate(names):
                current = ('current-%d' % i).encode()
                (shortcuts / name).write_bytes(current)
                state_files[name] = interface_layout.digest(current)
                wanted = ('previous-%d' % i).encode()
                (backup / name).write_bytes(wanted if i == 0 else b'CORRUPTED')
                entries[name] = {'exists': True, 'sha256': interface_layout.digest(wanted)}
            entries['skin.actweeter.properties'] = {'exists': False}
            entries['previous-state.json'] = {'exists': False}
            (backup / 'MANIFEST.json').write_text(json.dumps({'files': entries}))
            (service / 'interface_layout_state.json').write_text(json.dumps({
                'backup': backup_id, 'files': state_files,
            }))
            with self.assertRaises(OSError):
                interface_layout.rollback_layout(shortcuts, service)
            for i, name in enumerate(names):
                self.assertEqual((shortcuts / name).read_bytes(), ('current-%d' % i).encode())

    def test_rollback_missing_previous_state_entry_preserves_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shortcuts = root / 'shortcuts'
            service = root / 'service'
            shortcuts.mkdir()
            backup_id = '20261019T000000Z-abcdef12'
            backup = service / 'interface_backups' / backup_id
            backup.mkdir(parents=True)
            state = service / 'interface_layout_state.json'
            state.write_text(json.dumps({'backup': backup_id, 'files': {}}))
            before = state.read_bytes()
            (backup / 'MANIFEST.json').write_text(json.dumps({'files': {
                'skin.actweeter.properties': {'exists': False},
            }}))
            with self.assertRaises(OSError):
                interface_layout.rollback_layout(shortcuts, service)
            self.assertEqual(state.read_bytes(), before)

    def test_rollback_missing_manifest_does_not_delete_shortcuts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shortcuts = root / 'shortcuts'
            service = root / 'service'
            shortcuts.mkdir()
            service.mkdir()
            filename = 'skin.actweeter-test.DATA.xml'
            original = shortcuts / filename
            original.write_bytes(b'current')
            backup_id = '20261019T000000Z-abcdef12'
            (service / 'interface_backups' / backup_id).mkdir(parents=True)
            (service / 'interface_layout_state.json').write_text(json.dumps({
                'backup': backup_id, 'files': {filename: interface_layout.digest(b'current')},
            }))
            with self.assertRaises(OSError):
                interface_layout.rollback_layout(shortcuts, service)
            self.assertEqual(original.read_bytes(), b'current')

    def test_rollback_rejects_symlink_without_mutating_shortcuts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shortcuts = root / 'shortcuts'
            service = root / 'service'
            shortcuts.mkdir()
            service.mkdir()
            victim = root / 'outside.xml'
            victim.write_text('private', encoding='utf-8')
            (shortcuts / 'skin.actweeter-test.DATA.xml').symlink_to(victim)
            backup = service / 'interface_backups' / '20261019T000000Z-abcdef12'
            backup.mkdir(parents=True)
            (backup / 'MANIFEST.json').write_text(json.dumps({'files': {
                'skin.actweeter-test.DATA.xml': {'exists': False},
                'skin.actweeter.properties': {'exists': False},
                'previous-state.json': {'exists': False},
            }}))
            (service / 'interface_layout_state.json').write_text(json.dumps({
                'backup': '20261019T000000Z-abcdef12',
                'files': {'skin.actweeter-test.DATA.xml': 'fake'},
            }))
            with self.assertRaises(ValueError):
                interface_layout.rollback_layout(shortcuts, service)
            self.assertEqual(victim.read_text(), 'private')

    def test_supported_provider_list_route_gets_expansion_without_rewriting_reload(self):
        route = (
            "plugin://plugin.video.xstream-pro/?mode=premium&view=continue&"
            "stype=movie&reload=$INFO[Window(Home).Property(Refresh)]"
        )
        expanded, enabled = interface_layout.expandable_widget_action(route)
        self.assertTrue(enabled)
        self.assertTrue(expanded.startswith(route + "&"))
        self.assertIn("actweeter_expand=1&limit=20", expanded)
        self.assertEqual(interface_layout.expandable_widget_action(expanded), (expanded, True))

    def test_non_list_and_non_provider_routes_are_not_expandable(self):
        routes = (
            "plugin://plugin.video.xstream-pro/?mode=movies_menu",
            "plugin://plugin.video.xstream-pro/?mode=premium&view=collections_root&stype=movie",
            "plugin://plugin.video.xstream-pro/?mode=xstream_trakt_list&section=recommendations&tmdb_type=movie",
            "plugin://plugin.video.youtube/?video_id=example",
        )
        for route in routes:
            with self.subTest(route=route):
                self.assertEqual(interface_layout.expandable_widget_action(route), (route, False))

    def test_source_documents_marks_only_supported_default_rows_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            skin = Path(temp)
            shortcuts = skin / "shortcuts"
            shortcuts.mkdir()
            rows = {
                "mainmenu": [("Inicio", "ActivateWindow(Home)")],
                "powermenu": [("Ajustes", "ActivateWindow(Settings)")],
                "inicio-1": [
                    ("Continue", "plugin://plugin.video.xstream-pro/?mode=premium&view=continue&stype=both&reload=$INFO[Window(Home).Property(R)]"),
                    ("Movies", "plugin://plugin.video.xstream-pro/?mode=premium&stype=movie"),
                    ("Collections", "plugin://plugin.video.xstream-pro/?mode=premium&view=collections_root&stype=movie"),
                ],
                "10000-1": [("Series", "plugin://plugin.video.xstream-pro/?mode=premium&stype=series")],
                "moviehub": [("Popular", "plugin://plugin.video.xstream-pro/?mode=premium&view=popular&stype=movie")],
                "tvshowhub": [("Recommendations", "plugin://plugin.video.xstream-pro/?mode=xstream_trakt_list&section=recommendations&tmdb_type=tv")],
            }
            for group, items in rows.items():
                root = ET.Element("shortcuts")
                for label, action in items:
                    shortcut = ET.SubElement(root, "shortcut")
                    ET.SubElement(shortcut, "label").text = label
                    ET.SubElement(shortcut, "label2")
                    ET.SubElement(shortcut, "action").text = action
                (shortcuts / (group + ".DATA.xml")).write_bytes(ET.tostring(root))

            output = interface_layout.source_documents(skin)
            self.assertEqual(output, interface_layout.source_documents(skin))
            home = ET.fromstring(output["skin.actweeter-inicio-1.DATA.xml"])
            first = home.find("shortcut")
            route = first.findtext("action")
            self.assertIn("reload=$INFO[Window(Home).Property(R)]&amp;actweeter_expand=1&amp;limit=20", ET.tostring(first, encoding="unicode"))
            self.assertTrue(first.findtext("defaultID").startswith("actweeter-expand-inicio-1-"))
            self.assertIsNone(first.find("property[@name='widgetExpandable']"))
            self.assertIn("actweeter_expand=1", route)

            movies = ET.fromstring(output["skin.actweeter-moviehub.DATA.xml"])
            popular = movies.find("shortcut")
            self.assertTrue(popular.findtext("defaultID").startswith("actweeter-expand-moviehub-"))
            self.assertIsNone(popular.find("property[@name='widgetExpandable']"))

            series = ET.fromstring(output["skin.actweeter-tvshowhub.DATA.xml"])
            self.assertNotIn("actweeter_expand=1", series.findtext("shortcut/action"))
            self.assertIsNone(series.find("shortcut/defaultID"))

            self.assertGreater(len(interface_layout.expandable_shortcut_ids(output)), 0)
            identities = {}
            for default_id, source_group in interface_layout.expandable_shortcut_ids(output).items():
                runtime_group = {"inicio-1": "inicio.1", "10000-1": "inicio.2",
                                 "moviehub": "peliculas.1", "tvshowhub": "series.1"}[source_group]
                identities[default_id] = (runtime_group, "widget_" + default_id[-6:])
            rows = interface_layout.expandable_property_rows(output, identities)
            self.assertTrue(all(len(row) == 4 and row[2:] == ["widgetExpandable", "true"]
                                for row in rows))
            self.assertTrue(any(row[0] == "inicio.1" and row[1] for row in rows))

    def test_skinshortcuts_property_merge_preserves_user_data_and_is_idempotent(self):
        required = ["moviehub.1", "popular", "widgetExpandable", "true"]
        unrelated = ["mainmenu", "custom-menu-item", "myUserProperty", "keep-me"]
        existing = interface_layout.json.dumps([unrelated], ensure_ascii=False).encode("utf-8")

        merged = interface_layout.merge_expandable_properties(existing, [required])
        rows = interface_layout.json.loads(merged.decode("utf-8"))
        self.assertEqual(rows, [unrelated, required])
        self.assertEqual(interface_layout.merge_expandable_properties(merged, [required]), merged)

    def test_skinshortcuts_property_merge_refuses_to_overwrite_a_conflict(self):
        existing = interface_layout.json.dumps([
            ["moviehub.1", "popular", "widgetExpandable", "false"]
        ]).encode("utf-8")
        with self.assertRaisesRegex(ValueError, "conflicting"):
            interface_layout.merge_expandable_properties(existing, [
                ["moviehub.1", "popular", "widgetExpandable", "true"]
            ])

    def test_generated_identity_uses_runtime_group_and_label_id(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "generated.xml"
            root = ET.Element("includes")
            item = ET.SubElement(root, "item")
            for name, value in (("defaultID", "expand-1"),
                                ("group", "inicio.1"),
                                ("labelID", "continuarviendo")):
                ET.SubElement(item, "property", name=name).text = value
            path.write_bytes(ET.tostring(root))
            self.assertEqual(interface_layout.generated_shortcut_identities(
                path, {"expand-1"}), {"expand-1": ("inicio.1", "continuarviendo")})
            item.find("property[@name='labelID']").text = ""
            path.write_bytes(ET.tostring(root))
            with self.assertRaisesRegex(ValueError, "group or labelID"):
                interface_layout.generated_shortcut_identities(path, {"expand-1"})

    def test_unmaterialized_default_shortcuts_are_skipped_until_active(self):
        documents = interface_layout.source_documents(ROOT / "addons/skin.actweeter")
        expected = interface_layout.expandable_shortcut_ids(documents)
        active_id = next(iter(expected))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "generated.xml"
            root = ET.Element("includes")
            item = ET.SubElement(root, "item")
            for name, value in (("defaultID", active_id),
                                ("group", "inicio.1"),
                                ("labelID", "continuarviendo")):
                ET.SubElement(item, "property", name=name).text = value
            path.write_bytes(ET.tostring(root))

            identities = interface_layout.generated_shortcut_identities(
                path, set(expected))
            self.assertEqual(set(identities), {active_id})
            rows = interface_layout.expandable_property_rows(documents, identities)
            self.assertEqual(rows, [["inicio.1", "continuarviendo",
                                     "widgetExpandable", "true"]])

    def test_active_generated_widget_without_expansion_property_is_not_ready(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "generated.xml"
            root = ET.Element("includes")
            template = ET.SubElement(root, "include", name="skinshortcuts-template-Widgets")
            item = ET.SubElement(template, "include", name="widget-row")
            ET.SubElement(item, "param", name="widgetPath", value=(
                "plugin://plugin.video.xstream-pro/?mode=premium&view=popular&stype=movie"
                "&actweeter_expand=1&limit=20"))
            ET.SubElement(item, "param", name="widgetExpandable", value="")
            path.write_bytes(ET.tostring(root))

            rows = interface_layout.generated_rows(path)
            self.assertEqual(len(rows["Widgets"]), 1)
            self.assertFalse(rows["Widgets"][0]["expansion_ready"])

    def test_legacy_five_field_row_is_preserved_and_correct_four_field_row_added(self):
        legacy = ["inicio-1", "", "widgetExpandable", "true", "expand-1"]
        existing = json.dumps([legacy]).encode("utf-8")
        correct = ["inicio.1", "continuarviendo", "widgetExpandable", "true"]
        merged = json.loads(interface_layout.merge_expandable_properties(
            existing, [correct]).decode("utf-8"))
        self.assertIn(legacy, merged)
        self.assertIn(correct, merged)

    def test_skinshortcuts_property_merge_refuses_malformed_user_file(self):
        with self.assertRaises((ValueError, SyntaxError)):
            interface_layout.merge_expandable_properties(
                b"this is not a Skin Shortcuts properties document", [])

    def test_upgrade_migrates_owned_shortcuts_with_backup(self):
        old_skin = ROOT.parent / "0.4.28/addons/skin.actweeter"
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            shortcuts = temp / "userdata/addon_data/script.skinshortcuts"
            service = temp / "service"
            shortcuts.mkdir(parents=True)
            old_docs = {
                "skin.actweeter-" + group + ".DATA.xml":
                    (old_skin / "shortcuts" / (group + ".DATA.xml")).read_bytes()
                for group in interface_layout.GROUPS
            }
            old_hashes = {}
            for name, data in old_docs.items():
                (shortcuts / name).write_bytes(data)
                old_hashes[name] = hashlib.sha256(data).hexdigest()
            (service / "interface_layout_state.json").parent.mkdir(parents=True)
            (service / "interface_layout_state.json").write_text(json.dumps({
                "layout_version": 8,
                "files": old_hashes,
                "settings": interface_layout.SETTINGS,
            }), encoding="utf-8")

            result = interface_layout.apply_layout(
                shortcuts, service, ROOT / "addons/skin.actweeter",
                interface_layout.SETTINGS)
            self.assertEqual(result["status"], "APPLIED")
            migrated = ET.parse(shortcuts / "skin.actweeter-moviehub.DATA.xml").getroot()
            self.assertIn("actweeter_expand=1", migrated.findtext("shortcut/action"))
            properties_path = shortcuts / "skin.actweeter.properties"
            self.assertFalse(properties_path.exists())
            documents = interface_layout.source_documents(ROOT / "addons/skin.actweeter")
            generated = temp / "generated-includes.xml"
            generated_root = ET.Element("includes")
            for default_id, group in interface_layout.expandable_shortcut_ids(documents).items():
                item = ET.SubElement(generated_root, "item")
                for key, value in (("defaultID", default_id), ("group", group + ".1"),
                                   ("labelID", "label_" + default_id[-6:])):
                    ET.SubElement(item, "property", name=key).text = value
            generated.write_bytes(ET.tostring(generated_root))
            persisted = interface_layout.persist_generated_expandable_properties(
                shortcuts, service, generated, documents)
            self.assertTrue(persisted["changed"])
            properties = json.loads(properties_path.read_text(encoding="utf-8"))
            self.assertTrue(properties)
            self.assertTrue(all(len(row) == 4 and row[2:] == ["widgetExpandable", "true"]
                                for row in properties))
            current_state = interface_layout.load_state(service / "interface_layout_state.json")
            self.assertEqual(interface_layout.digest(properties_path.read_bytes()),
                             current_state["properties_hash"])
            identities = interface_layout.generated_shortcut_identities(
                generated, interface_layout.expandable_shortcut_ids(documents))
            self.assertTrue(interface_layout.verify_expandable_property_store(
                shortcuts, documents, identities))
            stored = json.loads(properties_path.read_text(encoding="utf-8"))
            stored[0][3] = "false"
            properties_path.write_text(json.dumps(stored), encoding="utf-8")
            self.assertFalse(interface_layout.verify_expandable_property_store(
                shortcuts, documents, identities))
            manifest = json.loads((service / "interface_backups" / result["backup"] / "MANIFEST.json").read_text())
            self.assertTrue(manifest["files"]["skin.actweeter-moviehub.DATA.xml"]["exists"])
            self.assertFalse(manifest["files"]["skin.actweeter.properties"]["exists"])

    def test_upgrade_refuses_to_overwrite_customized_shortcuts_without_consent(self):
        old_skin = ROOT.parent / "0.4.28/addons/skin.actweeter"
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            shortcuts = temp / "userdata/addon_data/script.skinshortcuts"
            service = temp / "service"
            shortcuts.mkdir(parents=True)
            old_docs = {
                "skin.actweeter-" + group + ".DATA.xml":
                    (old_skin / "shortcuts" / (group + ".DATA.xml")).read_bytes()
                for group in interface_layout.GROUPS
            }
            old_hashes = {}
            for name, data in old_docs.items():
                old_hashes[name] = hashlib.sha256(data).hexdigest()
                (shortcuts / name).write_bytes(data)
            target = shortcuts / "skin.actweeter-moviehub.DATA.xml"
            customized = target.read_bytes() + b"\n<!-- user edit -->\n"
            target.write_bytes(customized)
            service.mkdir()
            (service / "interface_layout_state.json").write_text(json.dumps({
                "layout_version": 8,
                "files": old_hashes,
                "settings": interface_layout.SETTINGS,
            }), encoding="utf-8")

            result = interface_layout.apply_layout(
                shortcuts, service, ROOT / "addons/skin.actweeter",
                interface_layout.SETTINGS)
            self.assertEqual(result["status"], "CONSENT_REQUIRED")
            self.assertEqual(target.read_bytes(), customized)

    def test_upgrade_appends_properties_without_discarding_existing_customizations(self):
        old_skin = ROOT.parent / "0.4.28/addons/skin.actweeter"
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            shortcuts = temp / "userdata/addon_data/script.skinshortcuts"
            service = temp / "service"
            shortcuts.mkdir(parents=True)
            old_docs = {
                "skin.actweeter-" + group + ".DATA.xml":
                    (old_skin / "shortcuts" / (group + ".DATA.xml")).read_bytes()
                for group in interface_layout.GROUPS
            }
            for name, data in old_docs.items():
                (shortcuts / name).write_bytes(data)
            service.mkdir()
            (service / "interface_layout_state.json").write_text(json.dumps({
                "layout_version": 8,
                "files": {name: hashlib.sha256(data).hexdigest() for name, data in old_docs.items()},
                "settings": interface_layout.SETTINGS,
            }), encoding="utf-8")
            custom_row = ["moviehub.1", "user-shortcut", "userProperty", "preserve"]
            properties_path = shortcuts / "skin.actweeter.properties"
            properties_path.write_text(json.dumps([custom_row]), encoding="utf-8")

            result = interface_layout.apply_layout(
                shortcuts, service, ROOT / "addons/skin.actweeter",
                interface_layout.SETTINGS)
            self.assertEqual(result["status"], "APPLIED")
            self.assertEqual(json.loads(properties_path.read_text(encoding="utf-8")),
                             [custom_row])
            documents = interface_layout.source_documents(ROOT / "addons/skin.actweeter")
            generated = temp / "generated.xml"
            generated_root = ET.Element("includes")
            for default_id, group in interface_layout.expandable_shortcut_ids(documents).items():
                item = ET.SubElement(generated_root, "item")
                for key, value in (("defaultID", default_id), ("group", group + ".1"),
                                   ("labelID", "label_" + default_id[-6:])):
                    ET.SubElement(item, "property", name=key).text = value
            generated.write_bytes(ET.tostring(generated_root))
            interface_layout.persist_generated_expandable_properties(
                shortcuts, service, generated, documents)
            merged_rows = json.loads(properties_path.read_text(encoding="utf-8"))
            self.assertIn(custom_row, merged_rows)
            self.assertTrue(any(row[2:] == ["widgetExpandable", "true"]
                                for row in merged_rows if len(row) == 4))

    def test_skin_templates_use_explicit_flag_not_full_plugin_url_condition(self):
        include_file = ROOT / "addons/skin.actweeter/1080i/IncludesHomeWidgets.xml"
        template_file = ROOT / "addons/skin.actweeter/shortcuts/template.xml"
        include_text = include_file.read_text(encoding="utf-8")
        template_text = template_file.read_text(encoding="utf-8")
        self.assertNotIn("String.Contains($PARAM[widgetPath]", include_text)
        self.assertIn('condition="$PARAM[widgetExpandable]"', include_text)
        self.assertNotIn('String.IsEqual($PARAM[widgetExpandable],true)', include_text)
        self.assertIn('name="widgetExpandable"', template_text)

    def test_generated_layout_requires_route_and_template_expansion_metadata(self):
        route = "plugin://plugin.video.xstream-pro/?mode=premium&view=popular&stype=movie&actweeter_expand=1&limit=20"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "generated.xml"
            root = ET.Element("includes")
            include = ET.SubElement(root, "include", name="skinshortcuts-template-moviehub")
            row = ET.SubElement(include, "include", content="widget_base")
            ET.SubElement(row, "param", name="widgetPath", value=route)
            ET.SubElement(row, "param", name="widgetName", value="Populares")
            ET.SubElement(row, "param", name="widgetExpandable", value="true")
            path.write_bytes(ET.tostring(root))
            row_data = interface_layout.generated_rows(path)["moviehub"][0]
            self.assertTrue(row_data["provider_only"])
            self.assertTrue(row_data["expandable"])
            self.assertTrue(row_data["expansion_ready"])

            row.find("param[@name='widgetExpandable']").set("value", "false")
            path.write_bytes(ET.tostring(root))
            row_data = interface_layout.generated_rows(path)["moviehub"][0]
            self.assertFalse(row_data["expansion_ready"])

    def test_profile_property_write_is_idempotent_and_output_gate_reads_active_xml(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skin = ROOT / "addons/skin.actweeter"
            documents = interface_layout.source_documents(skin)
            identities = {default_id: (group + ".1", "label_" + default_id[-6:])
                          for default_id, group in
                          interface_layout.expandable_shortcut_ids(documents).items()}
            generated = root / "generated.xml"
            generated_root = ET.Element("includes")
            for default_id, (group, label_id) in identities.items():
                item = ET.SubElement(generated_root, "item")
                for key, value in (("defaultID", default_id), ("group", group),
                                   ("labelID", label_id)):
                    ET.SubElement(item, "property", name=key).text = value
            include = ET.SubElement(generated_root, "include",
                                     name="skinshortcuts-template-moviehub")
            widget = ET.SubElement(include, "include", content="widget_base")
            ET.SubElement(widget, "param", name="widgetPath", value=(
                "plugin://plugin.video.xstream-pro/?mode=premium&view=popular&stype=movie&"
                "actweeter_expand=1&limit=20"))
            ET.SubElement(widget, "param", name="widgetName", value="Popular")
            ET.SubElement(widget, "param", name="widgetExpandable", value="true")
            generated.write_bytes(ET.tostring(generated_root))
            shortcuts = root / "userdata/addon_data/script.skinshortcuts"
            service = root / "service"
            shortcuts.mkdir(parents=True)
            service.mkdir()
            (service / "interface_layout_state.json").write_text(
                json.dumps({"layout_version": 12, "build_status": "PENDING"}),
                encoding="utf-8")
            first = interface_layout.persist_generated_expandable_properties(
                shortcuts, service, generated, documents)
            second = interface_layout.persist_generated_expandable_properties(
                shortcuts, service, generated, documents)
            self.assertTrue(first["changed"])
            self.assertFalse(second["changed"])
            self.assertTrue(interface_layout.verify_expandable_property_store(
                shortcuts, documents, identities))
            rows = interface_layout.generated_rows(generated)
            self.assertTrue(rows["moviehub"][0]["expansion_ready"])


if __name__ == "__main__":
    unittest.main()
