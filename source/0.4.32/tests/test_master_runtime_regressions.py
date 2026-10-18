from __future__ import annotations

import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "addons/service.actweeter/resources/lib"
sys.path.insert(0, str(LIB))

from automatic_preview import PreviewOwnership  # noqa: E402
from playing_video_item import get_playing_video_item  # noqa: E402


class MasterRuntimeRegressionTests(unittest.TestCase):
    def test_idle_home_focus_recovers_stale_other_owner(self):
        ownership = PreviewOwnership()
        ownership.external_playback()

        self.assertIsNone(ownership.latest_candidate("tt123", 11111, 1508, 1508, 1))
        self.assertTrue(ownership.recover_idle_other_owner(player_has_media=False))
        self.assertEqual(ownership.owner, "NONE")
        self.assertIsNotNone(ownership.latest_candidate("tt123", 11111, 1508, 1508, 1))

    def test_owner_recovery_fails_closed_during_playback(self):
        ownership = PreviewOwnership()
        ownership.external_playback()

        self.assertFalse(ownership.recover_idle_other_owner(player_has_media=True))
        self.assertEqual(ownership.owner, "OTHER")
        self.assertIsNone(ownership.latest_candidate("tt123", 11111, 1508, 1508, 1))

    def test_auto_preview_owner_is_never_released_as_idle_other(self):
        ownership = PreviewOwnership()
        request = ownership.latest_candidate("tt123", 11111, 1508, 1508, 1)
        ownership.av_started(request, request.generation, "tt123", 11111, 1508)

        self.assertFalse(ownership.recover_idle_other_owner(player_has_media=False))
        self.assertEqual(ownership.owner, "AUTO_PREVIEW")

    def test_terminal_callback_does_not_query_item_after_video_stops(self):
        class StoppedPlayer:
            def isPlayingVideo(self):
                return False

            def getPlayingItem(self):
                raise AssertionError("must not query Kodi after playback stopped")

        self.assertIsNone(get_playing_video_item(StoppedPlayer()))

    def test_active_video_item_is_still_available(self):
        marker = object()

        class ActivePlayer:
            def isPlayingVideo(self):
                return True

            def getPlayingItem(self):
                return marker

        self.assertIs(get_playing_video_item(ActivePlayer()), marker)

    def test_movies_shortcut_uses_unquoted_plugin_target(self):
        shortcuts = ET.parse(
            ROOT / "addons/skin.actweeter/shortcuts/movies.DATA.xml")
        action = shortcuts.findtext("./shortcut/action") or ""

        self.assertEqual(
            action,
            'ActivateWindow(Videos,"plugin://plugin.video.xstream-pro/?mode=movies_menu",return)')


if __name__ == "__main__":
    unittest.main()
