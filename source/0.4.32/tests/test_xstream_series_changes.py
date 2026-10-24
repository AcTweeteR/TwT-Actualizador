import importlib.util
import json
from datetime import datetime, timezone
import sys
import tempfile
import time
import types
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "third_party/xstream/series_changes.py"


def _normalize_inventory(episodes):
    if not isinstance(episodes, dict) or not episodes:
        return [], False
    rows = []
    complete = True
    for season, entries in episodes.items():
        try:
            season_number = int(season)
        except (TypeError, ValueError):
            complete = False
            continue
        if not isinstance(entries, list):
            complete = False
            continue
        for item in entries:
            if not isinstance(item, dict):
                complete = False
                continue
            try:
                episode_number = int(item.get("episode_num", item.get("num")))
            except (TypeError, ValueError):
                complete = False
                continue
            provider_id = str(item.get("id") or item.get("episode_id") or "")
            if episode_number < 1 or not provider_id:
                complete = False
                continue
            rows.append({"season": season_number, "episode": episode_number,
                         "provider_id": provider_id})
    return sorted(rows, key=lambda row: (row["season"], row["episode"])), bool(rows) and complete


class SeriesChangesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_modules = patch.dict(sys.modules, {
            "xbmcvfs": types.SimpleNamespace(translatePath=lambda path: path),
            "series_state": types.SimpleNamespace(
                normalize_inventory=_normalize_inventory,
                inventory_diagnostics=lambda _episodes: {}),
        })
        cls.temp_modules.start()
        spec = importlib.util.spec_from_file_location("tested_series_changes", SOURCE)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    @classmethod
    def tearDownClass(cls):
        cls.temp_modules.stop()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.addon = types.SimpleNamespace(
            getAddonInfo=lambda _key: self.temp.name)

    def read(self):
        return json.loads(Path(self.temp.name, "series_changes_p1.json").read_text())

    def test_first_install_baselines_without_flood_and_uses_only_recent_added_dates(self):
        now = time.time()
        rows = [{"series_id": str(i), "name": "Series %d" % i} for i in range(70)]
        rows[0]["added"] = int(now - 60)
        self.assertTrue(self.module.record_catalog(
            self.addon, 1, rows, provider=("https://provider.invalid", "account")))
        data = self.read()
        self.assertEqual(len(data["catalog_ids"]), 70)
        self.assertEqual([row["series_id"] for row in data["events"]], ["0"])
        self.assertNotIn("provider.invalid", json.dumps(data))
        self.assertNotIn("account", json.dumps(data))

    def test_legacy_empty_baseline_is_not_misread_as_a_complete_empty_catalog(self):
        Path(self.temp.name, "series_changes_p1.json").write_text(
            json.dumps({"catalog_ids": [], "events": [], "episode_ids": {},
                        "episode_inventory": {}}), encoding="utf-8")
        rows = [{"series_id": "old", "name": "Existing without provider date"}]
        self.module.record_catalog(self.addon, 1, rows, force=True)
        self.assertEqual(self.module.status(self.addon, 1, "old"), "")
        self.assertEqual(self.read()["catalog_ids"], ["old"])

    def test_provider_added_dates_produce_the_same_first_install_labels(self):
        now = datetime.now(timezone.utc).isoformat()
        rows = [{"series_id": "new", "name": "New Show", "added": now}]
        device_a = self.addon
        other = tempfile.TemporaryDirectory()
        self.addCleanup(other.cleanup)
        device_b = types.SimpleNamespace(getAddonInfo=lambda _key: other.name)
        for addon in (device_a, device_b):
            self.module.record_catalog(addon, 1, rows,
                                       provider=("https://provider.invalid", "account"))
        self.assertEqual(self.module.status(device_a, 1, "new"), "NUEVA SERIE")
        self.assertEqual(self.module.status(device_b, 1, "new"), "NUEVA SERIE")

    def test_change_labels_expire_at_five_day_boundary(self):
        now = 2_000_000_000
        path = Path(self.temp.name, "series_changes_p1.json")
        path.write_text(json.dumps({
            "schema_version": 2,
            "catalog_ids": ["day4", "day5", "day6"],
            "events": [
                {"series_id": "day4", "status": "NUEVA SERIE", "changed": now - 4 * 86400},
                {"series_id": "day5", "status": "NUEVA SERIE", "changed": now - 5 * 86400},
                {"series_id": "day6", "status": "NUEVA SERIE", "changed": now - 5 * 86400 - 1},
            ],
            "episode_ids": {}, "episode_inventory": {},
        }), encoding="utf-8")
        with patch.object(self.module.time, "time", return_value=now):
            self.assertEqual(self.module.status(self.addon, 1, "day4"), "NUEVA SERIE")
            self.assertEqual(self.module.status(self.addon, 1, "day5"), "NUEVA SERIE")
            self.assertEqual(self.module.status(self.addon, 1, "day6"), "")
        with patch.object(self.module.time, "time", return_value=now + 1):
            self.assertEqual(self.module.status(self.addon, 1, "day5"), "")

    def test_timezone_free_provider_dates_are_not_treated_as_reliable(self):
        rows = [{"series_id": "unknown-timezone", "name": "Unknown",
                 "added": datetime.now().isoformat()}]
        self.module.record_catalog(self.addon, 1, rows)
        self.assertEqual(self.module.status(self.addon, 1, "unknown-timezone"), "")

    def test_more_than_fifty_new_series_remain_labelled_and_widget_stays_bounded(self):
        rows = [{"series_id": str(i), "name": "Series %d" % i} for i in range(100)]
        self.module.record_catalog(self.addon, 1, rows)
        changed = rows + [{"series_id": "new-%d" % i, "name": "New %d" % i}
                          for i in range(75)]
        self.module.record_catalog(self.addon, 1, changed, force=True)
        self.assertEqual(len(self.read()["events"]), 75)
        self.assertTrue(all(self.module.status(self.addon, 1, "new-%d" % i)
                            == "NUEVA SERIE" for i in range(75)))
        self.assertEqual(len(self.module.recent(self.addon, 1, 500)), 50)

    def test_catalog_throttle_skips_rescanning_the_large_provider_list(self):
        rows = [{"series_id": str(i), "name": "Series %d" % i} for i in range(5000)]
        self.module.record_catalog(self.addon, 1, rows)
        with patch.object(self.module, "_catalog_snapshot", side_effect=AssertionError("rescanned")):
            self.assertFalse(self.module.record_catalog(self.addon, 1, rows))

    def test_partial_or_malformed_catalog_does_not_create_baseline_or_events(self):
        rows = [{"series_id": "1", "name": "One"}]
        self.assertFalse(self.module.record_catalog(self.addon, 1, rows, complete=False))
        self.assertFalse(Path(self.temp.name, "series_changes_p1.json").exists())
        self.assertFalse(self.module.record_catalog(
            self.addon, 1, rows + [{"series_id": "2"}], force=True))
        self.assertFalse(Path(self.temp.name, "series_changes_p1.json").exists())

    def test_incomplete_episode_inventory_does_not_replace_last_complete_inventory(self):
        first = {"episodes": {"1": [{"id": "e1", "episode_num": 1}]}}
        partial = {"episodes": {"1": [{"id": "e1", "episode_num": 1},
                                       {"id": "e2", "episode_num": "bad"}]}}
        second = {"episodes": {"1": [{"id": "e1", "episode_num": 1},
                                       {"id": "e2", "episode_num": 2,
                                        "added": int(time.time())}]}}
        self.assertTrue(self.module.record_series_info(self.addon, 1, "s1", "Show", first))
        self.assertFalse(self.module.record_series_info(self.addon, 1, "s1", "Show", partial))
        self.assertEqual(self.read()["episode_ids"]["s1"], ["e1"])
        self.assertTrue(self.module.record_series_info(self.addon, 1, "s1", "Show", second))
        self.assertEqual(self.read()["episode_ids"]["s1"], ["e1", "e2"])
        self.assertEqual(self.module.status(self.addon, 1, "s1"), "NUEVOS CAPÍTULOS")

    def test_provider_episode_added_timestamp_labels_a_first_inventory_deterministically(self):
        added = datetime.now(timezone.utc).isoformat()
        response = {"episodes": {"1": [{"id": "e1", "episode_num": 1,
                                         "added": added}]}}
        self.assertTrue(self.module.record_series_info(
            self.addon, 1, "s1", "Show", response,
            provider=("https://provider.invalid", "account")))
        self.assertEqual(self.module.status(self.addon, 1, "s1"), "NUEVOS CAPÍTULOS")

    def test_old_provider_episode_date_does_not_turn_into_a_false_recent_event(self):
        first = {"episodes": {"1": [{"id": "e1", "episode_num": 1}]}}
        second = {"episodes": {"1": [
            {"id": "e1", "episode_num": 1},
            {"id": "e2", "episode_num": 2, "added": int(time.time() - 90 * 86400)},
        ]}}
        self.assertTrue(self.module.record_series_info(self.addon, 1, "s1", "Show", first))
        self.assertTrue(self.module.record_series_info(self.addon, 1, "s1", "Show", second))
        self.assertEqual(self.module.status(self.addon, 1, "s1"), "")

    def test_expired_new_series_event_does_not_suppress_later_episode_news(self):
        old = time.time() - 90 * 86400
        data = {"schema_version": 2, "catalog_ids": ["s1"],
                "events": [{"series_id": "s1", "title": "Show",
                            "status": "NUEVA SERIE", "changed": old}],
                "episode_ids": {"s1": ["e1"]},
                "episode_inventory": {"s1": {"complete": True, "episodes": [
                    {"provider_id": "e1"}]}}}
        Path(self.temp.name, "series_changes_p1.json").write_text(
            json.dumps(data), encoding="utf-8")
        response = {"episodes": {"1": [
            {"id": "e1", "episode_num": 1},
            {"id": "e2", "episode_num": 2},
        ]}}
        self.module.record_series_info(self.addon, 1, "s1", "Show", response)
        self.assertEqual(self.module.status(self.addon, 1, "s1"), "NUEVOS CAPÍTULOS")

    def test_catalog_reconstruction_and_provider_switch_are_fail_safe(self):
        rows = [{"series_id": "1", "name": "One"}]
        provider_a = ("https://a.invalid", "user-a")
        provider_b = ("https://b.invalid", "user-b")
        self.module.record_catalog(self.addon, 1, rows, provider=provider_a)
        self.module.record_catalog(self.addon, 1,
                                   rows + [{"series_id": "2", "name": "Two"}],
                                   force=True, provider=provider_a)
        self.assertEqual(self.module.status(self.addon, 1, "2"), "NUEVA SERIE")
        self.module.record_catalog(self.addon, 1,
                                   rows + [{"series_id": "2", "name": "Two"}],
                                   force=True, provider=provider_a)
        self.assertEqual(len(self.read()["events"]), 1)
        # A provider change establishes a clean baseline instead of cross-matching IDs.
        self.module.record_catalog(self.addon, 1, rows, force=True, provider=provider_b)
        self.assertEqual(self.module.status(self.addon, 1, "2"), "")
        self.assertEqual(self.read()["catalog_ids"], ["1"])

    def test_change_labels_survive_a_fresh_xstream_module_process(self):
        rows = [{"series_id": "1", "name": "One"}]
        self.module.record_catalog(self.addon, 1, rows)
        self.module.record_catalog(self.addon, 1,
                                   rows + [{"series_id": "2", "name": "Two"}], force=True)
        spec = importlib.util.spec_from_file_location("restarted_series_changes", SOURCE)
        restarted = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(restarted)
        self.assertEqual(restarted.status(self.addon, 1, "2"), "NUEVA SERIE")

    def test_corrupt_state_is_preserved_and_legacy_state_migrates_on_write(self):
        path = Path(self.temp.name, "series_changes_p1.json")
        path.write_text("{broken", encoding="utf-8")
        self.assertFalse(self.module.record_catalog(
            self.addon, 1, [{"series_id": "1", "name": "One"}], force=True))
        self.assertEqual(path.read_text(encoding="utf-8"), "{broken")
        path.write_text(json.dumps({"catalog_ids": ["1"], "events": [],
                                    "episode_ids": {}, "episode_inventory": {}}),
                        encoding="utf-8")
        self.module.record_catalog(self.addon, 1,
                                   [{"series_id": "1", "name": "One"},
                                    {"series_id": "2", "name": "Two"}], force=True)
        self.assertEqual(self.read()["schema_version"], 2)
        self.assertEqual(self.module.status(self.addon, 1, "2"), "NUEVA SERIE")
        self.assertFalse(list(Path(self.temp.name).glob(".series_changes_*")))

    def test_malformed_event_rows_fail_closed_without_erasing_state(self):
        path = Path(self.temp.name, "series_changes_p1.json")
        original = json.dumps({"schema_version": 2, "events": [None],
                               "catalog_ids": ["1"], "episode_ids": {},
                               "episode_inventory": {}})
        path.write_text(original, encoding="utf-8")
        self.assertFalse(self.module.record_catalog(
            self.addon, 1, [{"series_id": "2", "name": "Two"}], force=True))
        self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_skin_consumes_the_property_written_by_xstream(self):
        skin = ROOT / "addons/skin.actweeter/1080i"
        for filename, include_name in (
                ("IncludesViewsLayoutPoster.xml", "Poster_New_Episodes_Tag_Overlay"),
                ("IncludesViewsLayoutLandscape.xml", "New_Episodes_Tag_Overlay"),
                ("IncludesViewsLayoutSquare.xml", "Square_New_Episodes_Tag_Overlay")):
            path = skin / filename
            tree = ET.parse(path)
            self.assertTrue(any(node.get("name") == include_name
                                for node in tree.iter("include")))
            self.assertIn("XStream.ChangeStatus", path.read_text(encoding="utf-8"))
        patch_text = (ROOT / "third_party/xstream/patches/1.1.2/actweeter-runtime.patch")
        self.assertIn("setProperty('XStream.ChangeStatus', status)",
                      patch_text.read_text(encoding="utf-8"))

    def test_startup_uses_the_configured_splash_setting_before_home(self):
        startup = ET.parse(ROOT / "addons/skin.actweeter/1080i/Startup.xml").getroot()
        actions = [node for node in startup.findall("onload")
                   if "ReplaceWindow" in (node.text or "")]
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].get("condition"),
                         "String.IsEmpty(Skin.String(splash_screen))")

    def test_five_thousand_series_catalog_has_bounded_processing_cost(self):
        rows = [{"series_id": str(i), "name": "Series %d" % i} for i in range(5000)]
        start = time.perf_counter()
        self.module.record_catalog(self.addon, 1, rows)
        elapsed = time.perf_counter() - start
        self.assertEqual(len(self.read()["catalog_ids"]), 5000)
        self.assertLess(elapsed, 5.0)


if __name__ == "__main__":
    unittest.main()
