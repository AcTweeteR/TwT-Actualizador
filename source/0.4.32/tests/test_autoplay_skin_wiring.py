"""Contracts for the missing Beta10 selection-to-coordinator connection."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[3]
SKIN = ROOT / 'source/0.4.32/addons/skin.actweeter'
BASELINE = ROOT / 'docs/testing/repo/skin.actweeter/skin.actweeter-1.2.29~beta10.zip'


def include(filename, name):
    return ET.parse(SKIN / '1080i' / filename).getroot().find(
        "./include[@name='%s']" % name)


class AutoplaySkinWiringTests(unittest.TestCase):
    def check_focus(self, parent, setting):
        actions = [node for node in parent.findall('onfocus')
                   if 'preview_focus' in (node.text or '')]
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].text,
                         'RunScript(service.actweeter,preview_focus,$PARAM[widgetid],3)')
        condition = actions[0].get('condition')
        for gate in ('System.HasAddon(slyguy.trailers)',
                     'Skin.HasSetting(%s)' % setting,
                     'String.IsEqual(Skin.String(AutoYoutubeTrailer),true)',
                     '!String.IsEqual(Skin.String(trailersource),imdb)'):
            self.assertIn(gate, condition)
        # Register rows even if the first poster has no usable trailer/ID.
        self.assertNotIn('ListItem', condition)

    def test_spotlight_uses_its_own_focused_list(self):
        parent = include('IncludesBingie.xml', 'BingieSpotlightWidget').find('control')
        self.assertEqual(parent.get('id'), '$PARAM[widgetid]')
        self.check_focus(parent, 'SpotLightTrailers')

    def test_rows_register_movie_and_series_windows(self):
        parent = include('IncludesHomeWidgets.xml', 'WidgetBaseBingieIncludes')
        self.check_focus(parent, 'BingieAutoTrailer')
        action = next(n for n in parent.findall('onfocus') if 'preview_focus' in n.text)
        for window in ('Home', '11110', '11111'):
            self.assertIn('Window.IsActive(%s)' % window, action.get('condition'))

    def test_both_controls_cancel_their_own_container(self):
        parents = (include('IncludesBingie.xml', 'BingieSpotlightWidget').find('control'),
                   include('IncludesHomeWidgets.xml', 'WidgetBaseBingieIncludes'))
        for parent in parents:
            self.assertTrue(any(n.text == 'RunScript(service.actweeter,preview_cancel,$PARAM[widgetid])'
                                for n in parent.findall('onunfocus')))

    def test_all_preview_windows_cancel_on_exit(self):
        for filename in ('Home.xml', 'Custom_1110_TVShows_Hub.xml',
                         'Custom_1111_Movies_Hub.xml'):
            root = ET.parse(SKIN / '1080i' / filename).getroot()
            self.assertTrue(any(n.text == 'RunScript(service.actweeter,preview_exit)'
                                for n in root.findall('onunload')), filename)

    def test_manual_actions_and_navigation_unchanged_from_published_skin(self):
        with zipfile.ZipFile(BASELINE) as archive:
            for path in (SKIN / '1080i').glob('*.xml'):
                if path.name == 'script-skinshortcuts-includes.xml':
                    # The builder replaces this empty source stub with neutral defaults.
                    continue
                name = 'skin.actweeter/1080i/' + path.name
                before = ET.fromstring(archive.read(name))
                after = ET.parse(path).getroot()
                for tag in ('onclick', 'onup', 'ondown', 'onleft', 'onright', 'onback'):
                    self.assertEqual([ET.tostring(n) for n in before.iter(tag)],
                                     [ET.tostring(n) for n in after.iter(tag)],
                                     (path.name, tag))

    def test_published_baseline_exposes_the_missing_wiring(self):
        with zipfile.ZipFile(BASELINE) as archive:
            for filename in ('IncludesBingie.xml', 'IncludesHomeWidgets.xml'):
                root = ET.fromstring(archive.read('skin.actweeter/1080i/' + filename))
                self.assertFalse(any('preview_focus' in (n.text or '')
                                     for n in root.iter('onfocus')), filename)

    def test_requires_current_service_and_preserves_optional_slyguy(self):
        root = ET.parse(SKIN / 'addon.xml').getroot()
        self.assertEqual(root.find("./requires/import[@addon='service.actweeter']").get('version'),
                         '0.4.39')
        self.assertIsNone(root.find("./requires/import[@addon='slyguy.trailers']"))


if __name__ == '__main__':
    unittest.main()
