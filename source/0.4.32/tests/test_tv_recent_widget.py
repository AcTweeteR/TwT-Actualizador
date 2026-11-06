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
from interface_layout import LAYOUT_VERSION, source_documents, generated_rows


class HistoryTests(unittest.TestCase):
    def test_mru_move_to_front_dedupe_and_fifo_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tv.json"
            for number in range(1, 24):
                self.assertTrue(record(path, number))
            self.assertEqual(read_history(path), list(range(23, 4, -1)))
            self.assertTrue(record(path, 9))
            self.assertEqual(read_history(path)[:3], [9, 23, 22])
            self.assertEqual(len(read_history(path)), MAX_CHANNELS)
            self.assertEqual(read_history(path).count(9), 1)
            before = path.read_bytes()
            self.assertFalse(record(path, 9))
            self.assertEqual(path.read_bytes(), before)
            self.assertTrue(record(path, 42))
            self.assertEqual(read_history(path)[0], 42)
            self.assertEqual(len(read_history(path)), 19)

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
    def test_sources_have_tv_second_no_expand_and_19_cap(self):
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

    def test_tv_focus_uses_same_landscape_frame_as_other_widgets(self):
        root = ET.parse(ROOT / "addons/skin.actweeter/1080i/IncludesHomeWidgets.xml").getroot()
        layout = root.find(".//include[@name='widget_layout_tv_recent']")
        focused = layout.find("focusedlayout[@condition='Control.HasFocus($PARAM[widgetid])']")
        self.assertIsNotNone(focused)
        group = focused.find('control')
        self.assertEqual([child.tag for child in group][:2], ['include', 'control'])
        self.assertEqual(group[0].get('content'), 'AcTweeteRTVRecentCard')
        border = group[1]
        self.assertEqual(border.get('type'), 'group')
        edges = border.findall('control')
        self.assertEqual(len(edges), 4)
        self.assertEqual([edge.findtext('texture') for edge in edges],
                         ['colors/color_white.png'] * 4)
        self.assertEqual([edge.findtext('width') for edge in edges],
                         ['418','418','4','4'])
        self.assertEqual([edge.findtext('height') for edge in edges],
                         ['4','4','242','242'])
        self.assertEqual(edges[1].findtext('top'),'238')
        self.assertEqual(edges[3].findtext('left'),'414')
        card = root.find(".//include[@name='AcTweeteRTVRecentCard']")
        self.assertEqual(card.findtext("control/control[@type='image']/bordersize"), '8')
        texture = card.find("control/control[@type='image']/texture")
        self.assertEqual(texture.get('diffuse'), 'home/home_matte3.png')
        self.assertEqual(card.find("control/control[@type='image']/aspectratio").get(
            'scalediffuse'), 'false')
        self.assertIsNotNone(layout.find(
            "focusedlayout[@condition='!Control.HasFocus($PARAM[widgetid])']"))

    def test_live_tv_refresh_waits_until_home_without_reloading_skin(self):
        import ast
        import threading
        import uuid
        source = (ROOT / "addons/service.actweeter/service.py").read_text()
        tree = ast.parse(source)
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name in ('_tv_recent_invalidate', '_tv_recent_refresh_loop')]
        class FakeMonitor:
            def abortRequested(self):
                return False
            def waitForAbort(self, delay):
                return delay == 1
        class Kodi:
            LOGWARNING = 2
            LOGINFO = 1
            def __init__(self, home):
                self.home = home
                self.calls = []
            def Monitor(self):
                return FakeMonitor()
            def executebuiltin(self, value, wait):
                self.calls.append((value, wait))
            def getCondVisibility(self, condition):
                self.calls.append((condition, None))
                return self.home
            def log(self, value, level):
                self.calls.append((value, level))
        class FakeThread:
            created = []
            def __init__(self, target, args, name, daemon):
                self.target = target
                self.args = args
                self.name = name
                self.daemon = daemon
                self.created.append(self)
            def start(self):
                pass
            def is_alive(self):
                return True
        stub = Kodi(False)
        event = threading.Event()
        env = {'uuid': uuid, 'xbmc': stub, 'threading': threading,
               '_TV_RECENT_REFRESH_PENDING': event,
               '_TV_RECENT_REFRESH_GUARD': threading.Lock(),
               '_TV_RECENT_REFRESH_WORKER': None}
        env['threading'] = type('FakeThreading', (), {'Thread': FakeThread})
        exec(compile(ast.Module(body=functions, type_ignores=[]),
                     'service.py', 'exec'), env)
        self.assertTrue(env['_tv_recent_invalidate'](stub))
        self.assertTrue(event.is_set())
        self.assertEqual(len(FakeThread.created), 1)
        self.assertTrue(FakeThread.created[0].daemon)
        env['_tv_recent_refresh_loop'](stub)
        self.assertTrue(event.is_set())
        self.assertFalse(any('Container.Refresh' in x for x, _ in stub.calls))
        stub.home = True
        env['_tv_recent_refresh_loop'](stub)
        self.assertFalse(event.is_set())
        commands = [cmd for cmd, wait in stub.calls if wait is False]
        self.assertEqual(len([x for x in commands if x.startswith(
            'SetProperty(AcTweeteR.TVRecentRefresh,')]), 1)
        self.assertEqual(len([x for x in commands if 'Container.Refresh' in x]), 1)
        self.assertFalse(any('ReloadSkin' in x or 'SkinShortcuts' in x
                             for x in commands))

    def test_skin_card_and_template_current_epg(self):
        includes = ET.parse(ROOT / "addons/skin.actweeter/1080i/IncludesHomeWidgets.xml")
        self.assertIsNotNone(includes.find(".//include[@name='widget_layout_tv_recent']"))
        self.assertIsNotNone(includes.find(".//include[@name='AcTweeteRTVRecentCard']"))
        self.assertIn("ListItem.Property(AcTweeteR.TVNow)",
                      (ROOT / "addons/skin.actweeter/1080i/IncludesHomeWidgets.xml").read_text())
        template = (ROOT / "addons/skin.actweeter/shortcuts/template.xml").read_text()
        self.assertIn('value="widget_layout_tv_recent"', template)
        self.assertIn("widgetPath.startswith('plugin://service.actweeter/?action=tv_recent')", template)

    def test_native_generated_layout_accepts_only_first_party_tv_route(self):
        import xml.etree.ElementTree as ET
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'skin.xml'
            root = ET.Element('includes')
            inc = ET.SubElement(root, 'include', {'name': 'skinshortcuts-template-Widgets'})
            tv = ET.SubElement(inc, 'include', {'content': 'widget_base'})
            ET.SubElement(tv, 'param', {'name': 'widgetName', 'value': 'TV'})
            ET.SubElement(tv, 'param', {'name': 'widgetPath', 'value':
                'plugin://service.actweeter/?action=tv_recent&reload=1'})
            p.write_bytes(ET.tostring(root))
            rows = generated_rows(p)['Widgets']
            self.assertEqual(len(rows), 1)
            self.assertTrue(rows[0]['provider_only'])
            self.assertTrue(rows[0]['expansion_ready'])
            self.assertFalse(rows[0]['expandable'])
            tv.find("param[@name='widgetPath']").set('value',
                'plugin://service.actweeter/?action=tv_recent&url=https://unknown.example/')
            p.write_bytes(ET.tostring(root))
            self.assertFalse(generated_rows(p)['Widgets'][0]['provider_only'])

    def test_generated_template_excludes_inactive_false_widget_branch(self):
        # Real Skin Shortcuts generates both conditional widget_base branches.
        # The unused branch must not fail expandable-property verification.
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'generated.xml'
            root = ET.Element('includes')
            inc = ET.SubElement(root, 'include',
                                {'name': 'skinshortcuts-template-Widgets'})
            route = ('plugin://plugin.video.xstream-pro/?mode=premium&'
                     'view=continue&stype=both&actweeter_expand=1&limit=19')
            for condition, expansion in [('true', 'true'), ('false', None)]:
                node = ET.SubElement(inc, 'include',
                                     {'content': 'widget_base', 'condition': condition})
                ET.SubElement(node, 'param', name='widgetName', value='Continuar viendo')
                ET.SubElement(node, 'param', name='widgetPath', value=route)
                if expansion is not None:
                    ET.SubElement(node, 'param', name='widgetExpandable', value=expansion)
            tv = ET.SubElement(inc, 'include',
                               {'content': 'widget_base', 'condition': 'true'})
            ET.SubElement(tv, 'param', name='widgetName', value='TV')
            ET.SubElement(tv, 'param', name='widgetPath',
                          value='plugin://service.actweeter/?action=tv_recent&reload=1')
            p.write_bytes(ET.tostring(root))
            rows = generated_rows(p)['Widgets']
            self.assertEqual([r['label'] for r in rows], ['Continuar viendo', 'TV'])
            self.assertTrue(all(r['expansion_ready'] for r in rows))
            self.assertFalse(rows[1]['expandable'])

    def test_service_does_not_write_vod_trakt_or_playlists(self):
        source = (ROOT / "addons/service.actweeter/resources/lib/tv_recent.py").read_text()
        self.assertNotIn("trakt", source.lower())
        self.assertNotIn("m3u", source.lower())
        self.assertNotIn("password", source.lower())


if __name__ == "__main__":
    unittest.main()
