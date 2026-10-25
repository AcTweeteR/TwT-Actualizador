import importlib.util
from pathlib import Path
import unittest
import base64
import json
import sys
import threading
from types import SimpleNamespace
from unittest.mock import Mock, patch

p = Path(__file__).resolve().parents[1] / "addons/service.actweeter/resources/lib/slyguy_preview_bridge.py"
spec = importlib.util.spec_from_file_location("preview_bridge_target_test", p)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class PreviewTargetPlatformRoutes(unittest.TestCase):
    def test_supported_youtube_and_tubed_paths(self):
        for path in ("plugin://plugin.video.youtube/play/?video_id=abcdefghijk",
                     "plugin://plugin.video.tubed/?mode=play&video_id=abcdefghijk",
                     "https://youtu.be/abcdefghijk"):
            with self.subTest(path=path):
                self.assertEqual(m.preview_target(path, lambda _: None), ("youtube", "abcdefghijk"))

    def test_unrecognized_plugin_rejected(self):
        self.assertEqual(m.preview_target("plugin://evil.example/play/?video_id=abcdefghijk", lambda _: None), ("", ""))


class ResolvedPreviewTests(unittest.TestCase):
    def worker(self, item, current=True):
        worker = m.SlyGuyPreviewService.__new__(m.SlyGuyPreviewService)
        worker.xbmc = Mock(LOGINFO=1, LOGWARNING=2)
        worker.xbmc.translatePath.side_effect = str
        worker.player = Mock()
        worker.build_item = Mock(return_value=item)
        worker.get_youtube_id = lambda path: None
        worker.play_yt_dlp = Mock()
        worker.resolve_imdb = Mock()
        worker.refresh_settings = Mock()
        worker._is_current = Mock(return_value=current)
        worker.lock = threading.Condition()
        worker.closed = False
        return worker

    def item(self, path):
        item = SimpleNamespace(path=path, headers={'Referer': 'fixture'},
            inputstream=object(), proxy_data={'fixture': True}, subtitles=['fixture'])
        li = Mock()
        def get_li(**kwargs):
            if item.path.startswith('special://temp/'):
                item.path = 'http://127.0.0.1:1234/' + item.path
            return li
        item.get_li = Mock(side_effect=get_li)
        return item

    def request(self):
        return {'generation': 1, 'request_id': 'a'*32+'-1', 'identity': 'tmdb:42',
                'media_type': 'movie', 'tmdb': '42', 'title': 'Fixture'}

    def test_native_resolved_manifests_reuse_item_metadata_and_unique_path(self):
        for path in ('special://temp/yt.mpd', 'special://temp/imdb.m3u8'):
            with self.subTest(path=path):
                item = self.item(path)
                worker = self.worker(item)
                vfs = Mock(); vfs.copy.return_value = True
                before = (item.headers, item.inputstream, item.proxy_data, item.subtitles)
                with patch.dict(sys.modules, {'kodi_six.xbmcvfs': vfs}):
                    self.assertEqual(worker._resolve(self.request()), 'started')
                worker.play_yt_dlp.assert_not_called()
                worker.resolve_imdb.assert_not_called()
                self.assertEqual((item.headers, item.inputstream, item.proxy_data, item.subtitles), before)
                vfs.copy.assert_called_once()
                self.assertIn('actweeter_preview_' + 'a'*32 + '-1', vfs.copy.call_args.args[1])
                self.assertEqual(worker.player.play.call_args.args[0], item.path)
                self.assertTrue(worker.player.play.call_args.kwargs['windowed'])
                worker.player.play.call_args.args[1].setProperty.assert_any_call("script.trakt.exclude", "true")
                vfs.delete.assert_not_called()

    def test_native_https_media_preserved_but_arbitrary_urls_fail_closed(self):
        for path, expected in (
            ('https://video.media-amazon.com/fixture.m3u8', 'started'),
            ('https://r1.googlevideo.com/fixture.m3u8', 'started'),
            ('https://evil.example/movie.mp4', 'no_results'),
            ('https://media-amazon.com.evil.example/movie.mp4', 'no_results'),
            ('http://video.media-amazon.com/movie.mp4', 'no_results'),
            ('file:///tmp/movie.mp4', 'no_results'),
            ('special://temp/other.mpd', 'no_results'),
            ('plugin://evil.example/?video_id=abcdefghijk', 'no_results')):
            with self.subTest(path=path):
                worker = self.worker(self.item(path))
                with patch.dict(sys.modules, {'kodi_six.xbmcvfs': Mock()}):
                    self.assertEqual(worker._resolve(self.request()), expected)
                self.assertEqual(worker.player.play.call_count, int(expected == 'started'))

    def test_unresolved_route_still_resolves_once(self):
        worker = self.worker(self.item('plugin://slyguy.trailers/play/?video_id=abcdefghijk'))
        manifest = 'special://temp/actweeter_preview_' + 'a'*32 + '-1.mpd'
        worker.play_yt_dlp.return_value = self.item(manifest)
        with patch.dict(sys.modules, {'kodi_six.xbmcvfs': Mock()}):
            self.assertEqual(worker._resolve(self.request()), 'started')
        worker.play_yt_dlp.assert_called_once_with('abcdefghijk', manifest_path=manifest)

    def test_focus_changed_during_native_resolution_never_plays_or_copies(self):
        worker = self.worker(self.item('special://temp/yt.mpd'))
        worker._is_current.side_effect = [True, False]
        vfs = Mock()
        with patch.dict(sys.modules, {'kodi_six.xbmcvfs': vfs}):
            self.assertEqual(worker._resolve(self.request()), 'stale')
        worker.player.play.assert_not_called()
        vfs.copy.assert_not_called()

    def test_copy_failure_never_plays(self):
        worker = self.worker(self.item('special://temp/yt.mpd'))
        vfs = Mock(); vfs.copy.return_value = False
        with patch.dict(sys.modules, {'kodi_six.xbmcvfs': vfs}):
            self.assertEqual(worker._resolve(self.request()), 'error')
        worker.player.play.assert_not_called()

    def test_focus_exit_are_not_decode_errors_but_malformed_resolve_is(self):
        worker = self.worker(None)
        for action in ('focus', 'exit'):
            payload = base64.b64encode(json.dumps({'action': action}).encode()).decode()
            self.assertFalse(worker.on_notification(m.REQUEST_SENDER, 'Other.'+m.MESSAGE,
                                                   json.dumps([payload])))
        worker.xbmc.log.assert_not_called()
        self.assertFalse(worker.on_notification(m.REQUEST_SENDER, 'Other.'+m.MESSAGE,
                                               json.dumps(['not-base64!'])))
        self.assertIn('decode_rejected', worker.xbmc.log.call_args.args[0])
