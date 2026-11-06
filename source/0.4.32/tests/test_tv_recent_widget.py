"""TV MRU widget: ID-only history, EPG, profile migration and skin contracts."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addons/service.actweeter/resources/lib"))
from tv_recent import (MAX_CHANNELS, channel_from_item, channel_catalog,
                       current_tv_channel, read_history, record, tv_rows)
from interface_layout import LAYOUT_VERSION, source_documents


class HistoryTests(unittest.TestCase):
    def test_mru_move_to_front_dedupe_and_fifo_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tv.json"
            for number in range(1, 24):
                self.assertTrue(record(path, number))
            self.assertEqual(read_history(path), list(range(23, 3, -1)))
            self.assertTrue(record(path, 9))
            self.assertEqual(read_history(path)[:3], [9, 23, 22])
            self.assertEqual(len(read_history(path)), MAX_CHANNELS)
            self.assertEqual(read_history(path).count(9), 1)
            before = path.read_bytes()
            self.assertFalse(record(path, 9))
            self.assertEqual(path.read_bytes(), before)
            self.assertTrue(record(path, 42))
            self.assertEqual(read_history(path)[0], 42)
            self.assertEqual(len(read_history(path)), 20)

    def test_invalid_inputs_and_corrupt_profile_are_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tv.json"
            self.assertEqual(read_history(path), [])
            for value in ("abc", "-1", "", True, None, 0, "1.2"):
                self.assertFalse(record(path, value))
            path.write_text("{invalid")
            self.assertEqual(read_history(path), [])
            self.assertTrue(record(path, 12))
            self.assertEqual(read_history(path), [12])
            path.write_text(json.dumps({"version": 1,
                            "channels": [9, 9, "8", "garbage", 8, 7]}))
            self.assertEqual(read_history(path), [9, 8, 7])
            target = Path(directory) / "target"
            target.write_text("unrelated")
            symlink = Path(directory) / "linked"
            symlink.symlink_to(target)
            self.assertFalse(record(symlink, 88))
            self.assertEqual(target.read_text(), "unrelated")

    def test_only_real_tv_channels_count(self):
        self.assertEqual(channel_from_item({"type": "channel", "id": 312}), 312)
        self.assertEqual(channel_from_item({"type": "channel", "channelid": "45"}), 45)
        for item in (None, [], {"type": "movie", "id": 312},
                     {"type": "channel", "id": -1}, {"id": 42}):
            self.assertIsNone(channel_from_item(item))

    def test_player_getitem_tv_only(self):
        class Kodi:
            def __init__(self, item):
                self.item = item
            def executeJSONRPC(self, request):
                assert json.loads(request)["method"] == "Player.GetItem"
                return json.dumps({"result": {"item": self.item}})
        self.assertEqual(current_tv_channel(Kodi({"type": "channel", "id": 28})), 28)
        self.assertIsNone(current_tv_channel(Kodi({"type": "movie", "id": 28})))


class TVDirectoryTests(unittest.TestCase):
    def test_batched_channel_epg_and_channel_logo(self):
        calls = []
        def rpc(method, params=None):
            calls.append((method, params))
            if method == "PVR.GetChannelGroups":
                return {"channelgroups": [{"channelgroupid": 10}]}
            if method == "PVR.GetChannels":
                return {"channels": [
                    {"channelid": 24, "channel": "Canal 24", "icon": "image://24",
                     "broadcastnow": {"title": "Informativos"}},
                    {"channelid": 30, "channel": "Canal 30", "thumbnail": "image://30"},
                    {"channelid": 60, "channel": "Radio", "channeltype": "radio"}]}
            return {}
        data = tv_rows([30, 24, 60, 999], rpc)
        self.assertEqual([row["id"] for row in data], [30, 24])
        self.assertEqual(data[0]["now"], "Sin información EPG")
        self.assertEqual(data[0]["icon"], "image://30")
        self.assertEqual(data[1]["now"], "Informativos")
        self.assertEqual(data[1]["icon"], "image://24")
        self.assertEqual([name for name, _ in calls].count("PVR.GetChannels"), 1)

    def test_no_epg_or_no_pvr_hides_unknown_channel(self):
        self.assertEqual(tv_rows([20], lambda m, p=None: {}), [])
        def rpc(method, params=None):
            if method == "PVR.GetChannelGroups":
                return {"channelgroups": [{"channelgroupid": 7}]}
            if method == "PVR.GetChannels":
                return {"channels": []}
            if method == "PVR.GetChannelDetails":
                return {"channeldetails": {"channel": "Uno", "icon": "logo"}}
            return {}
        self.assertEqual(tv_rows([20], rpc)[0]["name"], "Uno")


class WidgetWiringTests(unittest.TestCase):
    def test_sources_have_tv_second_no_expand_and_20_cap(self):
        self.assertEqual(LAYOUT_VERSION, 20)
        sources = source_documents(ROOT / "addons/skin.actweeter")
        for name in ("inicio-1", "10000-1"):
            root = ET.fromstring(sources[f"skin.actweeter-{name}.DATA.xml"])
            items = root.findall("shortcut")
            self.assertEqual([s.findtext("label") for s in items[:3]],
                             ["Continuar viendo", "TV", "Añadidas recientemente"])
            path = items[1].findtext("action")
            self.assertTrue(path.startswith("plugin://service.actweeter/?action=tv_recent&"))
            self.assertNotIn("actweeter_expand", path)
            self.assertNotIn("limit=19", path)

    def test_skin_card_and_template_current_epg(self):
        includes = ET.parse(ROOT / "addons/skin.actweeter/1080i/IncludesHomeWidgets.xml")
        self.assertIsNotNone(includes.find(".//include[@name='widget_layout_tv_recent']"))
        self.assertIsNotNone(includes.find(".//include[@name='AcTweeteRTVRecentCard']"))
        self.assertIn("ListItem.Property(AcTweeteR.TVNow)",
                      (ROOT / "addons/skin.actweeter/1080i/IncludesHomeWidgets.xml").read_text())
        template = (ROOT / "addons/skin.actweeter/shortcuts/template.xml").read_text()
        self.assertIn('value="widget_layout_tv_recent"', template)
        self.assertIn("widgetPath.startswith('plugin://service.actweeter/?action=tv_recent')", template)

    def test_service_does_not_write_vod_trakt_or_playlists(self):
        source = (ROOT / "addons/service.actweeter/resources/lib/tv_recent.py").read_text()
        self.assertNotIn("trakt", source.lower())
        self.assertNotIn("m3u", source.lower())
        self.assertNotIn("password", source.lower())


if __name__ == "__main__":
    unittest.main()
