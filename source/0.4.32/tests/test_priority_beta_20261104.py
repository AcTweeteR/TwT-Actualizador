"""Regression checks for the 2026-11-04 isolated priority Beta."""
import sys
import tempfile
import time
import types
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]
sys.path.insert(0, str(ROOT / "addons/service.actweeter/resources/lib"))
sys.path.insert(0, str(ROOT / "third_party/xstream"))

from kodi_auto_preview import extract_preview_trailer_id
from watched_progress import IncompleteSeriesInventory, prior_episodes, mark_progress
from pvr_epg_health import acceptable, should_refresh
from series_state import _valid_stored_inventory


def inventory():
    rows = [{"season": s, "episode": e, "provider_id": "ep%s_%s" % (s, e)}
            for s, limit in ((1, 2), (2, 3)) for e in range(1, limit + 1)]
    return {"complete": True, "checked_at": time.time(), "tmdb_id": "123",
            "episodes": rows}


class TrailerSelectionTests(unittest.TestCase):
    def test_youtube_url_and_kodi_plugin_are_recognized(self):
        paths = [
            "plugin://plugin.video.youtube/play/?video_id=Abc123_-DEF",
            "https://youtu.be/Abc123_-DEF",
            "https://www.youtube.com/watch?v=Abc123_-DEF",
        ]
        for path in paths:
            self.assertEqual(extract_preview_trailer_id(path), "Abc123_-DEF")

    def test_no_guess_from_foreign_or_invalid_trailers(self):
        for path in ["", "plugin://plugin.video.other/?video_id=Abc123_-DEF",
                     "https://untrusted.example/watch?v=Abc123_-DEF",
                     "plugin://plugin.video.youtube/play/?video_id=short",
                     "https://youtube.com/watch?v=Abc123_-DEF!",
                     "https://youtu.be/"]:
            self.assertEqual(extract_preview_trailer_id(path), "")


class SeriesProgressTests(unittest.TestCase):
    def test_marks_previous_seasons_in_order(self):
        rows = prior_episodes(inventory(), 2, 2)
        self.assertEqual([(x["season"], x["episode"]) for x in rows],
                         [(1, 1), (1, 2), (2, 1), (2, 2)])

    def test_refuses_incomplete_stale_ambiguous_or_nonexistent(self):
        invalid = [
            dict(inventory(), complete=False),
            dict(inventory(), checked_at=time.time()-20*86400),
            dict(inventory(), episodes=[{"season":1,"episode":1,"provider_id":"a"},
                                        {"season":1,"episode":1,"provider_id":"b"}]),
        ]
        for record in invalid:
            with self.assertRaises(IncompleteSeriesInventory):
                prior_episodes(record, 2, 2)
        for season, ep in [(0, 1), (2, 9), ("bad", 1)]:
            with self.assertRaises(IncompleteSeriesInventory):
                prior_episodes(inventory(), season, ep)

    def test_monotonic_idempotent_preserves_later_marks(self):
        class Store:
            def __init__(self, data):
                self._data = data
                self.saves = 0
            def _save(self):
                self.saves += 1
        native = Store({"my-series": {"2": ["ep2_3"]}})
        mirror = Store({"tmdb:episode:123:s2:e3": True})
        record = inventory()
        sys.modules["series_changes"] = types.SimpleNamespace(
            inventory_map=lambda addon, pnum: {"my-series": record})
        package = PROJECT / "build/priority-beta-ready/plugin.video.xstream-pro-1.1.2.40~beta1.zip"
        with zipfile.ZipFile(package) as archive:
            watched_source = archive.read(
                "plugin.video.xstream-pro/resources/lib/watched_actions.py")
        module = types.ModuleType("watched_actions")
        exec(compile(watched_source, "watched_actions.py", "exec"), module.__dict__)
        sys.modules["watched_actions"] = module
        try:
            refresh = []
            g = {"pm": types.SimpleNamespace(active="1"), "addon": object(),
                 "WatchedEpisodes": lambda *args, **kwargs: native,
                 "WatchedMovies": lambda *args, **kwargs: mirror,
                 "xbmc": types.SimpleNamespace(executebuiltin=refresh.append)}
            request = {"profile_num":["1"],"series_id":["my-series"],
                       "season":["2"],"episode":["2"],"tmdb_id":["123"]}
            result = mark_progress(g, request)
            self.assertEqual(result, {"episodes_up_to_target": 4, "newly_marked": 4})
            self.assertIn("ep2_3", native._data["my-series"]["2"])
            self.assertEqual(len(native._data["my-series"]["1"]), 2)
            self.assertEqual(native.saves, 1)
            self.assertEqual(mirror.saves, 1)
            self.assertTrue(mirror._data["tmdb:episode:123:s2:e3"])
            self.assertEqual(mark_progress(g, request)["newly_marked"], 0)
            self.assertEqual(native.saves, 1)
            self.assertEqual(mirror.saves, 1)
            with self.assertRaises(IncompleteSeriesInventory):
                mark_progress(g, dict(request, profile_num=["2"]))
            with self.assertRaises(IncompleteSeriesInventory):
                mark_progress(g, dict(request, tmdb_id=["999"]))
            self.assertEqual(native.saves, 1)
            self.assertEqual(mirror.saves, 1)
        finally:
            sys.modules.pop("series_changes", None)
            sys.modules.pop("watched_actions", None)


