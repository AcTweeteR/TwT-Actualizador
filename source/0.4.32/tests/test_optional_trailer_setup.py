from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "addons/service.actweeter/resources/lib"
sys.path.insert(0, str(LIB))

import first_run  # noqa: E402
import module_catalog  # noqa: E402


class OptionalTrailerSetupTests(unittest.TestCase):
    def test_trailers_are_not_a_core_setup_gate(self):
        self.assertNotIn("trailer_addon_ready", first_run.MANDATORY_SETUP_CHECKS)
        self.assertIn("trailer_addon_ready", first_run.OPTIONAL_SETUP_CHECKS)
        service = module_catalog.all_addons()["service.actweeter"]
        self.assertNotIn("slyguy.trailers", service["dependencies"])

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
