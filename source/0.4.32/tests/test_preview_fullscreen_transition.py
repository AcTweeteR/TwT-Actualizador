import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock

LIB = Path(__file__).resolve().parents[1] / "addons/service.actweeter/resources/lib"
sys.path.insert(0, str(LIB))
from kodi_auto_preview import KodiAutoPreviewCoordinator, stable_identity


class FullscreenTransitionTests(TestCase):
    def test_title_and_year_identify_preview_when_external_ids_are_missing(self):
        payload = {"media_type": "movie", "title": "Obsesión", "year": "2025", "tmdb": ""}
        self.assertEqual(stable_identity(payload), "title:obsesión:2025")
        self.assertEqual(stable_identity({**payload, "tmdb": "603"}), "tmdb:603")
        self.assertEqual(stable_identity({**payload, "year": ""}), "title:obsesión:")
        self.assertEqual(stable_identity({**payload, "media_type": "episode"}), "")
        self.assertEqual(stable_identity({**payload, "title": ""}), "")

    def test_focused_card_without_external_ids_keeps_preview_ownership(self):
        c = self.coordinator()
        request = SimpleNamespace(generation=7, identity="title:obsesión:2025",
                                  window=10000, container=1508, focus=1508, position=0)
        c.scheduler.active = request
        c.kodi.getCondVisibility.side_effect = lambda expr: expr == "Window.IsActive(10000)"
        c.kodi.getInfoLabel.side_effect = lambda label: {
            "System.CurrentControlId": "1508",
            "Container(1508).CurrentItem": "0",
            "Container(1508).ListItem.DBType": "movie",
            "Container(1508).ListItem.Title": "Obsesión",
            "Container(1508).ListItem.Year": "2025",
        }.get(label, "")
        self.assertTrue(c._active_focus_still_matches(request))
        request.position = 1
        self.assertFalse(c._active_focus_still_matches(request))

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

    def test_invalid_placeholder_does_not_erase_previous_valid_row(self):
        c = self.coordinator()
        c.focus_context = {"window": 10000, "container": 13003,
                           "focus": 13003, "position": 2, "tmdb": "603"}
        c.delay_parser = float
        payload = {"window": 10000, "container": 13004, "focus": 13004,
                   "position": 1, "media_type": "movie", "tmdb": ""}
        self.assertFalse(c._focus(payload))
        self.assertEqual(c.focus_context["tmdb"], "603")

    def test_other_windows_keep_normal_focus_validation(self):
        c = self.coordinator()
        c.kodi.getCondVisibility.side_effect = None
        c.kodi.getCondVisibility.return_value = False
        self.assertFalse(c._owned_fullscreen(c.scheduler.active))
        c._owned_item.assert_not_called()
