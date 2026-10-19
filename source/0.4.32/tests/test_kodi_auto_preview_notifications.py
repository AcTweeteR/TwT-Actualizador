"""Fail-closed Kodi preview notification contracts; no Kodi runtime required."""

from __future__ import annotations

import base64
import json
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "addons/service.actweeter/resources/lib"
sys.path.insert(0, str(LIB))

from automatic_preview import LatestPreviewScheduler, PreviewOwnership  # noqa: E402
from kodi_auto_preview import KodiAutoPreviewCoordinator, SENDER, MESSAGE  # noqa: E402


class FakeKodi:
    LOGINFO = 1

    def __init__(self, has_media=False, visibility_error=False):
        self.has_media = has_media
        self.visibility_error = visibility_error
        self.commands = []
        self.messages = []

    def getCondVisibility(self, condition):
        assert condition == "Player.HasMedia"
        if self.visibility_error:
            raise RuntimeError("Kodi is shutting down")
        return self.has_media

    def executebuiltin(self, command, wait=False):
        self.commands.append((command, wait))

    def log(self, message, level):
        self.messages.append(message)


def focus_packet(**updates):
    payload = {
        "action": "focus",
        "imdb": "tt123",
        "window": 11111,
        "container": 1508,
        "focus": 1508,
        "position": 1,
        "media_type": "movie",
        "delay": 1.25,
    }
    payload.update(updates)
    return payload


def notification(payload):
    encoded = base64.b64encode(
        json.dumps(payload).encode("utf-8")).decode("ascii")
    return json.dumps([encoded])


def coordinator(kodi):
    # Exercise real on_notification/_focus code while bypassing background
    # worker and all Kodi playback/device state.
    instance = object.__new__(KodiAutoPreviewCoordinator)
    instance.kodi = kodi
    instance.closed = False
    instance.focus_context = None
    instance.clock = lambda: 100.0
    instance.delay_parser = float
    instance.session_id = "notification-test"
    instance.scheduler = LatestPreviewScheduler(PreviewOwnership())
    instance.wake = instance.scheduler.condition
    instance.requests = {}
    instance.item_data = {}
    instance.request_ids = {}
    instance.stop_lock = threading.Lock()
    instance.stop_inflight = set()
    instance.stop_timeline = {}
    instance.stale_owned = set()
    instance.vfs = None
    instance.kodi.getInfoLabel = lambda label: ""
    instance._stop_owned = lambda request, **kwargs: None
    return instance


