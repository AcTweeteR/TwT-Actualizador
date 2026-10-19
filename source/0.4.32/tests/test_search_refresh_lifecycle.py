"""Provider-only background refresh scheduling and pending lifecycle contracts."""
import ast
from contextlib import closing
import sqlite3
import tempfile
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'addons/service.actweeter/resources/lib'))
from search_background import RefreshGate, last_successful_sync, refresh_due


class RefreshLifecycleTests(unittest.TestCase):
    def test_sync_timestamp_rejects_nan_infinity_and_negative(self):
        for value, expected in (('nan',0.0),('inf',0.0),('-50',0.0),('123.5',123.5)):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp)/'provider_search_1.sqlite'
                with closing(sqlite3.connect(path)) as db, db:
                    db.execute('CREATE TABLE meta (key TEXT, value TEXT)')
                    db.execute('INSERT INTO meta VALUES (?,?)',('last_successful_sync',value))
                self.assertEqual(last_successful_sync(tmp,1),expected)
        self.assertFalse(refresh_due(float('nan'),123))
        self.assertFalse(refresh_due(0,float('nan')))

    def test_sync_database_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root/'external.sqlite'
            with closing(sqlite3.connect(target)) as db, db:
                db.execute('CREATE TABLE meta (key TEXT, value TEXT)')
                db.execute('INSERT INTO meta VALUES (?,?)',('last_successful_sync','123'))
            (root/'provider_search_1.sqlite').symlink_to(target)
            self.assertEqual(last_successful_sync(str(root),1),0.0)

    def test_initial_refresh_is_allowed_before_one_hour_uptime(self):
        gate = RefreshGate()
        self.assertTrue(gate.should_request(0, 120))
        gate.mark_requested(120)
        self.assertFalse(gate.should_request(0, 121))
        self.assertFalse(gate.should_request(0, 3719))
        self.assertTrue(gate.should_request(0, 3720))

    def test_refresh_after_time_origin_and_abort(self):
        gate = RefreshGate()
        self.assertTrue(gate.should_request(0, 0))
        gate.mark_requested(0)
        self.assertFalse(gate.should_request(0, 1))
        self.assertFalse(gate.should_request(0, 3600, abort=True))
        self.assertTrue(gate.should_request(0, 3600))

    def test_pending_refresh_has_bounded_unobserved_recovery(self):
        source = (ROOT/'addons/service.actweeter/service.py').read_text()
        tree = ast.parse(source)
        method = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                      and n.name == '_run_coordinator')
        code = ast.unparse(method)
        self.assertIn('now - pending_refresh[\'requested_at\'] >= 2 * refresh_gate.interval', code)
        self.assertIn("'requested_at': now", code)
        self.assertIn("pending_refresh = None", code)
