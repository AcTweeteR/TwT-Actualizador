import sys
import tempfile
import unittest
import ast
from unittest import mock
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

    def test_preparation_busy_retries_then_confirms_success(self):
        results = iter(("PREPARATION_BUSY", "BUILD_BUSY", "GENERATED"))
        waits = []
        attempts = []
        result, count = interface_layout.retry_interface_preparation(
            lambda: next(results), lambda delay: waits.append(delay) or False,
            on_attempt=lambda attempt, maximum: attempts.append((attempt, maximum)))
        self.assertEqual((result, count), ("GENERATED", 3))
        self.assertEqual(waits, [1.0, 2.0])
        self.assertEqual(attempts, [(1, 6), (2, 6), (3, 6)])

    def test_preparation_busy_retry_is_bounded_and_not_marked_complete(self):
        attempts = []
        result, count = interface_layout.retry_interface_preparation(
            lambda: "PREPARATION_BUSY", lambda _delay: False,
            on_attempt=lambda attempt, _maximum: attempts.append(attempt))
        self.assertEqual((result, count), ("PREPARATION_BUSY", 6))
        self.assertEqual(attempts, [1, 2, 3, 4, 5, 6])
        self.assertIn("PREPARATION_BUSY", interface_layout.RETRYABLE_INTERFACE_RESULTS)

    def test_skinshortcuts_build_requires_observed_run_and_completion(self):
        class FakeWindow:
            def __init__(self, states):
                self.states = iter(states)

            def getProperty(self, _name):
                return next(self.states)

        class FakeKodi:
            LOGINFO = 1
            LOGWARNING = 2

            def __init__(self):
                self.commands = []
                self.logs = []

            def executebuiltin(self, command, _wait):
                self.commands.append(command)

            def log(self, message, _level):
                self.logs.append(message)

        class FakeMonitor:
            def __init__(self, clock):
                self.clock = clock

            def abortRequested(self):
                return False

            def waitForAbort(self, delay):
                self.clock.now += delay
                return False

        class Clock:
            now = 0.0

            def monotonic(self):
                return self.now

        clock = Clock()
        kodi = FakeKodi()
        window = FakeWindow(("False", "True", "False"))
        with mock.patch.object(interface_layout.time, "monotonic", clock.monotonic):
            result = interface_layout.request_skinshortcuts_build(
                kodi, window, FakeMonitor(clock), Path("missing-includes.xml"),
                timeout=1.0, start_timeout=0.5, poll_interval=0.05)
        self.assertEqual(result, "BUILD_FINISHED")
        self.assertEqual(len(kodi.commands), 1)

        with tempfile.TemporaryDirectory() as temp:
            generated = Path(temp) / "includes.xml"
            generated.write_text("old", encoding="utf-8")

            class WritingKodi(FakeKodi):
                def executebuiltin(self, command, wait):
                    super().executebuiltin(command, wait)
                    generated.write_text("new", encoding="utf-8")

            clock = Clock()
            kodi = WritingKodi()
            window = FakeWindow(("False", "False"))
            with mock.patch.object(interface_layout.time, "monotonic", clock.monotonic):
                result = interface_layout.request_skinshortcuts_build(
                    kodi, window, FakeMonitor(clock), generated,
                    timeout=1.0, start_timeout=0.5, poll_interval=0.05)
            self.assertEqual(result, "BUILD_FINISHED")
            self.assertTrue(any("finished_without_running_signal" in line
                                for line in kodi.logs))

        clock = Clock()
        kodi = FakeKodi()
        window = FakeWindow(("False", "False", "False", "False", "False", "False"))
        with mock.patch.object(interface_layout.time, "monotonic", clock.monotonic):
            result = interface_layout.request_skinshortcuts_build(
                kodi, window, FakeMonitor(clock), Path("missing-includes.xml"),
                timeout=0.2, start_timeout=0.1, poll_interval=0.05)
        self.assertEqual(result, "BUILD_NOT_CONFIRMED")
        self.assertEqual(len(kodi.commands), 1)

    def test_transient_results_are_not_success_states(self):
        for result in interface_layout.RETRYABLE_INTERFACE_RESULTS:
            with self.subTest(result=result):
                self.assertNotEqual(result, "GENERATED")
        source = (ROOT / "addons/service.actweeter/setup.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        helper = next(node for node in tree.body
                      if isinstance(node, ast.FunctionDef)
                      and node.name == "_run_pending_interface_migration")
        helper_source = ast.unparse(helper)
        self.assertIn("retry_interface_preparation", helper_source)
        self.assertIn("window.setProperty(marker_name, marker)", helper_source)
        result_branch = next(node for node in ast.walk(helper)
                             if isinstance(node, ast.If)
                             and isinstance(node.test, ast.Compare)
                             and isinstance(node.test.left, ast.Name)
                             and node.test.left.id == "result"
                             and len(node.test.comparators) == 1
                             and isinstance(node.test.comparators[0], ast.Constant)
                             and node.test.comparators[0].value == "GENERATED")
        result_branch_source = ast.unparse(result_branch)
        self.assertIn("window.setProperty(marker_name, marker)", result_branch_source)
        self.assertNotIn("window.clearProperty(marker_name)", result_branch_source)

    def test_home_reload_cannot_relaunch_a_completed_or_deferred_migration(self):
        source = (ROOT / "addons/service.actweeter/setup.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        helper = next(node for node in tree.body
                      if isinstance(node, ast.FunctionDef)
                      and node.name == "_run_pending_interface_migration")
        helper_source = ast.unparse(helper)
        self.assertIn('window.getProperty(marker_name) == marker', helper_source)
        self.assertGreaterEqual(helper_source.count('window.setProperty(marker_name, marker)'), 2)
        self.assertIn('if explicit', helper_source)
        self.assertIn('window.clearProperty(marker_name)', helper_source)

    def test_stale_lock_removed_only_when_owner_is_proven_gone_and_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            lock = Path(temp) / "interface-prepare.lock"
            lock.write_text('{"pid":123}', encoding="utf-8")
            with mock.patch.object(interface_layout.os, "kill",
                                   side_effect=ProcessLookupError):
                self.assertTrue(interface_layout.remove_stale_preparation_lock(
                    lock, current_pid=999))
            self.assertFalse(lock.exists())

            lock.write_text('{"pid":123}', encoding="utf-8")
            with mock.patch.object(interface_layout.os, "kill"):
                self.assertFalse(interface_layout.remove_stale_preparation_lock(
                    lock, current_pid=999))
            self.assertTrue(lock.exists())

            with mock.patch.object(interface_layout.os, "kill",
                                   side_effect=ValueError("unsupported probe")):
                self.assertFalse(interface_layout.remove_stale_preparation_lock(
                    lock, current_pid=999))
            self.assertTrue(lock.exists())

            lock.write_text('{"pid":123}', encoding="utf-8")
            def changed_during_probe(_pid, _signal):
                lock.write_text('{"pid":456}', encoding="utf-8")
                raise ProcessLookupError
            with mock.patch.object(interface_layout.os, "kill",
                                   side_effect=changed_during_probe):
                self.assertFalse(interface_layout.remove_stale_preparation_lock(
                    lock, current_pid=999))
            self.assertEqual(lock.read_text(encoding="utf-8"), '{"pid":456}')


if __name__ == "__main__":
    unittest.main()
