from __future__ import annotations

import sys
import unittest
import ast
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "addons/service.actweeter/resources/lib"
sys.path.insert(0, str(LIB))

import first_run  # noqa: E402
import module_catalog  # noqa: E402


class OptionalTrailerSetupTests(unittest.TestCase):
    def test_every_declared_addon_is_required_on_every_supported_platform(self):
        self.assertTrue(all(item["required"] for item in module_catalog.all_addons().values()))
        expected = set(module_catalog.all_addons()) - {"xbmc.gui"}
        for platform in module_catalog.ALL_TARGET_PLATFORMS:
            self.assertEqual({item["id"] for item in module_catalog.installation_plan(platform)}, expected)

    def test_slyguy_manifest_bootstraps_before_native_dependency_resolution(self):
        manifest = ROOT / "addons/service.actweeter/addon.xml"
        tree = ET.parse(manifest)
        imports = {
            node.get("addon"): node
            for node in tree.findall("./requires/import")
        }

        self.assertIn("slyguy.trailers", imports)
        self.assertEqual(imports["slyguy.trailers"].get("optional"), "true")
        self.assertIn("slyguy.trailers", {
            addon_id for addon_id, item in module_catalog.all_addons().items()
            if item.get("required", True)
        })
        self.assertIsNone(imports["script.trakt"].get("optional"))

    def test_new_required_addon_reopens_component_offer_for_existing_profile(self):
        state = {
            "completed": True,
            "prompted": True,
            "component_catalog_offer_version": module_catalog.CATALOG_VERSION - 1,
        }
        self.assertTrue(first_run.should_offer_component_completion(
            state, ["script.trakt"], core_configured=True))
        state = first_run.mark_component_offer_seen(state)
        self.assertFalse(first_run.should_offer_component_completion(
            state, ["script.trakt"], core_configured=True))

    def test_trailers_and_trakt_are_installation_gates_but_account_authorization_is_separate(self):
        self.assertNotIn("trailer_addon_ready", first_run.MANDATORY_SETUP_CHECKS)
        self.assertIn("trailer_addon_ready", first_run.OPTIONAL_SETUP_CHECKS)
        self.assertEqual(first_run.REQUIRED_EXTERNAL_ADDON_MINIMUMS["slyguy.trailers"], "0.2.1")
        self.assertEqual(first_run.REQUIRED_EXTERNAL_ADDON_MINIMUMS["script.trakt"], "3.9.0")
        self.assertIn("script_trakt_authorization", first_run.OPTIONAL_SETUP_CHECKS)
        service = module_catalog.all_addons()["service.actweeter"]
        self.assertNotIn("slyguy.trailers", service["dependencies"])

    def test_missing_slyguy_and_trakt_are_reported_as_required_in_service_status(self):
        rows = first_run.service_rows({"required": True, "slyguy": False})
        by_name = {row["service"]: row for row in rows}

        for name in ("SlyGuy Trailers", "Previews automáticos", "Trakt"):
            self.assertFalse(by_name[name]["optional"])
            self.assertEqual(by_name[name]["status"], "MISSING")

    def test_installed_slyguy_is_not_reported_as_runtime_validated(self):
        rows = first_run.service_rows({"required": True, "slyguy": True})
        by_name = {row["service"]: row for row in rows}

        self.assertEqual(by_name["SlyGuy Trailers"]["status"], "INSTALLED_NOT_CHECKED")
        self.assertEqual(by_name["Previews automáticos"]["status"], "INTEGRATION_NOT_CHECKED_NOW")

    def test_legacy_master_completion_is_preserved_without_fake_runtime_pass(self):
        old = {"schema_version": 1, "wizard_version": 4,
               "completed": True, "prompted": True,
               "setup_state": "COMPLETE"}
        state = first_run.normalize_state(old)
        self.assertFalse(state["completed"])
        self.assertEqual(state["setup_state"], "INCOMPLETE")
        self.assertTrue(state["legacy_completed_review"])
        self.assertFalse(first_run.should_offer_first_run(state, core_configured=True))
        self.assertTrue(first_run.should_offer_first_run(state, core_configured=False))
        self.assertTrue(first_run.should_offer_first_run(
            first_run.normalize_state(old | {"completed": False, "prompted": False}),
            core_configured=True))

    def test_explicit_decline_persists_for_configured_profile_only(self):
        state = {"schema_version": 1, "wizard_version": 8,
                 "completed": False, "setup_state": "VERIFYING",
                 "setup_checks": {"mandatory_addons": "FAIL"}}
        self.assertTrue(first_run.should_offer_first_run(state, True))
        saved = first_run.normalize_state(first_run.mark_deferred(
            state, 12345, core_configured=True))
        self.assertTrue(saved["configured_onboarding_declined"])
        self.assertFalse(saved["completed"])
        self.assertEqual(saved["setup_checks"]["mandatory_addons"], "FAIL")
        self.assertFalse(first_run.should_offer_first_run(saved, True))
        self.assertFalse(first_run.should_offer_first_run_in_process(
            saved, True, 67890))
        self.assertTrue(first_run.should_offer_first_run(saved, False))
        reset = first_run.mark_started(saved)
        self.assertNotIn("configured_onboarding_declined", reset)
        self.assertTrue(first_run.should_offer_first_run(reset, True))

    def test_unconfigured_profile_is_reoffered_and_malformed_state_rejected(self):
        state = first_run.mark_deferred(
            {"schema_version": 1}, 12345, core_configured=False)
        self.assertNotIn("configured_onboarding_declined", state)
        self.assertFalse(first_run.should_offer_first_run_in_process(state, False, 12345))
        self.assertTrue(first_run.should_offer_first_run_in_process(state, False, 67890))
        bad = first_run.normalize_state({
            "schema_version": 1,
            "configured_onboarding_declined": "true"})
        self.assertNotIn("configured_onboarding_declined", bad)

    def test_runtime_gate_does_not_readiness_gate_optional_addons(self):
        setup_path = ROOT / "addons/service.actweeter/setup.py"
        tree = ast.parse(setup_path.read_text(encoding="utf-8"))
        function = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef)
                        and node.name == "_mandatory_addons_ready")
        referenced_names = {node.id for node in ast.walk(function)
                            if isinstance(node, ast.Name)}
        self.assertNotIn("OPTIONAL_ADDONS", referenced_names)
        self.assertIn("installation_plan", referenced_names)
        self.assertIn("_installed_dependency_graph", referenced_names)

    def test_trailer_stack_requires_consent_and_is_in_default_install_plan(self):
        entries = module_catalog.all_addons()
        trailer_ids = {
            "repository.slyguy", "slyguy.dependencies",
            "script.module.slyguy", "slyguy.trailers",
        }
        for addon_id in trailer_ids:
            self.assertTrue(entries[addon_id]["required"], addon_id)
            self.assertTrue(entries[addon_id]["consent_required"], addon_id)

        default_plan = module_catalog.installation_plan("macos")
        default_ids = {entry["id"] for entry in default_plan}
        self.assertTrue(trailer_ids.issubset(default_ids))
        self.assertIn("script.trakt", default_ids)
        self.assertIn("inputstream.adaptive", default_ids)

    def test_core_setup_can_complete_after_addon_install_when_trailer_runtime_check_is_pending(self):
        state = {}
        for key in first_run.MANDATORY_SETUP_CHECKS:
            state = first_run.mark_setup_check(state, key, "PASS_RUNTIME")
        state = first_run.mark_setup_check(state, "trailer_addon_ready", "NOT_TESTED")

        self.assertEqual(first_run.completion_blockers(state), ())
        completed = first_run.mark_completed(state)
        self.assertTrue(completed["completed"])
        self.assertEqual(completed["setup_state"], "COMPLETE")

    def test_core_setup_still_blocks_without_runtime_provider_or_pvr_evidence(self):
        state = {}
        for key in first_run.MANDATORY_SETUP_CHECKS:
            status = "FAIL" if key == "pvr_configuration" else "PASS_RUNTIME"
            state = first_run.mark_setup_check(state, key, status)
        self.assertIn("pvr_configuration", first_run.completion_blockers(state))
        self.assertFalse(first_run.mark_completed(state)["completed"])


if __name__ == "__main__":
    unittest.main()
