import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/service.actweeter/resources/lib'))
import trakt_integration as trakt


class TraktOnboardingResumeTests(unittest.TestCase):
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
