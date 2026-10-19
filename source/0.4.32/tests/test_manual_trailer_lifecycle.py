"""Manual trailer ownership and return gates, without a real player."""
import sys
import unittest
import ast
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                       "addons/service.actweeter/resources/lib"))
from slyguy_trailer_return import capture_context, manual_exit_requires_stop, return_decision


class ManualTrailerTests(unittest.TestCase):
    def test_real_presentation_worker_stops_only_its_own_file_after_back(self):
        source = Path(__file__).resolve().parents[1] / "addons/service.actweeter/service.py"
        player = next(node for node in ast.parse(source.read_text()).body
                      if isinstance(node, ast.ClassDef) and node.name == "SlyGuyTrailerReturnPlayer")
        method = next(node for node in player.body
                      if isinstance(node, ast.FunctionDef) and node.name == "_present_manual")
        for second_file, expected in (("trailer.mp4", 1), ("movie.mp4", 0)):
            with self.subTest(second_file=second_file):
                namespace = {"_window_id": mock.Mock(side_effect=[12005, 10000]),
                             "manual_exit_requires_stop": manual_exit_requires_stop}
                exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), "exec"), namespace)
                fake = mock.Mock()
                fake.monitor.waitForAbort.side_effect = [False, False, True]
                fake.isPlayingVideo.return_value = True
                fake._request_is_current.return_value = True
                fake.getPlayingFile.side_effect = ["trailer.mp4", second_file]
                namespace[method.name](fake, {"playing_file": "trailer.mp4"})
                self.assertEqual(fake.stop.call_count, expected)
                self.assertEqual(fake.kodi.executebuiltin.call_args_list,
                                 [mock.call("Dialog.Close(movieinformation)", False),
                                  mock.call("ActivateWindow(fullscreenvideo)", False)])

    def test_movie_and_series_capture_require_matching_identity(self):
        for media in ("movie", "tvshow"):
            args = dict(pending=True, explicit_request=True, vod_pending=False,
                        window_id=12003, item_type=media, identity="tmdb:123",
                        current_values={"tmdb": "123"})
            self.assertIsNotNone(capture_context(**args))
            args["current_values"] = {"tmdb": "999"}
            self.assertIsNone(capture_context(**args))

    def test_stop_requires_exact_file_request_and_observed_fullscreen_exit(self):
        context = {"playing_file": "trailer.mp4"}
        args = dict(playing_file="trailer.mp4", window_id=10000,
                    fullscreen_seen=True, request_current=True)
        self.assertTrue(manual_exit_requires_stop(context, **args))
        for field, value in (("playing_file", "movie.mp4"),
                             ("playing_file", ""), ("window_id", 12005),
                             ("window_id", 10100), ("fullscreen_seen", False),
                             ("request_current", False)):
            with self.subTest(field=field, value=value):
                self.assertFalse(manual_exit_requires_stop(context, **(args | {field: value})))

    def test_transient_empty_identity_waits_but_different_identity_abandons(self):
        context = {"identity": "tmdb:123", "origin": "VIDEO_INFO",
                   "return_window_id": 12003}
        for window in (12003, 10000, 11110, 11111, 10025):
            args = dict(event="stopped", player_active=False, window_id=window)
            with self.subTest(window=window):
                self.assertEqual(return_decision(context, current_values={}, **args), "wait")
                self.assertEqual(return_decision(context, current_values={"tmdb": "999"}, **args), "abandon")

    def test_home_and_series_hub_restore_only_matching_detail(self):
        context = {"identity": "tmdb:123", "origin": "VIDEO_INFO",
                   "return_window_id": 12003}
        for window in (10000, 11110, 11111, 10025):
            args = dict(event="stopped", player_active=False, window_id=window)
            self.assertEqual(return_decision(context, current_values={"tmdb": "123"}, **args), "restore")
            self.assertEqual(return_decision(context, current_values={"tmdb": "999"}, **args), "abandon")
