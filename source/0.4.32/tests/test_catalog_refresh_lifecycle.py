import multiprocessing
import sys
from pathlib import Path
import tempfile
import unittest

LIB = Path(__file__).resolve().parents[1] / "addons/service.actweeter/resources/lib"
sys.path.insert(0, str(LIB))
from catalog_refresh import (
    begin_search_operation, finish_search_operation, recover_search_operations,
    search_operation, read_retry_state,
)


def _finish_operation(profile, request_id, outcome, start, done):
    start.wait(5)
    done.put(finish_search_operation(profile, request_id, outcome, now=20))


class CatalogRefreshLifecycleTests(unittest.TestCase):
    def test_failure_is_terminal_even_when_success_timestamp_does_not_change(self):
        with tempfile.TemporaryDirectory() as profile:
            request_id = "a" * 32
            begin_search_operation(profile, request_id, 1, now=10)
            self.assertTrue(finish_search_operation(profile, request_id, "error", now=11))
            self.assertEqual(search_operation(profile, request_id)["status"], "ERROR")
            self.assertFalse(finish_search_operation(profile, request_id, "success", now=12))

    def test_restart_marks_only_unfinished_operations_interrupted(self):
        with tempfile.TemporaryDirectory() as profile:
            begin_search_operation(profile, "b" * 32, 1, now=10)
            begin_search_operation(profile, "c" * 32, 2, now=10)
            finish_search_operation(profile, "c" * 32, "success", now=11)
            self.assertEqual(recover_search_operations(profile, now=20), 1)
            self.assertEqual(search_operation(profile, "b" * 32)["status"], "INTERRUPTED")
            self.assertEqual(search_operation(profile, "c" * 32)["status"], "COMPLETED")
            self.assertEqual(read_retry_state(profile, 1)["failures"], 1)

    def test_timeout_and_late_completion_do_not_reopen_operation(self):
        with tempfile.TemporaryDirectory() as profile:
            request_id = "e" * 32
            begin_search_operation(profile, request_id, 3, now=10)
            self.assertTrue(finish_search_operation(profile, request_id, "timeout", now=40))
            self.assertFalse(finish_search_operation(profile, request_id, "success", now=41))
            self.assertEqual(search_operation(profile, request_id)["status"], "TIMEOUT")

    def test_concurrent_terminal_events_have_one_winner_across_processes(self):
        with tempfile.TemporaryDirectory() as profile:
            request_id = "d" * 32
            begin_search_operation(profile, request_id, 1, now=10)
            ctx = multiprocessing.get_context("spawn")
            start, done = ctx.Event(), ctx.Queue()
            processes = [ctx.Process(target=_finish_operation,
                                     args=(profile, request_id, outcome, start, done))
                         for outcome in ("timeout", "error")]
            for process in processes:
                process.start()
            start.set()
            results = [done.get(timeout=10) for _ in processes]
            for process in processes:
                process.join(10)
                self.assertEqual(process.exitcode, 0)
            self.assertEqual(sum(results), 1)
            self.assertIn(search_operation(profile, request_id)["status"],
                          ("TIMEOUT", "ERROR"))


if __name__ == "__main__":
    unittest.main()
