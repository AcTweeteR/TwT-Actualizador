"""Kodi Trakt operations screen is strictly read-only and never creates a queue."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'addons/service.actweeter/resources/lib'
spec = importlib.util.spec_from_file_location('trakt_actions_ui_test', ROOT / 'trakt_actions_ui.py')
ui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui)


class TraktActionsUiTests(unittest.TestCase):
    def test_empty_screen_does_not_create_queue(self):
        with tempfile.TemporaryDirectory() as directory:
            rows = []
            class Item:
                def __init__(self, label): self.label = label
                def setProperty(self, *_): pass
            plugin = types.SimpleNamespace(
                setPluginCategory=lambda *_: None, setContent=lambda *_: None,
                addDirectoryItem=lambda _handle, _url, item, _folder: rows.append(item.label),
                endOfDirectory=lambda *_args, **_kwargs: None)
            ui.render(1, addon=types.SimpleNamespace(getAddonInfo=lambda _: directory),
                      vfs=types.SimpleNamespace(translatePath=lambda path: path),
                      gui=types.SimpleNamespace(ListItem=Item), plugin=plugin,
                      params={'action': ['trakt_actions']})
            self.assertIn('Sin operaciones explícitas registradas', rows)
            self.assertFalse((Path(directory) / 'trakt_explicit_outbox.sqlite').exists())
            self.assertTrue(any('inciertas' in row for row in rows))

    def test_corrupt_queue_is_not_reported_as_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / 'trakt_explicit_outbox.sqlite').write_text('not a database')
            rows = []
            class Item:
                def __init__(self, label): self.label = label
                def setProperty(self, *_): pass
            plugin = types.SimpleNamespace(setPluginCategory=lambda *_: None, setContent=lambda *_: None,
                addDirectoryItem=lambda _handle, _url, item, _folder: rows.append(item.label),
                endOfDirectory=lambda *_args, **_kwargs: None)
            ui.render(1, addon=types.SimpleNamespace(getAddonInfo=lambda _: directory),
                      vfs=types.SimpleNamespace(translatePath=lambda path: path),
                      gui=types.SimpleNamespace(ListItem=Item), plugin=plugin,
                      params={'action': ['trakt_actions']})
            self.assertIn('Estado de operaciones explícitas no disponible', rows)
            self.assertNotIn('Sin operaciones explícitas registradas', rows)

    def test_only_pending_typed_action_can_be_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'trakt_explicit_outbox.sqlite'
            db = sqlite3.connect(path)
            db.execute('create table events (id text, state text, attempts integer, event text)')
            for identifier, state in [('a' * 64, 'pending'), ('b' * 64, 'unknown'), ('c' * 64, 'held'), ('d' * 64, 'retained')]:
                db.execute('insert into events values (?,?,?,?)', (identifier, state, 1, json.dumps({'schema': 2})))
            db.commit(); db.close()
            links = []
            class Item:
                def __init__(self, label): self.label = label
                def setProperty(self, *_): pass
            plugin = types.SimpleNamespace(setPluginCategory=lambda *_: None, setContent=lambda *_: None,
                addDirectoryItem=lambda _h, url, _item, folder: links.append((url, folder)),
                endOfDirectory=lambda *_a, **_kw: None)
            ui.render(1, addon=types.SimpleNamespace(getAddonInfo=lambda _: directory),
                vfs=types.SimpleNamespace(translatePath=lambda path: path),
                gui=types.SimpleNamespace(ListItem=Item), plugin=plugin, params={'action': ['trakt_actions']})
            self.assertIn(('plugin://plugin.video.xstream-pro/?mode=xstream_trakt_retry_manual&operation=' + 'a' * 64, True), links)
            self.assertFalse(any('b' * 64 in url for url, _ in links))
            self.assertFalse(any('d' * 64 in url for url, _ in links))
            self.assertTrue(any('c' * 64 in url for url, _ in links))

    def test_other_action_is_rejected(self):
        with self.assertRaises(ValueError):
            ui.render(-1, addon=None, vfs=None, gui=None, plugin=None,
                      params={'action': ['trakt_send']})


if __name__ == '__main__':
    unittest.main()
