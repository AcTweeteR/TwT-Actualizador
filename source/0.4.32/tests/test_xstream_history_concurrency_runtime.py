"""Integration exercise against the real XStream history.py inside a built ZIP."""
import os
import subprocess
import sys
import unittest


REAL_XSTREAM_TEST = r'''
import json, multiprocessing, os, sys, tempfile, types
from pathlib import Path
root = Path(tempfile.mkdtemp())
xbmc = types.ModuleType("xbmc")
xbmc.LOGWARNING = 2
xbmc.log = lambda *args: None
xbmc.getCondVisibility = lambda condition: False
sys.modules["xbmc"] = xbmc
addon_module = types.ModuleType("xbmcaddon")
addon_module.Addon = lambda *args: None
sys.modules["xbmcaddon"] = addon_module
vfs = types.ModuleType("xbmcvfs")
vfs.translatePath = lambda value: str(root)
sys.modules["xbmcvfs"] = vfs
sys.path.insert(0, sys.argv[1] + "/plugin.video.xstream-pro/resources/lib")
import history
addon = types.SimpleNamespace(getAddonInfo=lambda key: str(root))

# Real XStream instances reproduce stale in-memory snapshots.
a, b = history.WatchedMovies(addon, 1), history.WatchedMovies(addon, 1)
a.mark_watched(11); b.mark_watched(22)
assert set(json.loads((root / "watched_movies_p1.json").read_text())) == {"11", "22"}
a, b = history.WatchedEpisodes(addon, 1), history.WatchedEpisodes(addon, 1)
a.mark_watched(7, 1, 11); b.mark_watched(7, 1, 22)
assert set(json.loads((root / "watched_episodes_p1.json").read_text())["7"]["1"]) == {"11", "22"}

# A stale resume writer cannot replace the newer source timestamp.
a, b = history.ResumePoints(addon, 1), history.ResumePoints(addon, 1)
a.save_position("Film", "https://example.invalid/movie", 600, 3600,
                timestamp=200, force=True)
b.save_position("Film", "https://example.invalid/movie", 300, 3600,
                timestamp=100, force=True)
item = json.loads((root / "resume_points_p1.json").read_text())["Film||https://example.invalid/movie"]
assert item["position"] == 600 and item["timestamp"] == 200
current = history.ResumePoints(addon, 1)
current.save_position("Film", "https://example.invalid/movie", 300, 3600,
                      timestamp=100, force=True)
item = json.loads((root / "resume_points_p1.json").read_text())["Film||https://example.invalid/movie"]
assert item["position"] == 600 and item["timestamp"] == 200
# The stale writer may have loaded the newer value as its baseline.
stale = history.ResumePoints(addon, 1)
newer = history.ResumePoints(addon, 1)
newer.save_position("Baseline", "https://example.invalid/baseline", 600, 3600,
                    timestamp=200, force=True)
stale.save_position("Baseline", "https://example.invalid/baseline", 300, 3600,
                    timestamp=100, force=True)
item = json.loads((root / "resume_points_p1.json").read_text())["Baseline||https://example.invalid/baseline"]
assert item["position"] == 600 and item["timestamp"] == 200

# Sub-minute ticks do not rewrite the store; stop can force the final sample.
r = history.ResumePoints(addon, 1)
r.save_position("Cadence", "https://example.invalid/cadence", 100, 3600, force=True)
store = root / "resume_points_p1.json"
mtime = store.stat().st_mtime_ns
assert r.save_position("Cadence", "https://example.invalid/cadence", 105, 3600) is False
assert store.stat().st_mtime_ns == mtime
assert r.save_position("Cadence", "https://example.invalid/cadence", 165, 3600, force=True) is True

# Separate Kodi-style Python processes serialize through the OS lock.
def write_one(number):
    store = history.WatchedMovies(types.SimpleNamespace(getAddonInfo=lambda key: str(root)), 1)
    store.mark_watched(1000 + number)
if "fork" in multiprocessing.get_all_start_methods():
    with multiprocessing.get_context("fork").Pool(6) as pool:
        pool.map(write_one, range(24))
    movies = json.loads((root / "watched_movies_p1.json").read_text())
    assert all(str(1000 + number) in movies for number in range(24))

# Corrupt JSON must fail closed rather than being replaced with an empty store.
store_path = root / "resume_points_p1.json"
store_path.write_text("{corrupt", encoding="utf-8")
before = store_path.read_bytes()
try:
    history.ResumePoints(addon, 1).save_position(
        "Unsafe", "https://example.invalid/unsafe", 500, 3600, force=True)
except Exception:
    pass
else:
    raise AssertionError("corrupt store was overwritten")
assert store_path.read_bytes() == before
# Simulate failure at atomic replace: committed JSON stays intact and a later
# save can recover without dropping either operation.
real_replace = os.replace
history.os.replace = lambda *args: (_ for _ in ()).throw(OSError("simulated replace failure"))
try:
    history.WatchedMovies(addon, 1).mark_watched(2001)
except OSError:
    pass
else:
    raise AssertionError("simulated atomic replace failure was ignored")
finally:
    history.os.replace = real_replace
movies = history.WatchedMovies(addon, 1)
movies.mark_watched(2002)
persisted = json.loads((root / "watched_movies_p1.json").read_text())
assert "2001" not in persisted and "2002" in persisted
assert all(str(1000 + number) in persisted for number in range(24))
print("real XStream history store integration: PASS")
'''

