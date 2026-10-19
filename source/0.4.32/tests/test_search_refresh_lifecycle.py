"""Provider-only background refresh scheduling and pending lifecycle contracts."""
import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'addons/service.actweeter/resources/lib'))
from search_background import RefreshGate


class RefreshLifecycleTests(unittest.TestCase):
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
