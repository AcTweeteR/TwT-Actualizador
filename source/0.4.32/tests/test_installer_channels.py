"""Execute the real installer functions with an isolated Kodi API double."""
import ast
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, call

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addons/service.actweeter/resources/lib"))
import first_run
import module_catalog


class InstallerChannelTests(unittest.TestCase):
    def setUp(self):
        self.installed = {}
        self.disabled = set()
        self.dialog = Mock()
        self.dialog.yesno.return_value = True
        self.calls = []
        self.kodi = Mock()
        self.ns = dict(
            xbmc=self.kodi, OPTIONAL_ADDONS=first_run.OPTIONAL_ADDONS,
            SETTINGS_ADDONS=first_run.OPTIONAL_ADDONS,
            OPTIONAL_ADDON_SOURCES=first_run.OPTIONAL_ADDON_SOURCES,
            SLYGUY_INSTALL_SEQUENCE=first_run.SLYGUY_INSTALL_SEQUENCE,
            REQUIRED_EXTERNAL_ADDON_MINIMUMS=first_run.REQUIRED_EXTERNAL_ADDON_MINIMUMS,
            repository_candidates=first_run.repository_candidates,
            optional_addon_action=first_run.optional_addon_action,
            addon_version_satisfies=first_run.addon_version_satisfies,
            all_addons=module_catalog.all_addons,
            _addon_installed=lambda name: name in self.installed,
            _addon_enabled=lambda name: name in self.installed and name not in self.disabled,
            _addon_ready=lambda name: name in self.installed and name not in self.disabled,
            _addon_version=lambda name: self.installed.get(name, ""),
            _is_tvos=lambda: False,
            _offer_automatic_previews=Mock(return_value="CURRENT"),
        )
        names = {"_install_slyguy_stack", "_slyguy_stack_ready", "_enabled_install_sources",
                 "_request_native_addon_install", "_ensure_repository_enabled", "_open_settings",
                 "_wait_for_installable_addon"}
        tree = ast.parse((ROOT / "addons/service.actweeter/setup.py").read_text())
        funcs = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
        exec(compile(ast.Module(body=funcs, type_ignores=[]), "setup.py", "exec"), self.ns)
        self.native_install = self.ns["_request_native_addon_install"]
        self.ns["_request_native_addon_install"] = self.install
        self.ns["_set_addon_enabled"] = self.enable

    def enable(self, name, enabled):
        self.disabled.discard(name)
        return True

    def install(self, dialog, name, source, **kwargs):
        self.calls.append((name, source, kwargs))
        self.installed[name] = kwargs.get("minimum_version") or "1.0.0"
        self.disabled.discard(name)
        return "INSTALLED"

    def test_stable_beta_and_both_can_bootstrap_complete_stack(self):
        for repos in (("repository.actweeter",), ("repository.actweeter.testing",),
                      ("repository.actweeter", "repository.actweeter.testing")):
            with self.subTest(repos=repos):
                self.setUp()
                self.installed.update(dict.fromkeys(repos, "1.0.3"))
                self.assertTrue(self.ns["_install_slyguy_stack"](self.dialog))
                self.assertEqual([x[0] for x in self.calls], [x[0] for x in first_run.SLYGUY_INSTALL_SEQUENCE])
                self.assertTrue(any(repo in self.calls[0][1] for repo in repos))
                self.assertTrue(all(not call[2]["required"] for call in self.calls))
                self.calls.clear()
                self.dialog.yesno.reset_mock()
                self.assertTrue(self.ns["_install_slyguy_stack"](self.dialog))
                self.assertEqual(self.calls, [])
                self.dialog.yesno.assert_not_called()

    def test_ready_stack_does_not_need_actweeter_repository(self):
        self.installed.update({name: minimum for name, minimum, _ in first_run.SLYGUY_INSTALL_SEQUENCE})
        self.assertTrue(self.ns["_install_slyguy_stack"](self.dialog))
        self.assertFalse(self.calls)
        self.ns["_offer_automatic_previews"].assert_called_once_with(self.dialog)

    def test_optional_bridge_failure_does_not_invalidate_installed_stack(self):
        self.installed.update({name: minimum for name, minimum, _ in first_run.SLYGUY_INSTALL_SEQUENCE})
        self.ns["_offer_automatic_previews"].return_value = "ERROR"
        self.assertTrue(self.ns["_install_slyguy_stack"](self.dialog))
        self.ns["_offer_automatic_previews"].assert_called_once_with(self.dialog)
        self.assertFalse(self.calls)

    def test_declining_optional_stack_changes_nothing(self):
        self.dialog.yesno.return_value = False
        self.assertFalse(self.ns["_install_slyguy_stack"](self.dialog))
        self.assertFalse(self.calls)
        self.assertEqual(self.installed, {})
        self.ns["_offer_automatic_previews"].assert_not_called()

    def test_partial_stack_repairs_only_missing_or_disabled_items(self):
        self.installed.update({name: minimum for name, minimum, _ in first_run.SLYGUY_INSTALL_SEQUENCE})
        self.disabled.add("slyguy.dependencies")
        del self.installed["slyguy.trailers"]
        self.assertTrue(self.ns["_install_slyguy_stack"](self.dialog))
        self.assertEqual([x[0] for x in self.calls], ["slyguy.dependencies", "slyguy.trailers"])

    def test_old_optional_version_is_not_mistaken_for_ready(self):
        self.installed.update({name: minimum for name, minimum, _ in first_run.SLYGUY_INSTALL_SEQUENCE})
        self.installed["script.module.slyguy"] = "0.1.0"
        self.assertTrue(self.ns["_install_slyguy_stack"](self.dialog))
        self.assertEqual([x[0] for x in self.calls], ["script.module.slyguy"])

    def test_disabled_beta_can_be_enabled_only_with_consent(self):
        self.installed["repository.actweeter.testing"] = "1.0.1"
        self.disabled.add("repository.actweeter.testing")
        self.dialog.yesno.return_value = False
        self.assertFalse(self.ns["_install_slyguy_stack"](self.dialog, consent_granted=True))
        self.assertFalse(self.calls)
        self.dialog.yesno.return_value = True
        self.assertTrue(self.ns["_install_slyguy_stack"](self.dialog, consent_granted=True))

    def test_missing_sources_fail_without_downloading_any_zip(self):
        self.assertFalse(self.ns["_install_slyguy_stack"](self.dialog))
        self.assertFalse(self.calls)
        self.kodi.executebuiltin.assert_not_called()

    def test_failed_upstream_transaction_remains_retryable(self):
        self.installed["repository.actweeter.testing"] = "1.0.1"
        self.ns["_request_native_addon_install"] = Mock(return_value="FAILED")
        self.assertFalse(self.ns["_install_slyguy_stack"](self.dialog))
        self.assertNotIn("slyguy.trailers", self.installed)
        self.ns["_request_native_addon_install"] = self.install
        self.assertTrue(self.ns["_install_slyguy_stack"](self.dialog))

    def test_xstream_settings_install_accepts_beta_without_stable(self):
        self.installed["repository.actweeter.testing"] = "1.0.1"
        self.ns["_open_settings"](self.dialog, "xstream")
        self.assertEqual(self.calls[0][0:2], ("plugin.video.xstream-pro", "repository.actweeter.testing"))

    def test_ready_native_addon_is_not_prompted_or_reinstalled(self):
        self.installed["slyguy.trailers"] = "0.2.1"
        self.assertEqual(self.native_install(self.dialog, "slyguy.trailers", "existing", minimum_version="0.2.1"), "INSTALLED")
        self.dialog.yesno.assert_not_called()
        self.kodi.executebuiltin.assert_not_called()

    def test_native_timeout_is_bounded_and_never_reports_success(self):
        self.ns["_wait_for_addon_ready"] = Mock(return_value=False)
        self.assertEqual(self.native_install(self.dialog, "slyguy.trailers", "Beta", consent_granted=True), "FAILED")
        self.assertEqual(self.ns["_wait_for_addon_ready"].call_count, 2)

    def test_rivulet_refreshes_and_waits_for_installable_catalog_before_install(self):
        self.ns["_wait_for_installable_addon"] = Mock(return_value=True)
        self.ns["_wait_for_addon_ready"] = Mock(return_value=True)
        self.assertEqual(self.native_install(
            self.dialog, "plugin.video.rivulet", "repository.rivulet",
            consent_granted=True, minimum_version="0.36.0"), "INSTALLED")
        self.assertEqual(self.kodi.executebuiltin.call_args_list, [
            call("UpdateAddonRepos", True),
            call("InstallAddon(plugin.video.rivulet)", True),
        ])
        self.ns["_wait_for_installable_addon"].assert_not_called()

    def test_rivulet_catalog_timeout_still_uses_native_resolver(self):
        self.ns["_wait_for_installable_addon"] = Mock(return_value=False)
        self.ns["_wait_for_addon_ready"] = Mock(return_value=True)
        self.assertEqual(self.native_install(
            self.dialog, "plugin.video.rivulet", "repository.rivulet",
            consent_granted=True, minimum_version="0.36.0"), "INSTALLED")
        self.assertEqual(self.kodi.executebuiltin.call_args_list, [
            call("UpdateAddonRepos", True),
            call("InstallAddon(plugin.video.rivulet)", True),
        ])
        self.ns["_wait_for_installable_addon"].assert_not_called()

    def test_rivulet_catalog_wait_uses_kodis_installable_addon_api(self):
        self.ns["_jsonrpc"] = Mock(return_value={"addons": [{
            "addonid": "plugin.video.rivulet", "version": "0.36.0",
            "installed": False,
        }]})
        self.assertTrue(self.ns["_wait_for_installable_addon"](
            "plugin.video.rivulet", "0.36.0"))
        self.ns["_jsonrpc"].assert_called_once_with("Addons.GetAddons", {
            "type": "unknown", "enabled": "all", "installed": False,
            "properties": ["addonid", "version", "installed"],
        })
        self.assertFalse(self.ns["_wait_for_installable_addon"](
            "plugin.video.rivulet", "0.36.0", timeout=0))

    def test_optional_inputstream_is_not_a_core_install_gate(self):
        for platform in module_catalog.ALL_TARGET_PLATFORMS:
            self.assertNotIn("inputstream.adaptive", {x["id"] for x in module_catalog.installation_plan(platform)})
        selected = module_catalog.installation_plan("tvos", selected_optional={"slyguy.trailers"})
        self.assertIn("inputstream.adaptive", {x["id"] for x in selected})

    def test_038_state_survives_repeated_normalization_and_interruption(self):
        state = first_run.mark_started({})
        state = first_run.mark_step(state, first_run.WIZARD_STEPS[2], "RETURNED")
        state["script_trakt_status"] = "AUTHORIZATION_UNVERIFIED"
        before = copy.deepcopy(state)
        for _ in range(3):
            state = first_run.normalize_state(state)
        self.assertEqual(state["step_status"], before["step_status"])
        self.assertEqual(state["script_trakt_status"], before["script_trakt_status"])
        self.assertFalse(state["completed"])