class PreviewNotificationTests(unittest.TestCase):
    def test_idle_row_selection_schedules_once_after_non_movie_item(self):
        kodi = FakeKodi()
        bridge = coordinator(kodi)
        bridge._focus(focus_packet(media_type="episode"))
        labels = {"System.CurrentControlId": "1508",
                  "Container(1508).CurrentItem": "2",
                  "Container(1508).ListItem.DBType": "movie",
                  "Container(1508).ListItem.UniqueID(imdb)": "tt456"}
        kodi.getInfoLabel = lambda key: labels.get(key, "")
        kodi.getCondVisibility = lambda key: key == "Window.IsActive(11111)"
        bridge._poll_selected_card()
        request = bridge.scheduler.latest
        self.assertEqual(request.identity, "imdb:tt456")
        self.assertEqual(request.position, 2)
        bridge._poll_selected_card()
        self.assertEqual(bridge.scheduler.latest, request)

    def test_idle_poll_does_not_schedule_during_playback_or_outside_row(self):
        kodi = FakeKodi()
        bridge = coordinator(kodi)
        bridge._focus(focus_packet())
        request = bridge.scheduler.latest
        kodi.getCondVisibility = lambda key: key == "Player.HasMedia"
        bridge._poll_selected_card()
        self.assertEqual(bridge.scheduler.latest, request)
        kodi.getCondVisibility = lambda key: key == "Window.IsActive(11111)"
        kodi.getInfoLabel = lambda key: "40000"
        bridge._poll_selected_card()
        self.assertEqual(bridge.scheduler.latest, request)

    def test_mismatched_container_and_focus_is_rejected(self):
        bridge = coordinator(FakeKodi())
        self.assertFalse(bridge._focus(focus_packet(focus=13006)))
        self.assertIsNone(bridge.focus_context)
        self.assertIsNone(bridge.scheduler.latest)

    def test_new_focus_preserves_displaced_request_until_stop_callback(self):
        bridge = coordinator(FakeKodi())
        bridge._focus(focus_packet())
        old = bridge.scheduler.latest
        token = bridge.request_ids[old.generation]
        bridge.scheduler.take_ready(102)
        bridge.scheduler.resolution_finished(old, still_current=True)
        bridge.stop_inflight.add(old.generation)
        bridge.stop_timeline[old.generation] = {
            "requested_at": 99, "worker_finished_at": 99.5,
            "terminal_callback_at": 100,
        }
        bridge.scheduler.preempt("OTHER")
        bridge._focus(focus_packet(imdb="tt456", container=13005, focus=13005))
        new = bridge.scheduler.latest
        self.assertIn(old.generation, bridge.requests)
        self.assertIsNone(bridge._take_ready(105))
        self.assertFalse(bridge.terminal_by_identity(old.generation, old.identity, "wrong", "stopped"))
        self.assertTrue(bridge.terminal_by_identity(old.generation, old.identity, token, "stopped"))
        self.assertNotIn(old.generation, bridge.stop_inflight)
        self.assertEqual(bridge._take_ready(105), new)

    def test_valid_focus_notification_schedules_latest_request(self):
        kodi = FakeKodi()
        bridge = coordinator(kodi)

        self.assertTrue(
            bridge.on_notification(SENDER, MESSAGE, notification(focus_packet())))
        self.assertEqual(bridge.scheduler.latest.identity, "imdb:tt123")
        self.assertEqual(bridge.scheduler.delay_deadline, 101.25)
        self.assertEqual(len(kodi.commands), 1)

    def test_prefixed_kodi_notification_is_accepted(self):
        kodi = FakeKodi()
        bridge = coordinator(kodi)

        self.assertTrue(bridge.on_notification(
            SENDER, "Other." + MESSAGE, notification(focus_packet())))
        self.assertIsNotNone(bridge.scheduler.latest)

    def test_foreign_sender_or_broken_envelope_has_no_side_effects(self):
        for sender, data in (
            ("untrusted.addon", notification(focus_packet())),
            (SENDER, json.dumps(["invalid base64!"])),
        ):
            with self.subTest(sender=sender):
                kodi = FakeKodi()
                bridge = coordinator(kodi)
                self.assertFalse(bridge.on_notification(sender, MESSAGE, data))
                self.assertEqual(bridge.scheduler.ownership.generation, 0)
                self.assertEqual(kodi.commands, [])

    def test_missing_required_numeric_fields_rejected_without_side_effects(self):
        for key in ("window", "container", "focus", "position"):
            with self.subTest(missing=key):
                kodi = FakeKodi()
                bridge = coordinator(kodi)
                payload = focus_packet()
                del payload[key]

                self.assertFalse(
                    bridge.on_notification(SENDER, MESSAGE, notification(payload)))
                self.assertEqual(bridge.scheduler.ownership.generation, 0)
                self.assertIsNone(bridge.scheduler.latest)
                self.assertEqual(kodi.commands, [])
                self.assertTrue(any(
                    "FOCUS_REJECT" in entry for entry in kodi.messages))

    def test_invalid_focus_delay_rejected(self):
        for delay in ("not-a-number", "nan", "inf", "-inf"):
            with self.subTest(delay=delay):
                kodi = FakeKodi()
                bridge = coordinator(kodi)
                self.assertFalse(bridge.on_notification(
                    SENDER, MESSAGE, notification(focus_packet(delay=delay))))
                self.assertIsNone(bridge.scheduler.latest)
                self.assertEqual(kodi.commands, [])

    def test_focus_recovers_other_owner_only_when_player_idle(self):
        kodi = FakeKodi(has_media=False)
        bridge = coordinator(kodi)
        bridge.scheduler.ownership.external_playback()

        self.assertTrue(
            bridge.on_notification(SENDER, MESSAGE, notification(focus_packet())))
        self.assertEqual(bridge.scheduler.ownership.owner, "NONE")
        self.assertEqual(bridge.scheduler.latest.identity, "imdb:tt123")
        self.assertTrue(any(
            "FOCUS_OWNER_RECOVERED" in entry for entry in kodi.messages))

    def test_focus_does_not_preempt_active_other_playback(self):
        kodi = FakeKodi(has_media=True)
        bridge = coordinator(kodi)
        bridge.scheduler.ownership.external_playback()

        self.assertFalse(
            bridge.on_notification(SENDER, MESSAGE, notification(focus_packet())))
        self.assertEqual(bridge.scheduler.ownership.owner, "OTHER")
        self.assertIsNone(bridge.scheduler.latest)
        self.assertEqual(kodi.commands, [])

    def test_visibility_error_fails_closed(self):
        kodi = FakeKodi(visibility_error=True)
        bridge = coordinator(kodi)
        bridge.scheduler.ownership.external_playback()

        self.assertFalse(
            bridge.on_notification(SENDER, MESSAGE, notification(focus_packet())))
        self.assertEqual(bridge.scheduler.ownership.owner, "OTHER")
        self.assertIsNone(bridge.scheduler.latest)


if __name__ == "__main__":
    unittest.main()
