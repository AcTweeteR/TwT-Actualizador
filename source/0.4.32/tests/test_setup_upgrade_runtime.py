import ast
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


class SetupUpgradeRuntimeTests(unittest.TestCase):
    def finish(self, existing, result):
        path = ROOT / 'addons/service.actweeter/setup.py'
        node = next(n for n in ast.parse(path.read_text()).body
                    if isinstance(n, ast.FunctionDef) and n.name == '_finish_setup')
        state = {'legacy_completed_review': existing}
        write = Mock()
        env = {'_read_state': lambda: state, '_prepare_product_interface': Mock(return_value=result),
               '_evaluate_setup_gates': Mock(return_value=(state, {})),
               'completion_blockers': lambda value: (), '_write_state': write,
               'mark_completed': lambda value: value, 'xbmc': SimpleNamespace(),
               'ADDON': None, 'xbmcvfs': None}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), env)
        with patch.dict(sys.modules, {'addon_update_policy': SimpleNamespace(review=Mock())}):
            value = env['_finish_setup'](Mock())
        return value, write

    def test_existing_install_can_finish_with_interface_repair_pending(self):
        for result in ('BUILD_BUSY', 'CUSTOMIZATIONS_PRESERVED', 'GENERATED_XML_PROPERTY_MISSING'):
            with self.subTest(result=result):
                value, write = self.finish(True, result)
                self.assertTrue(value)
                write.assert_called_once()

    def test_new_install_still_requires_generated_interface(self):
        value, write = self.finish(False, 'BUILD_BUSY')
        self.assertFalse(value)
        write.assert_not_called()
