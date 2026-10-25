"""Regressions for the actual packaged routes and terminal callbacks."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "addons/service.actweeter/resources/lib"
sys.path.insert(0, str(LIB))
import content_state
import series_state
import slyguy_player_guard
import testing_updates
from smart_search_sources import WatchedState


class TerminalTests(unittest.TestCase):
    def player(self, active=True):
        source = ast.parse((ROOT / "addons/service.actweeter/service.py").read_bytes())
        cls = next(n for n in source.body if isinstance(n, ast.ClassDef) and n.name == "SlyGuyTrailerReturnPlayer")
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_finish_intro")
        properties = {"AcTweeteRIntroPlayback": "1", "StartupMask": "1"} if active else {}
        window = SimpleNamespace(getProperty=lambda k: properties.get(k, ""),
                                 clearProperty=lambda k: properties.pop(k, None))
        env = {"xbmcgui": SimpleNamespace(Window=lambda _: window)}
        exec(compile(ast.Module(body=[method], type_ignores=[]), "terminal", "exec"), env)
        class Player:
            _finish_intro = env["_finish_intro"]
        player = Player()
        player.lock = threading.Lock()
        player.intro_playback_active = active
        player.intro_terminal_seen = False
        player.kodi = Mock(LOGINFO=1)
        player._is_actweeter_intro = Mock(side_effect=AssertionError("unsafe terminal query"))
        player.stop = Mock()
        return player, properties

    def test_intro_identity_uses_official_player_label(self):
        source = ast.parse((ROOT / "addons/service.actweeter/service.py").read_bytes())
        cls = next(n for n in source.body if isinstance(n, ast.ClassDef) and n.name == "SlyGuyTrailerReturnPlayer")
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_is_actweeter_intro")
        env = {"os": os}
        exec(compile(ast.Module(body=[method], type_ignores=[]), "identity", "exec"), env)
        values = {"Window(Home).Property(AcTweeteRIntroPlayback)": "1",
                  "Player.Filenameandpath": "/local/actweeter_intro_Kodi.mp4"}
        player = SimpleNamespace(kodi=SimpleNamespace(getInfoLabel=lambda name: values.get(name, "")))
        self.assertTrue(env["_is_actweeter_intro"](player))
        values["Player.Filenameandpath"] = "/local/other.mp4"
        self.assertFalse(env["_is_actweeter_intro"](player))
        values["Player.Filenameandpath"] = ""
        self.assertFalse(env["_is_actweeter_intro"](player))

    def test_natural_error_and_duplicate_terminal_events_query_no_player(self):
        for event in ("ended", "stopped", "error", "watchdog"):
            player, properties = self.player()
            self.assertTrue(player._finish_intro(event))
            self.assertFalse(player._finish_intro(event))
            self.assertEqual(properties, {})
            self.assertEqual(player.kodi.executebuiltin.call_count, 2)
            player.stop.assert_not_called()

    def test_simultaneous_dialog_close_and_end_are_one_transition(self):
        player, properties = self.player()
        player._is_actweeter_intro.side_effect = None
        player._is_actweeter_intro.return_value = True
        barrier = threading.Barrier(3)
        def finish(event):
            barrier.wait()
            player._finish_intro(event)
        threads = [threading.Thread(target=finish, args=(event,)) for event in ("ended", "cancelled")]
        for thread in threads: thread.start()
        barrier.wait()
        for thread in threads: thread.join()
        self.assertEqual(player.kodi.log.call_count, 1)
        self.assertEqual(properties, {})
        self.assertLessEqual(player.stop.call_count, 1)

    def test_unrelated_trailer_and_pvr_terminals_are_not_consumed(self):
        for event in ("ended", "stopped", "error"):
            player, _ = self.player(False)
            self.assertFalse(player._finish_intro(event))
            player.kodi.executebuiltin.assert_not_called()
            player.stop.assert_not_called()

    def test_slyguy_inactive_callback_never_calls_gettime(self):
        original = b'class Player:\n    def _save_stop_time(self):\n        # getTime() still reports final position\n        try:\n            self._stop_time = int(self.getTime())\n        except Exception:\n            pass\n'
        with patch.object(slyguy_player_guard, "ORIGINAL_HASH", hashlib.sha256(original).hexdigest()):
            namespace = {"log": Mock()}
            exec(slyguy_player_guard.payload(original), namespace)
        player = namespace["Player"]()
        player.isPlaying = lambda: False
        player.getTime = Mock(side_effect=RuntimeError("Kodi is not playing any media file"))
        player._save_stop_time()
        player.getTime.assert_not_called()
        player.isPlaying = lambda: True
        player.getTime = lambda: 37
        player._save_stop_time()
        self.assertEqual(player._stop_time, 37)
        with self.assertRaises(ValueError): slyguy_player_guard.payload(original)


class StateTests(unittest.TestCase):
    def test_title_metadata_cache_cannot_authorize_watched_identity(self):
        calls = []
        def cached(name, profile_num):
            calls.append((name, profile_num))
            return {'expires': time.time()+60, 'data': {'tmdb_id': '42'}}
        g = {'_cache_load': cached, 'addon': None,
             'WatchedMovies': lambda *a, **k: SimpleNamespace(_data={'tmdb:movie:42': True})}
        self.assertIsNone(content_state.watched_state(g, 'movie', '', profile_num=2, provider_id='12'))
        self.assertEqual(calls, [('vod_info_12', 2)])

    def test_exact_provider_state_does_not_require_tmdb_and_false_wins(self):
        movies = SimpleNamespace(_data={"12": True, "tmdb:movie:42": False})
        g = {"addon": None, "WatchedMovies": lambda *a, **k: movies,
             "WatchedEpisodes": lambda *a, **k: SimpleNamespace(is_watched=lambda *a: True)}
        self.assertTrue(content_state.watched_state(g, "movie", "", provider_id="12"))
        self.assertFalse(content_state.watched_state(g, "movie", "42", provider_id="12"))
        self.assertTrue(content_state.watched_state(g, "episode", "", 1, 2, provider_id="99", series_id="5"))

    @unittest.skipUnless(os.environ.get("ACTWEETER_XSTREAM_LIVE_ZIP"), "exact candidate ZIP required")
    def test_actual_packaged_season_route_builds_native_playcount(self):
        with zipfile.ZipFile(os.environ["ACTWEETER_XSTREAM_LIVE_ZIP"]) as archive:
            source = ast.parse(archive.read("plugin.video.xstream-pro/resources/lib/addon.py"))
        function = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == "xtream_series")
        for total, watched_count, complete in ((10, 10, True), (10, 9, True), (11, 10, True),
                                               (11, 11, True), (0, 0, True), (10, 10, False)):
            for show_counts in (True, False):
                with self.subTest(total=total, watched=watched_count, counts=show_counts, complete=complete):
                    rows = [{"season": 1, "episode": n, "provider_id": str(n)} for n in range(1, total+1)]
                    info = {"episodes": {"1": [{"id": n} for n in range(total)]}, "info": {"tmdb_id": "55"}}
                    record = dict(episodes=rows, checked_at=time.time(), complete=complete)
                    items = []
                    def item(label):
                        value = Mock(); items.append(value); return value
                    env = dict(addon=SimpleNamespace(getSetting=lambda k: str(show_counts).lower() if k == "show_content_counts" else "false"),
                        pm=SimpleNamespace(active=1), _get_credentials_for_profile=lambda p: {},
                        IPTV=SimpleNamespace(get_xtream_series_info=lambda *a: info),
                        series_changes=SimpleNamespace(record_series_info=lambda *a, **k: None,
                            inventory_map=lambda *a: {"77": record}, series_state=series_state),
                        WatchedMovies=lambda *a, **k: SimpleNamespace(_data={}),
                        WatchedEpisodes=lambda *a, **k: SimpleNamespace(is_watched=lambda sid, season, ep: int(ep) <= watched_count),
                        xbmcplugin=Mock(), addon_handle=1, _new_listitem=item, build_url=lambda q: "plugin://synthetic",
                        _t=lambda *a: "Season", _log=lambda *a: None)
                    exec(compile(ast.Module(body=[function], type_ignores=[]), "season-route", "exec"), env)
                    env["xtream_series"]("77", 1)
                    expected = 1 if total and total == watched_count and complete else 0
                    self.assertEqual(items[0].getVideoInfoTag().setPlaycount.call_args.args, (expected,))


class UpdateTests(unittest.TestCase):
    def test_failures_never_claim_installation_and_retries_are_bounded(self):
        import tempfile
        for scenario, expected_status in [('current', 'CURRENT'), ('blocked', 'INDIVIDUAL_UPDATE_BLOCKED'),
                ('unpropagated', 'INDEX_TIMEOUT'), ('dependency_missing', 'INSTALL_TIMEOUT'),
                ('download_failed', 'INSTALL_TIMEOUT'), ('cancelled', 'ABORTED'), ('feed_failed', 'FEED_UNAVAILABLE')]:
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as temp:
                now = [1000]
                versions = {identity: '1.0' for identity in testing_updates.COMPONENTS}
                expected = dict(versions, **{'skin.actweeter': '1.1~beta5'})
                if scenario == 'current': versions.update(expected)
                kodi, vfs, addon = Mock(LOGINFO=1), Mock(), Mock()
                addon.getAddonInfo.return_value = temp
                vfs.translatePath.side_effect = lambda value: value
                kodi.getCondVisibility.return_value = False
                def wait(seconds):
                    now[0] += seconds
                    return scenario == 'cancelled'
                kodi.Monitor.return_value.waitForAbort.side_effect = wait
                def rpc(kodi, method, **params):
                    return {'value': 0} if method.startswith('Settings') else {'addon': {'version': versions[params['addonid']]}}
                origins = {identity: dict(origin=testing_updates.REPOSITORY, blocked=(scenario == 'blocked')) for identity in versions}
                fetch = Mock(side_effect=OSError) if scenario == 'feed_failed' else Mock(return_value=('new', expected))
                metadata = ('old', {}) if scenario == 'unpropagated' else ('new', expected)
                with patch.object(testing_updates, 'installation_state', return_value=origins), patch.object(testing_updates, '_rpc', side_effect=rpc), patch.object(testing_updates, 'local_metadata', return_value=metadata):
                    result = testing_updates.check(kodi, addon, vfs, fetch=fetch, clock=lambda: now[0], timeout=6)
                    self.assertEqual(result, expected_status)
                    self.assertEqual(testing_updates.check(kodi, addon, vfs, fetch=fetch, clock=lambda: now[0], timeout=120), 'BUSY')
                self.assertLessEqual(fetch.call_count, 2)
                self.assertLessEqual(kodi.executebuiltin.call_count, 1)

    def test_beta_numeric_order_and_stable_precedence(self):
        values = ["1.2.31", "1.2.32~beta4", "1.2.32~beta5", "1.2.32~beta15", "1.2.32"]
        self.assertEqual(sorted(reversed(values), key=testing_updates.version_key), values)
        with self.assertRaises(ValueError): testing_updates.version_key("unknown")

    def test_stale_metadata_is_refreshed_once_then_native_install_observed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            now = [1000]
            versions = {identity: "1.0" for identity in testing_updates.COMPONENTS}
            expected = dict(versions, **{"skin.actweeter": "1.1~beta5"})
            kodi, vfs, addon = Mock(LOGINFO=1), Mock(), Mock()
            addon.getAddonInfo.return_value = temp
            vfs.translatePath.side_effect = lambda value: value
            kodi.getCondVisibility.return_value = False
            def wait(seconds):
                now[0] += seconds
                versions.update(expected)
                return False
            kodi.Monitor.return_value.waitForAbort.side_effect = wait
            def rpc(kodi, method, **params):
                return {"value": 0} if method.startswith("Settings") else {"addon": {"version": versions[params["addonid"]]}}
            origins = {identity: dict(origin=testing_updates.REPOSITORY, blocked=False) for identity in versions}
            with patch.object(testing_updates, "installation_state", return_value=origins), patch.object(testing_updates, "_rpc", side_effect=rpc), patch.object(testing_updates, "local_metadata", side_effect=[("old", {}), ("new", expected)]):
                self.assertEqual(testing_updates.check(kodi, addon, vfs, fetch=lambda: ("new", expected), clock=lambda: now[0]), "INSTALLED")
            kodi.executebuiltin.assert_called_once_with("UpdateAddonRepos", False)
