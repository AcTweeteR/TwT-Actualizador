import json
import multiprocessing
import os
import sys
import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "third_party/xstream"))
import catalog_cache


def snapshots(marker):
    return {
        "xtream_streams_movie": [{"stream_id": marker, "marker": marker}],
        "xtream_cats_movie": [{"category_id": "m", "marker": marker}],
        "xtream_streams_series": [{"series_id": marker, "marker": marker}],
        "xtream_cats_series": [{"category_id": "s", "marker": marker}],
    }


def process_refresh(root, active, peak, calls, barrier, force):
    barrier.wait()

    def fetch(key):
        with active.get_lock():
            active.value += 1
            peak.value = max(peak.value, active.value)
        with calls.get_lock():
            calls.value += 1
        time.sleep(.04)
        with active.get_lock():
            active.value -= 1
        return snapshots("one")[key]

    catalog_cache.refresh(root, 1, "https://provider|user|password",
                          {key: (lambda key=key: fetch(key)) for key in catalog_cache.KEYS},
                          force=force, timeout=5)


def process_holds_lock(root, ready, release):
    with catalog_cache.provider_lock(root, 1, "https://provider|user|password",
                                     timeout=5):
        ready.set()
        release.wait(10)


class CatalogCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = "https://provider|user|password"

    def tearDown(self):
        self.temp.cleanup()

    def fetchers(self, values):
        return {key: (lambda key=key: values[key]) for key in catalog_cache.KEYS}

    def load(self, key):
        path = catalog_cache.cache_path(self.root, 1, self.source, key)
        return json.loads(Path(path).read_text())

    def test_failed_component_does_not_publish_any_new_component(self):
        first = catalog_cache.refresh(self.root, 1, self.source,
                                      self.fetchers(snapshots("old")), force=True)
        broken = self.fetchers(snapshots("new"))
        broken["xtream_cats_series"] = lambda: (_ for _ in ()).throw(OSError("offline"))
        with self.assertRaisesRegex(OSError, "offline"):
            catalog_cache.refresh(self.root, 1, self.source, broken, force=True)
        self.assertEqual(catalog_cache.current_generation(self.root, 1, self.source),
                         first["generation"])
        for key in catalog_cache.KEYS:
            self.assertEqual(self.load(key)["_data"][0]["marker"], "old")

    def test_generation_persists_only_provider_fingerprint_and_reads_legacy_cache(self):
        catalog_cache.refresh(self.root, 1, self.source,
                              self.fetchers(snapshots("private")), force=True)
        fingerprint = catalog_cache.provider_fingerprint(self.source)
        for key in catalog_cache.KEYS:
            raw = Path(catalog_cache.cache_path(
                self.root, 1, self.source, key)).read_bytes()
            value = json.loads(raw)
            self.assertEqual(value["_src"], fingerprint)
            self.assertNotIn(b"password", raw)
            self.assertTrue(catalog_cache.source_matches(value, self.source))
        self.assertTrue(catalog_cache.source_matches({"_src": self.source}, self.source))

    def test_crash_before_pointer_swap_keeps_previous_generation(self):
        first = catalog_cache.refresh(self.root, 1, self.source,
                                      self.fetchers(snapshots("old")), force=True)
        real_atomic = catalog_cache._atomic_write

        def fail_pointer(path, content):
            if Path(path).name.endswith(".json") and Path(path).parent.name == "catalog_generations":
                raise OSError("simulated interruption")
            return real_atomic(path, content)

        with patch.object(catalog_cache, "_atomic_write", side_effect=fail_pointer):
            with self.assertRaisesRegex(OSError, "interruption"):
                catalog_cache.refresh(self.root, 1, self.source,
                                      self.fetchers(snapshots("new")), force=True)
        self.assertEqual(catalog_cache.current_generation(self.root, 1, self.source),
                         first["generation"])
        self.assertEqual(self.load("xtream_streams_movie")["_data"][0]["stream_id"], "old")

    def test_corrupt_current_generation_recovers_previous_after_restart(self):
        first = catalog_cache.refresh(self.root, 1, self.source,
                                      self.fetchers(snapshots("old")), force=True)
        second = catalog_cache.refresh(self.root, 1, self.source,
                                       self.fetchers(snapshots("new")), force=True)
        active = Path(catalog_cache.cache_path(self.root, 1, self.source,
                                               "xtream_streams_movie"))
        active.write_text("corrupt")
        catalog_cache.reset_pins()
        self.assertEqual(catalog_cache.current_generation(self.root, 1, self.source),
                         first["generation"])
        self.assertEqual(self.load("xtream_streams_movie")["_data"][0]["marker"], "old")
        self.assertNotEqual(first["generation"], second["generation"])

    def test_empty_replacement_of_nonempty_component_is_rejected(self):
        first = catalog_cache.refresh(self.root, 1, self.source,
                                      self.fetchers(snapshots("old")), force=True)
        values = snapshots("new")
        values["xtream_streams_series"] = []
        with self.assertRaisesRegex(ValueError, "empty snapshot"):
            catalog_cache.refresh(self.root, 1, self.source, self.fetchers(values), force=True)
        self.assertEqual(catalog_cache.current_generation(self.root, 1, self.source),
                         first["generation"])

    def test_manual_and_auto_process_refreshes_coalesce(self):
        ctx = multiprocessing.get_context("spawn")
        active, peak, calls = ctx.Value("i", 0), ctx.Value("i", 0), ctx.Value("i", 0)
        barrier = ctx.Barrier(2)
        procs = [ctx.Process(target=process_refresh, args=(
            str(self.root), active, peak, calls, barrier, force))
            for force in (True, False)]
        for proc in procs:
            proc.start()
        for proc in procs:
            proc.join(10)
        self.assertEqual([proc.exitcode for proc in procs], [0, 0])
        self.assertEqual(peak.value, 1)
        self.assertEqual(calls.value, 4)

    def test_reader_keeps_one_generation_during_concurrent_refresh(self):
        catalog_cache.refresh(self.root, 1, self.source,
                              self.fetchers(snapshots("old")), force=True)
        ready, updated = threading.Event(), threading.Event()
        observed, errors = [], []

        def read_generation():
            try:
                observed.append(self.load(catalog_cache.KEYS[0])["_data"][0]["marker"])
                ready.set()
                if not updated.wait(5):
                    raise TimeoutError("refresh did not finish")
                observed.extend(self.load(key)["_data"][0]["marker"]
                                for key in catalog_cache.KEYS[1:])
            except Exception as exc:
                errors.append(exc)
                ready.set()

        reader = threading.Thread(target=read_generation)
        reader.start()
        self.assertTrue(ready.wait(5))
        catalog_cache.refresh(self.root, 1, self.source,
                              self.fetchers(snapshots("new")), force=True)
        updated.set()
        reader.join(5)
        self.assertFalse(reader.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(observed, ["old"] * len(catalog_cache.KEYS))
        self.assertEqual(self.load(catalog_cache.KEYS[0])["_data"][0]["marker"], "new")

    def test_reader_pin_survives_multiple_refreshes(self):
        catalog_cache.refresh(self.root, 1, self.source,
                              self.fetchers(snapshots("old")), force=True)
        ready, updated = threading.Event(), threading.Event()
        observed, errors = [], []

        def read_generation():
            try:
                first = catalog_cache.cache_path(
                    self.root, 1, self.source, catalog_cache.KEYS[0])
                ready.set()
                if not updated.wait(5):
                    raise TimeoutError("refreshes did not finish")
                observed.append(json.loads(Path(first).read_text())[
                    "_data"][0]["marker"])
                observed.extend(self.load(key)["_data"][0]["marker"]
                                for key in catalog_cache.KEYS[1:])
            except Exception as exc:
                errors.append(exc)
                ready.set()

        reader = threading.Thread(target=read_generation)
        reader.start()
        self.assertTrue(ready.wait(5))
        for marker in ("new", "newest"):
            catalog_cache.refresh(self.root, 1, self.source,
                                  self.fetchers(snapshots(marker)), force=True)
        updated.set()
        reader.join(5)
        self.assertFalse(reader.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(observed, ["old"] * len(catalog_cache.KEYS))

    def test_timeout_and_cancel_while_lock_is_held(self):
        event = multiprocessing.Event()
        with catalog_cache.provider_lock(self.root, 1, self.source):
            with self.assertRaises(TimeoutError):
                with catalog_cache.provider_lock(self.root, 1, self.source,
                                                 timeout=.01, poll_interval=.001):
                    pass
            event.set()
            with self.assertRaises(catalog_cache.RefreshCancelled):
                with catalog_cache.provider_lock(self.root, 1, self.source,
                                                 timeout=1, cancel=event):
                    pass

    def test_cancel_during_refresh_keeps_previous_generation_and_releases_lock(self):
        first = catalog_cache.refresh(self.root, 1, self.source,
                                      self.fetchers(snapshots("old")), force=True)
        cancelled = multiprocessing.Event()
        fetchers = self.fetchers(snapshots("new"))
        fetchers["xtream_streams_movie"] = lambda: (cancelled.set(), snapshots("new")[
            "xtream_streams_movie"])[1]
        with self.assertRaises(catalog_cache.RefreshCancelled):
            catalog_cache.refresh(self.root, 1, self.source, fetchers,
                                  force=True, cancel=cancelled)
        self.assertEqual(catalog_cache.current_generation(self.root, 1, self.source),
                         first["generation"])
        with catalog_cache.provider_lock(self.root, 1, self.source, timeout=.1):
            pass

    def test_terminated_process_lock_is_recovered(self):
        ctx = multiprocessing.get_context("spawn")
        ready, release = ctx.Event(), ctx.Event()
        process = ctx.Process(target=process_holds_lock,
                              args=(str(self.root), ready, release))
        process.start()
        self.assertTrue(ready.wait(5))
        process.terminate()
        process.join(5)
        self.assertIsNotNone(process.exitcode)
        result = catalog_cache.refresh(self.root, 1, self.source,
                                       self.fetchers(snapshots("recovered")),
                                       force=True, timeout=2)
        self.assertTrue(result["refreshed"])
        self.assertEqual(self.load("xtream_streams_movie")["_data"][0]["marker"],
                         "recovered")

    def test_dead_owner_lock_is_recovered(self):
        lock = self.root / "catalog_generations" / (
            "p1-" + catalog_cache.provider_fingerprint(self.source) + ".lock")
        lock.parent.mkdir(parents=True)
        lock.write_text(json.dumps({"pid": 999999999, "created": time.time(), "token": "dead"}))
        with catalog_cache.provider_lock(self.root, 1, self.source, timeout=.1):
            self.assertTrue(lock.exists())
        self.assertTrue(lock.exists())

    def test_malformed_stale_lock_file_does_not_block_acquisition(self):
        lock = self.root / "catalog_generations" / (
            "p1-" + catalog_cache.provider_fingerprint(self.source) + ".lock")
        lock.parent.mkdir(parents=True)
        lock.write_text("bad")
        os.utime(lock, (time.time() - 500, time.time() - 500))
        with catalog_cache.provider_lock(self.root, 1, self.source, timeout=.1):
            pass
        lock.write_text("bad")
        with catalog_cache.provider_lock(self.root, 1, self.source, timeout=.1):
            pass


if __name__ == "__main__":
    unittest.main()
