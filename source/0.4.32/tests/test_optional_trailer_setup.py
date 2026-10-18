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
    def test_slyguy_trailers_manifest_dependency_is_optional(self):
        manifest = ROOT / "addons/service.actweeter/addon.xml"
        tree = ET.parse(manifest)
        imports = {
            node.get("addon"): node
            for node in tree.findall("./requires/import")
        }

        self.assertIn("slyguy.trailers", imports)
        self.assertEqual(imports["slyguy.trailers"].get("optional"), "true")
        self.assertNotIn("slyguy.trailers", {
            addon_id for addon_id, item in module_catalog.all_addons().items()
            if item.get("required", True)
        })

    def test_trailers_are_not_a_core_setup_gate(self):
        self.assertNotIn("trailer_addon_ready", first_run.MANDATORY_SETUP_CHECKS)
        self.assertIn("trailer_addon_ready", first_run.OPTIONAL_SETUP_CHECKS)
        self.assertNotIn("slyguy.trailers", first_run.REQUIRED_EXTERNAL_ADDON_MINIMUMS)
        service = module_catalog.all_addons()["service.actweeter"]
        self.assertNotIn("slyguy.trailers", service["dependencies"])

    def test_missing_slyguy_is_reported_as_optional_in_service_status(self):
        rows = first_run.service_rows({"required": True, "slyguy": False})
        by_name = {row["service"]: row for row in rows}

        self.assertTrue(by_name["SlyGuy Trailers"]["optional"])
        self.assertEqual(by_name["SlyGuy Trailers"]["status"], "OPTIONAL_MISSING")
        self.assertTrue(by_name["Previews automáticos"]["optional"])
        self.assertEqual(by_name["Previews automáticos"]["status"], "OPTIONAL_MISSING")

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

    def test_trailer_stack_requires_consent_and_is_not_in_default_install_plan(self):
        entries = module_catalog.all_addons()
        trailer_ids = {
            "repository.slyguy", "slyguy.dependencies",
            "script.module.slyguy", "slyguy.trailers",
        }
        for addon_id in trailer_ids:
            self.assertFalse(entries[addon_id]["required"], addon_id)
            self.assertTrue(entries[addon_id]["consent_required"], addon_id)

        default_plan = module_catalog.installation_plan("macos")
        default_ids = {entry["id"] for entry in default_plan}
        self.assertFalse(trailer_ids.intersection(default_ids))

        consented_plan = module_catalog.installation_plan(
            "macos", selected_optional=trailer_ids)
        consented_ids = {entry["id"] for entry in consented_plan}
        self.assertTrue(trailer_ids.issubset(consented_ids))

    def test_core_setup_can_complete_when_optional_trailer_check_is_pending(self):
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
