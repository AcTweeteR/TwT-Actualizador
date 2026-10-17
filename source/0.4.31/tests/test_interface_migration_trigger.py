import sys
import unittest
import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addons/service.actweeter/resources/lib"))
import interface_layout  # noqa: E402


class InterfaceMigrationTriggerTests(unittest.TestCase):
    def test_previous_verified_layout_still_requires_update_migration(self):
        state = {
            "layout_version": interface_layout.LAYOUT_VERSION - 1,
            "build_status": "GENERATED",
            "migration_history": [{
                "id": "interface-layout-v9-expandable-widget-metadata",
                "status": "VERIFIED",
            }],
        }
        self.assertTrue(interface_layout.interface_migration_due(state))

    def test_current_layout_requires_verified_native_build(self):
        pending = {
            "layout_version": interface_layout.LAYOUT_VERSION,
            "build_status": "PENDING",
            "migration_history": [{
                "id": interface_layout.LAYOUT_MIGRATION_ID,
                "status": "APPLIED_PENDING_BUILD",
            }],
        }
        self.assertTrue(interface_layout.interface_migration_due(pending))

        verified = {
            "layout_version": interface_layout.LAYOUT_VERSION,
            "build_status": "GENERATED",
            "migration_history": [{
                "id": interface_layout.LAYOUT_MIGRATION_ID,
                "status": "VERIFIED",
            }],
        }
        self.assertFalse(interface_layout.interface_migration_due(verified))

    def test_absent_or_malformed_layout_state_fails_toward_repair(self):
        self.assertTrue(interface_layout.interface_migration_due({}))
        self.assertTrue(interface_layout.interface_migration_due({
            "layout_version": "not-a-version",
            "migration_history": "invalid",
        }))

    def test_session_claimed_wizard_still_runs_independent_layout_migration(self):
        source = (ROOT / "addons/service.actweeter/setup.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        main = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == "main")
        branch = next(node for node in ast.walk(main)
                      if isinstance(node, ast.If)
                      and "claim_process_session" in ast.unparse(node.test)
                      and "not" in ast.unparse(node.test))
        branch_source = ast.unparse(branch)
        self.assertIn("_run_pending_interface_migration(dialog)", branch_source)

    def test_explicit_repair_bypasses_migration_version_gate(self):
        source = (ROOT / "addons/service.actweeter/setup.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        helper = next(node for node in tree.body
                      if isinstance(node, ast.FunctionDef)
                      and node.name == "_run_pending_interface_migration")
        branch_source = ast.unparse(helper)
        self.assertIn("if explicit", branch_source)
        self.assertIn("_prepare_product_interface(dialog, allow_prompt=True)", branch_source)


if __name__ == "__main__":
    unittest.main()
