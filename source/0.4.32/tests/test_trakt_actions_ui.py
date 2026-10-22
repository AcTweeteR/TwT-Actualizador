"""Kodi Trakt operations screen is strictly read-only and never creates a queue."""
import importlib.util
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
            self.assertTrue(any('desactivados' in row for row in rows))

    def test_other_action_is_rejected(self):
        with self.assertRaises(ValueError):
            ui.render(-1, addon=None, vfs=None, gui=None, plugin=None,
                      params={'action': ['trakt_send']})


if __name__ == '__main__':
    unittest.main()