class EPGHealthTests(unittest.TestCase):
    def test_missing_or_stale_file_requires_refresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "guide.xml"
            self.assertTrue(should_refresh(path))
            path.write_text("<tv/>")
            self.assertFalse(should_refresh(path))
            self.assertTrue(should_refresh(path, now=time.time()+5*3600))

    def test_large_historical_guide_is_not_fresh(self):
        import pvr_epg_health
        fake = types.SimpleNamespace(_parse_xmltv_time=int)
        with patch.dict(sys.modules, {"epg": fake}):
            guide = {str(i): [{"start": "10", "stop": "20"}] for i in range(500)}
            for i in range(3):
                guide[str(i)] = [{"start": "100", "stop": "200"}]
            self.assertFalse(acceptable(guide, now=150))
            for i in range(3, 12):
                guide[str(i)] = [{"start": "100", "stop": "200"}]
            self.assertTrue(acceptable(guide, now=150))


class CandidatePackageTests(unittest.TestCase):
    def test_beta_packages_are_constructed_from_stable_not_in_place(self):
        directory = PROJECT / "build/priority-beta-ready"
        for addon, v in [("skin.actweeter", "1.2.40~beta1"),
                         ("service.actweeter", "0.4.98~beta1"),
                         ("plugin.video.xstream-pro", "1.1.2.40~beta1")]:
            path = directory / f"{addon}-{v}.zip"
            self.assertTrue(path.exists(), path)
            with zipfile.ZipFile(path) as z:
                self.assertIsNone(z.testzip())
                info = ET.fromstring(z.read(addon + "/addon.xml"))
                self.assertEqual(info.get("version"), v)

    def test_episodes_art_and_progress_are_in_distribution(self):
        path = PROJECT / "build/priority-beta-ready/plugin.video.xstream-pro-1.1.2.40~beta1.zip"
        with zipfile.ZipFile(path) as z:
            src = z.read("plugin.video.xstream-pro/resources/lib/addon.py").decode()
            self.assertIn('setContent(addon_handle, "seasons")', src)
            self.assertIn('art["season.poster"]', src)
            self.assertIn("Establecer progreso hasta aquí", src)
            self.assertIn("mark_progress_to", src)
            self.assertIn("acceptable(epg.programs)", src)
            self.assertEqual(src.count('li.addContextMenuItems(ctx)\n        watched_actions'), 0)


if __name__ == "__main__":
    unittest.main()
