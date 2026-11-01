"""The actual packaged Trakt menu must retain content and expose sync."""
import ast
import os
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = Path(os.environ.get("ACTWEETER_XSTREAM_LIVE_ZIP", ROOT / "docs/testing/repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.38~beta2.zip"))


class UnifiedTraktMenuTest(unittest.TestCase):
    def menu(self, enabled, authorized):
        with zipfile.ZipFile(PACKAGE) as archive:
            tree = ast.parse(archive.read("plugin.video.xstream-pro/resources/lib/tmdb_routes.py"))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "trakt_menu")
        calls = []
        lookup = {"_new_listitem": lambda label: label, "_t": lambda code: str(code)}
        env = {"trakt": SimpleNamespace(enabled=lambda: enabled, auth_configured=lambda: True, authorized=lambda: authorized),
               "c": lookup.__getitem__, "_label": lambda x: x, "_add_items": calls.append,
               "_folder_item": lambda label, params, icon: (params, label, True)}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])), "trakt_menu", "exec"), env)
        env["trakt_menu"]()
        return calls[0]

    def test_packaged_manual_routes_do_not_bypass_coordinator(self):
        with zipfile.ZipFile(PACKAGE) as archive:
            tree = ast.parse(archive.read('plugin.video.xstream-pro/resources/lib/tmdb_routes.py'))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'trakt_item_action_route')
        calls = [n for n in ast.walk(function) if isinstance(n, ast.Call)]
        self.assertTrue(any(isinstance(n.func, ast.Name) and n.func.id == 'coordinated_manual_action' for n in calls))
        self.assertFalse(any(isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
                             and n.func.value.id == 'trakt' and n.func.attr in
                             ('mark_watched', 'mark_unwatched', 'checkin_item', 'sync_item', 'post') for n in calls))

    def test_authorized_menu_keeps_content_and_exposes_sync(self):
        items = self.menu(True, True)
        self.assertTrue(any(isinstance(row[0], dict) and row[0].get("section") == "recommendations" for row in items))
        self.assertTrue(any(isinstance(row[0], dict) and row[0].get("section") == "watchlist" for row in items))
        self.assertTrue(any(isinstance(row[0], dict) and row[0].get("section") == "my" for row in items))
        self.assertIn("plugin://service.actweeter/?action=trakt_restore", [row[0] for row in items])

    def test_sync_entry_remains_when_content_is_disabled_or_unlinked(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                self.assertIn("plugin://service.actweeter/?action=trakt_restore", [row[0] for row in self.menu(enabled, False)])
