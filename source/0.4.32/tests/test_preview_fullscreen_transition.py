import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock

LIB = Path(__file__).resolve().parents[1] / "addons/service.actweeter/resources/lib"
sys.path.insert(0, str(LIB))
from kodi_auto_preview import KodiAutoPreviewCoordinator


class FullscreenTransitionTests(TestCase):
    def coordinator(self):
        c = KodiAutoPreviewCoordinator.__new__(KodiAutoPreviewCoordinator)
        c.kodi = Mock()
        c.kodi.getCondVisibility.side_effect = lambda expr: "fullscreenvideo" in expr
        c.request_ids = {7: "session-7"}
        c._owned_item = Mock(return_value=("7", "tmdb:603", "session-7"))
        c.scheduler = SimpleNamespace(active=SimpleNamespace(generation=7, identity="tmdb:603", window=10000), latest=None, resolving=None)
        c._stop_owned = Mock()
        c._log = Mock()
        return c

    def test_tab_keeps_exact_owned_video_despite_home_unload_and_unfocus(self):
        c = self.coordinator()
        self.assertTrue(c._active_focus_still_matches(c.scheduler.active))
        self.assertTrue(c._exit_home())
        self.assertFalse(c._cancel({}))
        c._stop_owned.assert_not_called()

    def test_other_player_or_old_request_is_not_preserved(self):
        for owned in (("8", "tmdb:603", "session-7"), ("7", "tmdb:604", "session-7"), ("7", "tmdb:603", "old-session"), ("", "", "")):
            with self.subTest(owned=owned):
                c = self.coordinator()
                c._owned_item.return_value = owned
                self.assertFalse(c._owned_fullscreen(c.scheduler.active))
                self.assertFalse(c._active_focus_still_matches(c.scheduler.active))

    def test_other_windows_keep_normal_focus_validation(self):
        c = self.coordinator()
        c.kodi.getCondVisibility.side_effect = None
        c.kodi.getCondVisibility.return_value = False
        self.assertFalse(c._owned_fullscreen(c.scheduler.active))
        c._owned_item.assert_not_called()
