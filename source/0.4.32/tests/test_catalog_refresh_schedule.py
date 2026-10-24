import importlib.util
import sys
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "addons/service.actweeter/resources/lib"
spec = importlib.util.spec_from_file_location("search_background", LIB / "search_background.py")
search_background = importlib.util.module_from_spec(spec)
spec.loader.exec_module(search_background)
sys.path.insert(0, str(LIB))
from catalog_refresh import read_retry_state, record_retry_result


class CatalogRefreshScheduleTests(unittest.TestCase):
    def test_automatic_refresh_is_due_at_24_hours(self):
        interval = search_background.DEFAULT_INTERVAL_SECONDS
        self.assertEqual(interval, 24 * 60 * 60)
        first = search_background.refresh_interval("/profile/device-a", 2)
        self.assertEqual(first, search_background.refresh_interval("/profile/device-a", 2))
        self.assertGreaterEqual(first, interval)
        self.assertLess(first, interval + search_background.REFRESH_JITTER_SECONDS)
        self.assertFalse(search_background.refresh_due(100, 100 + interval - 1))
        self.assertTrue(search_background.refresh_due(100, 100 + interval))
        gate = search_background.RefreshGate()
        self.assertTrue(gate.should_request(100, 100 + interval))
        gate.mark_requested(100 + interval)
        self.assertFalse(gate.should_request(100, 100 + interval + 1))

    def test_background_refresh_url_does_not_force_provider_refresh(self):
        url = search_background.plugin_refresh_url(2)
        self.assertIn("view=search_sync", url)
        self.assertIn("profile_num=2", url)
        self.assertNotIn("force_provider_refresh", url)

    def test_manual_button_uses_catalog_only_search_refresh(self):
        setup = (ROOT / "addons/service.actweeter/setup.py").read_text(encoding="utf-8")
        runtime = (ROOT / "third_party/xstream/patches/1.1.2/actweeter-runtime.patch").read_text(encoding="utf-8")
        start = setup.split("def _catalog_refresh_start(dialog):", 1)[1].split("def _catalog_refresh_result", 1)[0]
        sync = runtime.split("+    if view == 'search_sync':", 1)[1].split("+    if view == 'search':", 1)[0]
        self.assertIn("view=search_sync", start)
        self.assertIn("force_provider_refresh=1", start)
        self.assertNotIn("actweeter_refresh_profile", start)
        self.assertIn("force_provider_refresh = get('force_provider_refresh') == '1'", sync)
        self.assertIn("g['_cache_valid'](key)", sync)
        self.assertIn("catalog_refresh_result", sync)
        self.assertIn("empty Xtream streams snapshot", runtime)
        self.assertIn("empty Xtream categories snapshot", runtime)

    def test_generated_premium_route_is_valid_python(self):
        patch = (ROOT / "third_party/xstream/patches/1.1.2/actweeter-runtime.patch").read_text(encoding="utf-8")
        added_file = patch.split("+++ b/resources/lib/premium_routes.py\n", 1)[1].split("diff --git ", 1)[0]
        body = added_file.split("@@ -0,0 +1,", 1)[1].split(" @@\n", 1)[1]
        source = "\n".join(line[1:] for line in body.splitlines() if line.startswith("+"))
        compile(source, "premium_routes.py", "exec")

    def test_persistent_backoff_is_progressive_and_auth_blocks_automatic_retry(self):
        with tempfile.TemporaryDirectory() as profile:
            first = record_retry_result(profile, 1, "error", category="connection",
                                        now=100, jitter=0)
            self.assertEqual(first["retry_at"], 100 + 30 * 60)
            second = record_retry_result(profile, 1, "error", category="timeout",
                                         now=200, jitter=0)
            self.assertEqual(second["retry_at"], 200 + 2 * 60 * 60)
            resumed = read_retry_state(profile, 1)
            self.assertEqual(resumed["failures"], 2)
            self.assertEqual(resumed["retry_at"], second["retry_at"])
            auth = record_retry_result(profile, 1, "error", category="authentication",
                                       now=300, jitter=0)
            self.assertTrue(auth["automatic_blocked"])
            self.assertEqual(auth["retry_at"], 0)

    def test_retry_after_is_never_shortened_and_success_resets_backoff(self):
        with tempfile.TemporaryDirectory() as profile:
            state = record_retry_result(profile, 1, "error", category="rate_limited",
                                        retry_after=7200, now=100, jitter=0)
            self.assertEqual(state["retry_at"], 100 + 7200)
            cleared = record_retry_result(profile, 1, "success", now=200)
            self.assertEqual(cleared["failures"], 0)
            self.assertEqual(cleared["retry_at"], 0)


if __name__ == "__main__":
    unittest.main()