UPSTREAM_LOST_UPDATE_TEST = r'''
import json, sys, tempfile, types
from pathlib import Path
root = Path(tempfile.mkdtemp())
xbmc = types.ModuleType("xbmc"); xbmc.LOGWARNING = 2; xbmc.log = lambda *a: None
xbmc.getCondVisibility = lambda condition: False; sys.modules["xbmc"] = xbmc
addon_module = types.ModuleType("xbmcaddon"); addon_module.Addon = lambda *a: None
sys.modules["xbmcaddon"] = addon_module
vfs = types.ModuleType("xbmcvfs"); vfs.translatePath = lambda value: str(root)
sys.modules["xbmcvfs"] = vfs
sys.path.insert(0, sys.argv[1] + "/plugin.video.xstream-pro/resources/lib")
import history
addon = types.SimpleNamespace(getAddonInfo=lambda key: str(root))
first, second = history.WatchedMovies(addon, 1), history.WatchedMovies(addon, 1)
first.mark_watched(11); second.mark_watched(22)
assert set(json.loads((root / "watched_movies_p1.json").read_text())) == {"22"}
print("unpatched XStream stale-instance lost update reproduced: PASS")
'''


class XStreamHistoryConcurrencyRuntimeTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("ACTWEETER_XSTREAM_UPSTREAM_ZIP"),
                         "set ACTWEETER_XSTREAM_UPSTREAM_ZIP to the pinned upstream ZIP")
    def test_upstream_lost_update_is_reproducible(self):
        result = subprocess.run(
            [sys.executable, "-c", UPSTREAM_LOST_UPDATE_TEST,
             os.environ["ACTWEETER_XSTREAM_UPSTREAM_ZIP"]],
            text=True, capture_output=True, timeout=45,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("reproduced", result.stdout)

    @unittest.skipUnless(os.environ.get("ACTWEETER_XSTREAM_TEST_ZIP"),
                         "set ACTWEETER_XSTREAM_TEST_ZIP to a reproducible candidate ZIP")
    def test_real_xstream_classes_serialize_and_merge(self):
        result = subprocess.run(
            [sys.executable, "-c", REAL_XSTREAM_TEST,
             os.environ["ACTWEETER_XSTREAM_TEST_ZIP"]],
            text=True, capture_output=True, timeout=45,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
