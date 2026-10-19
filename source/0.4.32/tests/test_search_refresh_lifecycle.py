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
from search_background import RefreshGate, last_successful_sync, refresh_due, xstream_profile_number, plugin_refresh_url


class RefreshLifecycleTests(unittest.TestCase):
    def test_active_profile_validation_prevents_cross_profile_refresh(self):
        self.assertEqual(xstream_profile_number('Profile 1'),1)
        self.assertEqual(xstream_profile_number('Profile 10'),10)
        self.assertEqual(xstream_profile_number('profile 2'),2)
        self.assertEqual(xstream_profile_number(''),1)
        for value in ('Profile 0','Profile 11','Profile 999','Profile 2 extra',
                      'other 2','Profile -1','Profile １', '2', 2, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                xstream_profile_number(value)
        self.assertIn('profile_num=10',plugin_refresh_url(10))
        for value in (True, '1', 1.0, 0, 11):
            with self.subTest(url_value=value), self.assertRaises(ValueError):
                plugin_refresh_url(value)

    def test_sync_reader_rejects_invalid_profile_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            for value in (0, 11, -1, True, '1', 1.5):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    last_successful_sync(tmp,value)

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

    def test_future_provider_timestamp_recovers_from_clock_skew(self):
        self.assertFalse(refresh_due(1250, 1000))
        self.assertTrue(refresh_due(1400, 1000))
        self.assertFalse(refresh_due(1000, 1200))
        self.assertTrue(refresh_due(1000, 4600))

    def test_refresh_gate_recovers_from_large_clock_rollback(self):
        gate = RefreshGate()
        gate.mark_requested(10000)
        self.assertFalse(gate.should_request(0, 9800))
        self.assertTrue(gate.should_request(0, 9000))
        self.assertFalse(gate.should_request(0, 9000, abort=True))

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
