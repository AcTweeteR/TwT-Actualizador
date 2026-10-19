"""Manual trailer ownership and return gates, without a real player."""
import sys
import unittest
import ast
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                       "addons/service.actweeter/resources/lib"))
from slyguy_trailer_return import capture_context, manual_exit_requires_stop, return_decision, parse_identity, identity_matches


class ManualTrailerTests(unittest.TestCase):
    def test_manual_identity_rejects_malformed_and_nonstring_provider_ids(self):
        for value in ('tmdb:../evil', 'imdb:tt 123', 'tmdb:１２３',
                      'dbid:0', 'dbid:-1', 'dbid:001', 'tmdb:abc\n',
                      'tmdb:', 'other:123', None, 123):
            with self.subTest(value=value):
                self.assertIsNone(parse_identity(value))
        self.assertEqual(parse_identity('imdb:tt123'), ('imdb','tt123'))
        self.assertEqual(parse_identity('dbid:123'), ('dbid','123'))
        self.assertFalse(identity_matches('tmdb:123', {'tmdb':123}))
        self.assertFalse(identity_matches('tmdb:123', {'tmdb':None}))

    def test_manual_presentation_does_not_fullscreen_superseded_request(self):
        source = Path(__file__).resolve().parents[1] / 'addons/service.actweeter/service.py'
        player = next(node for node in ast.parse(source.read_text()).body
                      if isinstance(node, ast.ClassDef) and node.name == 'SlyGuyTrailerReturnPlayer')
        method = next(node for node in player.body
                      if isinstance(node, ast.FunctionDef) and node.name == '_present_manual')
        namespace = {'_window_id': mock.Mock(), 'manual_exit_requires_stop':manual_exit_requires_stop}
        exec(compile(ast.Module(body=[method],type_ignores=[]),str(source),'exec'),namespace)
        fake = mock.Mock()
        fake._request_is_current.side_effect = [True,False]
        namespace[method.name](fake,{'playing_file':'trailer.mp4'})
        fake.kodi.executebuiltin.assert_called_once_with('Dialog.Close(movieinformation)',False)
        fake.monitor.waitForAbort.assert_not_called()

    def test_manual_restore_recovers_only_verified_focused_list_control(self):
        source = Path(__file__).resolve().parents[1] / 'addons/service.actweeter/service.py'
        player = next(node for node in ast.parse(source.read_text()).body
                      if isinstance(node, ast.ClassDef) and node.name == 'SlyGuyTrailerReturnPlayer')
        method = next(node for node in player.body
                      if isinstance(node, ast.FunctionDef) and node.name == '_restore_context')
        code = ast.unparse(method)
        self.assertIn('xbmcgui.Window(window_id).getFocusId()', code)
        self.assertIn('candidate > 0', code)
        self.assertIn('Control.HasFocus(%d)', code)
        self.assertIn("identity_matches(context['identity'], values)", code)
        self.assertIn('source_control = candidate', code)
        self.assertIn('source_window_id', code)

    def test_manual_return_waits_require_current_request(self):
        source = Path(__file__).resolve().parents[1] / 'addons/service.actweeter/service.py'
        player = next(node for node in ast.parse(source.read_text()).body
                      if isinstance(node, ast.ClassDef) and node.name == 'SlyGuyTrailerReturnPlayer')
        method = next(node for node in player.body
                      if isinstance(node, ast.FunctionDef) and node.name == '_restore_context')
        code = ast.unparse(method)
        self.assertGreaterEqual(code.count('self._request_is_current(context)'), 4)
        self.assertIn("pending=pending == '1'", ast.unparse(next(
            node for node in player.body if isinstance(node, ast.FunctionDef)
            and node.name == '_clear_markers')))

    def test_manual_restore_refuses_missing_source_and_rechecks_before_info(self):
        source = Path(__file__).resolve().parents[1] / 'addons/service.actweeter/service.py'
        player = next(node for node in ast.parse(source.read_text()).body
                      if isinstance(node, ast.ClassDef) and node.name == 'SlyGuyTrailerReturnPlayer')
        method = next(node for node in player.body
                      if isinstance(node, ast.FunctionDef) and node.name == '_restore_context')
        statements = [node for node in ast.walk(method) if isinstance(node, ast.If)]
        missing_source_guards = [node for node in statements
                                 if 'not source_control' in ast.unparse(node.test)
                                 and 'source_window_id' in ast.unparse(node.test)]
        self.assertTrue(missing_source_guards)
        info = next(node for node in ast.walk(method)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == 'executebuiltin' and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value == 'Action(Info)')
        rechecks = [node for node in statements if node.lineno < info.lineno
                    and 'not self._request_is_current(context)' in ast.unparse(node.test)
                    and 'Control.HasFocus' in ast.unparse(node.test)
                    and 'identity_matches' in ast.unparse(node.test)]
        self.assertTrue(rechecks, 'request, focus and identity must be rechecked immediately before Info')

    def test_manual_restore_checks_focus_before_info_action(self):
        source = Path(__file__).resolve().parents[1] / 'addons/service.actweeter/service.py'
        player = next(node for node in ast.parse(source.read_text()).body
                      if isinstance(node, ast.ClassDef) and node.name == 'SlyGuyTrailerReturnPlayer')
        method = next(node for node in player.body
                      if isinstance(node, ast.FunctionDef) and node.name == '_restore_context')
        calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)]
        focus_checks = [node for node in calls if isinstance(node.func, ast.Attribute)
                        and node.func.attr == 'getCondVisibility' and node.args
                        and isinstance(node.args[0], ast.BinOp)
                        and isinstance(node.args[0].left, ast.Constant)
                        and 'Control.HasFocus' in str(node.args[0].left.value)]
        self.assertTrue(focus_checks, 'manual return must verify selected focus')
        info_calls = [node for node in calls if isinstance(node.func, ast.Attribute)
                      and node.func.attr == 'executebuiltin' and node.args
                      and isinstance(node.args[0], ast.Constant)
                      and node.args[0].value == 'Action(Info)']
        self.assertEqual(len(info_calls), 1)
        self.assertLess(focus_checks[0].lineno, info_calls[0].lineno)

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
