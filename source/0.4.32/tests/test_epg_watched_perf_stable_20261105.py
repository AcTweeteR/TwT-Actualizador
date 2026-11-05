"""Stable is a create-only reproducible promotion of exactly two Beta add-ons."""
import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
import promote_epg_watched_perf_stable as release  # noqa: E402
import verify_current_stable as verifier  # noqa: E402


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class PromotedStableTests(unittest.TestCase):
    def test_current_stable_version_pair_is_greater_than_old(self):
        stable={x.get('id'):x.get('version') for x in
                ET.parse(ROOT/'repo/addons.xml').getroot()}
        self.assertEqual(stable['skin.actweeter'],'1.2.41')
        self.assertEqual(stable['plugin.video.xstream-pro'],'1.1.2.45')
        self.assertEqual(stable['service.actweeter'],'0.4.101')
        archived={x.get('id'):x.get('version') for x in
                  ET.parse(ROOT/'manifests/archive/priority-stable-addons-20261104.xml').getroot()}
        self.assertEqual(archived['skin.actweeter'],'1.2.40')
        self.assertEqual(archived['plugin.video.xstream-pro'],'1.1.2.40')
        self.assertEqual(archived['service.actweeter'],'0.4.98')

    def test_stable_manifest_fails_closed_on_current_hash_mismatch(self):
        self.assertEqual(verifier.verify(),json.loads(verifier.MANIFEST.read_text())['index_sha256'])
        with tempfile.TemporaryDirectory() as td:
            bad=json.loads(verifier.MANIFEST.read_text())
            bad['index_sha256']='0'*64
            m=Path(td)/'invalid.json'
            m.write_text(json.dumps(bad))
            with self.assertRaisesRegex(ValueError,'Stable index differs'):
                verifier.verify(manifest_path=m)

    def test_promoter_rebuilds_identically_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as td:
            dest=Path(td)/'candidate'
            meta=release.build(dest)
            self.assertEqual(meta['index_sha256'],release.PROMOTED_INDEX)
            self.assertEqual((dest/'manifest.json').read_bytes(),
                             (ROOT/'manifests/actweeter-stable-epg-watched-performance-20261105.json').read_bytes())
            self.assertEqual((dest/'repo/addons.xml').read_bytes(),
                             (ROOT/'manifests/archive/epg-watched-perf-stable-addons-20261105.xml').read_bytes())
            for addon,(_,version) in release.VERSIONS.items():
                rel=Path('repo')/addon/(addon+'-'+version+'.zip')
                self.assertEqual((dest/rel).read_bytes(),(ROOT/rel).read_bytes())
            with self.assertRaisesRegex(ValueError,'overwrite'):
                release.build(dest)

    def test_manifest_pins_exact_beta_and_preserves_all_unchanged_addons(self):
        manifest=json.loads((ROOT/'manifests/actweeter-stable-epg-watched-performance-20261105.json').read_text())
        beta=json.loads(release.BETA_MANIFEST.read_text())
        self.assertEqual(manifest['beta_index_sha256'],beta['testing_index_sha256'])
        self.assertEqual(manifest['previous_index_sha256'],release.PREVIOUS_INDEX)
        before={x.get('id'):x.get('version') for x in ET.parse(
            ROOT/'manifests/archive/priority-stable-addons-20261104.xml').getroot()}
        after={x.get('id'):x.get('version') for x in ET.parse(
            ROOT/'manifests/archive/epg-watched-perf-stable-addons-20261105.xml').getroot()}
        self.assertEqual(set(before),set(after))
        self.assertEqual(
            {a for a in after if after[a]!=before[a]},
            {'skin.actweeter','plugin.video.xstream-pro'})
        for entry in manifest['addons']:
            addon=entry['id']
            if addon not in release.VERSIONS:
                self.assertEqual(before[addon],entry['version'])
                self.assertEqual(digest(ROOT/entry['path']),entry['sha256'])
        self.assertFalse(manifest['runtime_lenovo_verified'])

    def test_stable_xstream_has_watched_refresh_and_provider_fast_path(self):
        archive=ROOT/'repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.41.zip'
        with zipfile.ZipFile(archive) as z:
            self.assertIsNone(z.testzip())
            refresh=z.read('plugin.video.xstream-pro/resources/lib/watch_ui_refresh.py')
            self.assertIn(b'AcTweeteR.WatchedRefresh',refresh)
            self.assertIn(b'CancelAlarm(AcTweeteRWatchedRefresh',refresh)
            news=z.read('plugin.video.xstream-pro/resources/lib/series_changes.py')
            self.assertIn(b'Premium.CollectionsRefresh',news)
            premium=z.read('plugin.video.xstream-pro/resources/lib/premium_routes.py')
            self.assertIn(b'budget = [0, 0] if fast_widget else [4, 1]',premium)
            self.assertEqual(ET.fromstring(z.read(
                'plugin.video.xstream-pro/addon.xml')).get('version'),'1.1.2.41')

    def test_stable_skin_contains_epg_titles_and_touch_safe_mode(self):
        p=ROOT/'repo/skin.actweeter/skin.actweeter-1.2.41.zip'
        with zipfile.ZipFile(p) as z:
            self.assertIsNone(z.testzip())
            skin=ET.fromstring(z.read('skin.actweeter/addon.xml'))
            self.assertEqual(skin.get('version'),'1.2.41')
            views=z.read('skin.actweeter/1080i/IncludesViews.xml')
            self.assertIn(b'<width>90%</width>',views)
            touch=z.read('skin.actweeter/1080i/IncludesTouchMode.xml')
            self.assertIn(b'Skin.HasSetting(AcTweeteRTouchMode)',touch)
            self.assertTrue(z.read('skin.actweeter/changelog-1.2.41.txt'))

    def test_previous_stable_release_contents_do_not_change(self):
        old=json.loads((ROOT/'manifests/actweeter-stable-priority-20261104.json').read_text())
        self.assertEqual(digest(ROOT/'manifests/archive/priority-stable-addons-20261104.xml'),
                         old['index_sha256'])
        for entry in old['addons']:
            self.assertEqual(digest(ROOT/entry['path']),entry['sha256'])

if __name__=='__main__':
    unittest.main()
