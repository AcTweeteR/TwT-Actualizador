"""Fail-closed Kodi preview notification contracts; no Kodi runtime required."""

from __future__ import annotations

import base64
import json
import sys
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
    instance.clock = lambda: 100.0
    instance.delay_parser = float
    instance.session_id = "notification-test"
    instance.scheduler = LatestPreviewScheduler(PreviewOwnership())
    instance.wake = instance.scheduler.condition
    instance.requests = {}
    instance.item_data = {}
    instance.request_ids = {}
    instance._stop_owned = lambda request: None
    return instance


class PreviewNotificationTests(unittest.TestCase):
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
