import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import unittest


SOURCE = Path(__file__).resolve().parents[1]
MODULE = SOURCE / "third_party/xstream/performance_diagnostics.py"
MANIFEST = SOURCE / "third_party/xstream/upstream.json"
PATCH = SOURCE / "third_party/xstream/patches/1.1.2/actweeter-performance-diagnostics.patch"


def load_module():
    spec = importlib.util.spec_from_file_location("performance_diagnostics", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PerformanceDiagnosticsTests(unittest.TestCase):
    def payload(self, line):
        return json.loads(line.split(" ", 2)[2])

    def test_trace_aggregates_calls_and_never_logs_arguments(self):
        module = load_module()
        lines = []
        ticks = itertools.count(1)
        trace = module.PerformanceTrace(log=lines.append, clock=lambda: next(ticks) / 1000.0)
        trace.set_context("popular", "movie")
        self.assertEqual(trace.call("external.tmdb.details", lambda _secret: "ok",
                                    "https://private.invalid/token=secret"), "ok")
        trace.emit()

        self.assertEqual(len(lines), 1)
        self.assertNotIn("private.invalid", lines[0])
        self.assertNotIn("token=secret", lines[0])
        payload = self.payload(lines[0])
        self.assertEqual(payload["route"], "popular")
        self.assertEqual(payload["media"], "movie")
        self.assertEqual(payload["phases"]["external.tmdb.details"]["count"], 1)
        self.assertEqual(payload["counts"]["external.tmdb.details.calls"], 1)


    def test_instrument_cache_counts_hits_without_exposing_keys(self):
        module = load_module()
        lines = []
        trace = module.PerformanceTrace(log=lines.append)
        cache = {"secret-key": {"safe": True}}
        namespace = {
            "_cache_load": lambda key: cache.get(key),
            "_cache_save": lambda key, value: cache.update({key: value}),
        }
        trace.instrument_cache(namespace)
        self.assertEqual(namespace["_cache_load"]("secret-key"), {"safe": True})
        self.assertIsNone(namespace["_cache_load"]("missing-secret-key"))
        namespace["_cache_save"]("another-secret-key", {"safe": True})
        trace.emit()
        self.assertNotIn("secret-key", lines[0])
        payload = self.payload(lines[0])
        self.assertEqual(payload["counts"]["cache.read.hit"], 1)
        self.assertEqual(payload["counts"]["cache.read.miss"], 1)
        self.assertEqual(payload["counts"]["cache.json.write.calls"], 1)

    def test_instrument_provider_preserves_results_and_hides_credentials(self):
        module = load_module()
        lines = []

        class Provider:
            @staticmethod
            def get_xtream_streams(*args):
                return ["same-result"]

        trace = module.PerformanceTrace(log=lines.append)
        trace.instrument_provider(Provider)
        self.assertEqual(Provider.get_xtream_streams("private-host", "secret-user", "secret"),
                         ["same-result"])
        trace.emit()
        self.assertNotIn("private-host", lines[0])
        self.assertNotIn("secret-user", lines[0])
        self.assertNotIn("secret", lines[0])
        payload = self.payload(lines[0])
        self.assertEqual(payload["counts"]["external.xtream.streams.calls"], 1)


    def test_exception_is_preserved_and_counted(self):
        module = load_module()
        lines = []
        trace = module.PerformanceTrace(log=lines.append)

        def fail():
            raise LookupError("sensitive provider message")

        with self.assertRaisesRegex(LookupError, "sensitive provider message"):
            trace.call("external.xtream.streams", fail)
        trace.emit()
        payload = self.payload(lines[0])
        self.assertEqual(payload["counts"]["external.xtream.streams.errors"], 1)
        self.assertNotIn("sensitive provider message", lines[0])


    def test_diagnostic_setting_is_off_by_default_and_source_hashes_are_locked(self):
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(data["distribution_version"], "1.1.2.28~beta1")
        self.assertEqual(hashlib.sha256(PATCH.read_bytes()).hexdigest(),
                         data["performance_patch_sha256"])
        self.assertEqual(hashlib.sha256(MODULE.read_bytes()).hexdigest(),
                         data["performance_diagnostics_sha256"])
        patch_text = PATCH.read_text(encoding="utf-8")
        self.assertIn('id="performance_diagnostics_enabled" default="false"', patch_text)
        self.assertIn('premium_routes.dispatch(globals(), args)', patch_text)


if __name__ == "__main__":
    unittest.main()
