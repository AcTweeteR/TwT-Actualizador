import sys
import unittest
import ast
from types import SimpleNamespace
from unittest.mock import Mock, patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/service.actweeter/resources/lib'))
import trakt_integration as trakt


class TraktOnboardingResumeTests(unittest.TestCase):
    def test_resumed_wizard_skips_reviewed_script_but_offers_fresh_xstream(self):
        setup = Path(__file__).resolve().parents[1] / 'addons/service.actweeter/setup.py'
        node = next(n for n in ast.parse(setup.read_text()).body
                    if isinstance(n, ast.FunctionDef) and n.name == '_run_onboarding')
        state = {'script_trakt_status': 'AUTHORIZATION_UNVERIFIED'}
        script, xstream = Mock(), Mock()
        env = {
            '_read_state': lambda: state, '_write_state': lambda value: None,
            'mark_started': lambda value: value,
            'mark_step': lambda value, *args: value,
            '_offer_optional_tmdb': Mock(), '_complete_missing_components': lambda *a, **kw: True,
            '_configure_xstream_provider': lambda *a: True,
            '_setup_progress': lambda *a: __import__('contextlib').nullcontext(),
            '_install_slyguy_stack': Mock(), '_connect_trakt': script,
            '_connect_xstream_trakt': xstream,
            'should_offer_authorization': trakt.should_offer_authorization,
            '_verify_connected_services': lambda *a: True,
            'xbmc': SimpleNamespace(Monitor=lambda: SimpleNamespace(abortRequested=lambda: False)),
            'ADDON': None, 'xbmcvfs': None,
        }
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(setup), 'exec'), env)
        with patch.dict(sys.modules, {'addon_update_policy': SimpleNamespace(configure=Mock())}):
            self.assertTrue(env['_run_onboarding'](Mock(yesno=Mock(return_value=True))))
        script.assert_not_called()
        xstream.assert_called_once()

    def test_reviewed_authorizations_are_not_reoffered(self):
        for integration in ('script', 'xstream'):
            for status in ('DEFERRED', 'AUTHORIZATION_UNVERIFIED', 'AUTHORIZED_RUNTIME', 'AUTHORIZED_LOCAL'):
                with self.subTest(integration=integration, status=status):
                    self.assertFalse(trakt.should_offer_authorization(
                        {integration + '_trakt_status': status}, integration))

    def test_fresh_and_failed_authorizations_can_be_offered(self):
        self.assertTrue(trakt.should_offer_authorization({}, 'script'))
        self.assertTrue(trakt.should_offer_authorization(
            {'script_trakt_status': 'FAILED_RECOVERABLE'}, 'script'))

    def test_decisions_are_independent_and_do_not_mutate_state(self):
        state = {'script_trakt_status': 'DEFERRED'}
        self.assertTrue(trakt.should_offer_authorization(state, 'xstream'))
        self.assertEqual(state, {'script_trakt_status': 'DEFERRED'})
