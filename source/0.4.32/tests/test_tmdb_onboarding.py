import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addons/service.actweeter/resources/lib"))
import tmdb_onboarding as tmdb
import first_run


class TMDbOnboardingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.addon = Mock()
        self.settings = {tmdb.SETTING: ""}
        self.addon.getSetting.side_effect = lambda name: self.settings.get(name, "")
        self.addon.setSetting.side_effect = lambda name, value: self.settings.__setitem__(name, value)
        self.addon.getAddonInfo.return_value = self.directory.name
        self.vfs = Mock()
        self.vfs.translatePath.return_value = self.directory.name
        self.dialog = Mock()
        self.dialog.yesno.return_value = True
        self.dialog.input.return_value = "a" * 32

    def test_key_validator_and_offline_rejection(self):
        for value in ("", None, "x" * 32, "a" * 31, "a" * 33, "a" * 31 + "\n"):
            self.assertFalse(tmdb.valid_key(value))
            self.assertFalse(tmdb.check_key(value, requester=lambda url: True))
        self.assertTrue(tmdb.valid_key("a" * 32))
        self.assertFalse(tmdb.check_key("a" * 32, requester=lambda url: (_ for _ in ()).throw(OSError())))

    def test_verification_and_storage_only_after_success(self):
        checked = []
        result = tmdb.configure(self.addon, self.vfs, self.dialog,
                                requester=lambda url: checked.append(url) or True)
        self.assertEqual(result, "CONFIGURED")
        self.assertEqual(self.settings[tmdb.SETTING], "a" * 32)
        self.assertEqual(len(checked), 1)
        self.assertIn('api_key=', checked[0])
        self.addon.setSetting.assert_called_once()

    def test_invalid_or_unreachable_preserve_prior_key(self):
        self.settings[tmdb.SETTING] = "b" * 32
        self.dialog.input.return_value = "invalid"
        self.assertEqual(tmdb.configure(self.addon, self.vfs, self.dialog), "INVALID")
        self.assertEqual(self.settings[tmdb.SETTING], "b" * 32)
        self.dialog.input.return_value = "a" * 32
        self.assertEqual(tmdb.configure(self.addon, self.vfs, self.dialog, requester=lambda url: False), "UNVERIFIED")
        self.assertEqual(self.settings[tmdb.SETTING], "b" * 32)
        self.addon.setSetting.assert_not_called()

    def test_skip_only_once_and_no_secret_in_marker(self):
        self.dialog.yesno.return_value = False
        self.assertEqual(tmdb.offer_once(self.addon, self.vfs, self.dialog), "SKIPPED")
        self.assertEqual(tmdb.offer_once(self.addon, self.vfs, self.dialog), "ALREADY_OFFERED")
        self.assertEqual(self.dialog.yesno.call_count, 1)
        value = Path(self.directory.name, 'tmdb_onboarding.json').read_text()
        self.assertEqual(json.loads(value)['version'], tmdb.VERSION)
        self.assertNotIn('a' * 32, value)

    def test_skipping_tmdb_does_not_complete_or_defer_the_core_wizard(self):
        main_state = first_run.mark_started({})
        main_path = Path(self.directory.name, "setup_state.json")
        first_run.save_state(main_path, main_state)
        self.dialog.yesno.return_value = False
        self.assertEqual(tmdb.offer_once(self.addon, self.vfs, self.dialog), "SKIPPED")
        resumed = first_run.load_state(main_path)
        self.assertFalse(resumed["completed"])
        self.assertEqual(resumed["setup_state"], "INSTALLING_ADDONS")
        self.assertTrue(first_run.should_offer_first_run(resumed, core_configured=False))

    def test_legacy_prompted_marker_never_means_incomplete_core_setup_is_complete(self):
        state = first_run.normalize_state({"prompted": True, "completed": False,
                                           "setup_state": "INCOMPLETE"})
        self.assertFalse(state.get("completed", False))
        self.assertTrue(first_run.should_offer_first_run(state, core_configured=True))

    def test_interrupted_tmdb_prompt_retries_after_kodi_process_changes_only(self):
        self.dialog.yesno.side_effect = [RuntimeError("dialog interrupted"), False]
        with mock.patch.object(tmdb.os, "getpid", side_effect=[100, 100, 200]):
            self.assertEqual(tmdb.offer_once(self.addon, self.vfs, self.dialog),
                             "FAILED_RECOVERABLE")
            self.assertEqual(tmdb.offer_once(self.addon, self.vfs, self.dialog),
                             "ALREADY_OFFERED")
            self.assertEqual(tmdb.offer_once(self.addon, self.vfs, self.dialog), "SKIPPED")
        self.assertEqual(self.dialog.yesno.call_count, 2)

    def test_setup_isolates_optional_tmdb_and_continues_with_required_steps(self):
        setup = (ROOT / "addons/service.actweeter/setup.py").read_text()
        helper = setup.index("def _offer_optional_tmdb(dialog):")
        first_run = setup.index("def _run_onboarding(dialog")
        body = setup[helper:first_run]
        self.assertIn('outcome = "FAILED_RECOVERABLE"', body)
        self.assertLess(setup.index("_offer_optional_tmdb(dialog)", first_run),
                        setup.index("_complete_missing_components(dialog", first_run))
        self.assertIn("offer_once", body)

    def test_existing_key_keeps_settings_and_does_not_offer(self):
        self.settings[tmdb.SETTING] = "b" * 32
        self.assertEqual(tmdb.offer_once(self.addon, self.vfs, self.dialog), "CONFIGURED")
        self.dialog.yesno.assert_not_called()

    def test_setup_routes_offer_and_maintenance(self):
        setup = (ROOT / 'addons/service.actweeter/setup.py').read_text()
        self.assertIn('offer_tmdb(ADDON, xbmcvfs, dialog)', setup)
        self.assertIn('"Configurar TMDb (opcional)"', setup)
        self.assertIn('elif action == "tmdb":', setup)
        self.assertIn('elif action == "tmdb_offer":', setup)


if __name__ == '__main__':
    unittest.main()
