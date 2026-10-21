import ast
from contextlib import closing
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "addons/service.actweeter/resources/lib"
sys.path.insert(0, str(LIB))
import addon_update_policy as policy


class Kodi:
    def __init__(self, mode=1, repo_mode=0, reject=False, readback_failure=False):
        self.settings = {"general.addonupdates": mode, "addons.updatemode": repo_mode}
        self.calls = []
        self.reject, self.readback_failure = reject, readback_failure
        self.versions = {identity: "1.0" for identity in policy.COMPONENTS}
        self.disabled = set()

    def executeJSONRPC(self, raw):
        call = json.loads(raw)
        self.calls.append(call)
        params, method = call["params"], call["method"]
        if method == "Settings.GetSettingValue":
            result = {"value": self.settings[params["setting"]]}
        elif method == "Settings.SetSettingValue":
            assert params["setting"] == "general.addonupdates", "must not change repository policy"
            result = not self.reject
            if result and not self.readback_failure:
                self.settings[params["setting"]] = params["value"]
        elif method == "Addons.GetAddonDetails":
            identity = params["addonid"]
            result = {"addon": {"enabled": identity not in self.disabled,
                                "version": self.versions.get(identity, "1.0")}}
        else:
            raise AssertionError(method)
        return json.dumps({"result": result})


class UpdatePolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.database = self.path / "Addons33.db"
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("CREATE TABLE installed(addonID TEXT, origin TEXT)")
            connection.execute("CREATE TABLE update_rules(addonID TEXT, updateRule INT)")
            connection.executemany("INSERT INTO installed VALUES (?,?)",
                                  [(identity, "repository.actweeter.testing") for identity in policy.COMPONENTS])
        self.vfs = Mock()
        self.vfs.translatePath.side_effect = lambda value: str(self.path) if value == "special://database" else value
        self.vfs.listdir.return_value = ([], ["Addons33.db"])
        self.vfs.File.side_effect = lambda value: io.StringIO(
            '<settings><setting id="general.addonupdates">0</setting></settings>')
        self.addon = Mock()
        self.addon.getAddonInfo.return_value = str(self.path)
        self.dialog = Mock()
        self.dialog.yesno.return_value = False
        self.dialog.select.return_value = -1

    def configure(self, kodi):
        return policy.configure(kodi, self.addon, self.vfs, self.dialog)

    def writes(self, kodi):
        return [c for c in kodi.calls if c["method"] == "Settings.SetSettingValue"]

    def test_consent_sets_correct_setting_and_preserves_official_only(self):
        self.dialog.yesno.return_value = True
        kodi = Kodi()
        report = self.configure(kodi)
        self.assertEqual(report["problems"], [])
        self.assertEqual([c["params"] for c in self.writes(kodi)],
                         [{"setting": "general.addonupdates", "value": 0}])
        self.assertEqual(kodi.settings["addons.updatemode"], 0)
        self.assertIn("otros addons", self.dialog.yesno.call_args.args[1])

    def test_decline_preserves_preferences(self):
        kodi = Kodi(mode=2, repo_mode=1)
        self.assertTrue(self.configure(kodi)["problems"])
        self.assertEqual(self.writes(kodi), [])
        self.assertEqual(kodi.settings, {"general.addonupdates": 2, "addons.updatemode": 1})

    def test_already_enabled_is_idempotent(self):
        kodi = Kodi(mode=0)
        self.configure(kodi)
        self.configure(kodi)
        self.dialog.yesno.assert_not_called()
        self.assertEqual(self.writes(kodi), [])

    def test_failed_set_and_false_readback_do_not_claim_success(self):
        self.dialog.yesno.return_value = True
        for options in ({"reject": True}, {"readback_failure": True}):
            with self.subTest(options=options):
                report = self.configure(Kodi(**options))
                self.assertNotEqual(report["settings"][policy.AUTO_SETTING], 0)
                self.assertTrue(report["problems"])

    def test_persistence_is_separate_from_runtime_value(self):
        self.vfs.File.side_effect = lambda value: io.StringIO(
            '<settings><setting id="general.addonupdates">1</setting></settings>')
        report = self.configure(Kodi(mode=0))
        self.assertTrue(any("disco pendiente" in text for text in report["problems"]))

    def test_five_unchanged_startups_warn_only_once_and_never_write_settings(self):
        kodi = Kodi()
        for _ in range(5):
            policy.review(kodi, self.addon, self.vfs, self.dialog)
        self.assertEqual(self.dialog.notification.call_count, 1)
        self.assertEqual(self.writes(kodi), [])
        self.dialog.yesno.assert_not_called()

    def test_important_update_and_disabled_preference_are_reviewed(self):
        kodi = Kodi(mode=0)
        policy.review(kodi, self.addon, self.vfs, self.dialog)
        self.dialog.notification.assert_not_called()
        kodi.settings[policy.AUTO_SETTING] = 2
        policy.review(kodi, self.addon, self.vfs, self.dialog)
        self.assertEqual(self.dialog.notification.call_count, 1)
        kodi.versions["skin.actweeter"] = "2.0"
        policy.review(kodi, self.addon, self.vfs, self.dialog)
        self.assertEqual(self.dialog.notification.call_count, 2)

    def test_stable_and_testing_origins_work_with_either_repo_preference(self):
        for origin in policy.CHANNELS:
            with closing(sqlite3.connect(self.database)) as connection, connection:
                connection.execute("UPDATE installed SET origin=?", (origin,))
            for repo_mode in (0, 1):
                report = policy.snapshot(Kodi(mode=0, repo_mode=repo_mode), self.vfs)
                self.assertEqual(report["expected"], origin)
                self.assertEqual(report["problems"], [])

    def test_missing_mixed_origins_and_individual_blocks_are_reported_readonly(self):
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("UPDATE installed SET origin='' WHERE addonID='service.actweeter'")
            connection.execute("UPDATE installed SET origin='repository.actweeter' WHERE addonID='skin.actweeter'")
            connection.execute("INSERT INTO update_rules VALUES ('plugin.video.xstream-pro',1)")
        before = self.database.read_bytes()
        report = policy.snapshot(Kodi(mode=0), self.vfs, "repository.actweeter.testing")
        self.assertTrue(any("origen no verificable" in line for line in report["problems"]))
        self.assertTrue(any("origen distinto" in line for line in report["problems"]))
        self.assertTrue(any("individual bloqueada" in line for line in report["problems"]))
        self.assertEqual(before, self.database.read_bytes())

    def test_selected_channel_is_retained_not_silently_switched(self):
        self.configure(Kodi(mode=0))
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("UPDATE installed SET origin='repository.actweeter'")
        report = policy.review(Kodi(mode=0), self.addon, self.vfs, self.dialog)
        self.assertEqual(report["expected"], "repository.actweeter.testing")
        self.assertTrue(any("origen distinto" in line for line in report["problems"]))

    def test_unavailable_database_or_api_is_not_a_verified_origin(self):
        self.vfs.listdir.return_value = ([], [])
        kodi = Kodi(mode=0)
        kodi.executeJSONRPC = lambda raw: json.dumps({"error": {"code": -32601}})
        report = self.configure(kodi)
        self.assertTrue(report["problems"])
        self.assertEqual(report["installed"], {})
        self.assertIsNone(report["settings"][policy.AUTO_SETTING])

    def test_explicit_channel_choice_records_intent_without_rebinding_addons(self):
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("UPDATE installed SET origin=''")
        before = self.database.read_bytes()
        self.dialog.select.return_value = 0
        report = self.configure(Kodi(mode=0))
        self.assertEqual(report["expected"], "repository.actweeter.testing")
        self.assertEqual(before, self.database.read_bytes())
        self.assertTrue(report["problems"])

    def test_database_selection_is_numeric_and_uses_files_not_directories(self):
        self.vfs.listdir.return_value = (["Addons999.db"], ["Addons9.db", "Addons33.db"])
        self.assertEqual(len(policy.installation_state(self.vfs)), 3)

    def test_state_write_failure_does_not_abort_onboarding_or_claim_success(self):
        with patch.object(policy, "atomic_write", side_effect=OSError):
            report = self.configure(Kodi(mode=0))
        self.assertTrue(any("guardar la revisión" in line for line in report["problems"]))
        self.dialog.textviewer.assert_called_once()

    def test_disabled_repository_and_addon_are_not_success(self):
        kodi = Kodi(mode=0)
        kodi.disabled = {"repository.actweeter.testing", "skin.actweeter"}
        report = policy.snapshot(kodi, self.vfs)
        self.assertTrue(any("Repositorio Testing" in line for line in report["problems"]))
        self.assertTrue(any("skin.actweeter: ausente" in line for line in report["problems"]))

    def test_onboarding_maintenance_and_service_are_wired(self):
        setup = ast.parse((ROOT / "addons/service.actweeter/setup.py").read_text())
        onboarding = next(n for n in setup.body if isinstance(n, ast.FunctionDef) and n.name == "_run_onboarding")
        self.assertTrue(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                            and n.func.id == "configure_updates" for n in ast.walk(onboarding)))
        source = (ROOT / "addons/service.actweeter/setup.py").read_text()
        self.assertIn('"Actualizaciones y canal"', source)
        self.assertIn('action == "updates"', source)
        finish = next(n for n in setup.body if isinstance(n, ast.FunctionDef) and n.name == "_finish_setup")
        self.assertTrue(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                            and n.func.id == "review_updates" for n in ast.walk(finish)))
        self.assertIn('review_updates(kodi, ADDON, vfs, xbmcgui.Dialog())',
                      (ROOT / "addons/service.actweeter/service.py").read_text())


if __name__ == "__main__":
    unittest.main()
