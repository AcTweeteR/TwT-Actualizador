"""Immutable 21 Oct Stable contract, separate from historical 20 Oct Stable."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from build_stable_20261021 import (  # noqa: E402
    _sha, build, EXPECTED_INPUT_SHA256, BETA_VERSION, STABLE_VERSION, STABLE_NEWS,
)


class StableOctober21ReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = json.loads((ROOT / 'manifests/actweeter-stable-20261021.json').read_text())

    def test_20261021_manifest_and_retained_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            _skin, index, md5 = build(Path(tmp) / 'candidate')
            payload = index.read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), self.m['index_sha256'])
            self.assertEqual(hashlib.md5(payload).hexdigest(), self.m['index_md5'])
            self.assertEqual(md5.read_text().strip(), self.m['index_md5'])
            self.assertEqual([(x.get('id'), x.get('version')) for x in ET.fromstring(payload)],
                             [(a['id'], a['version']) for a in self.m['addons']])
        for addon in self.m['addons']:
            package = ROOT / addon['path']
            self.assertEqual(_sha(package), addon['sha256'])
            with zipfile.ZipFile(package) as archive:
                self.assertIsNone(archive.testzip())
                root = ET.fromstring(archive.read(addon['id'] + '/addon.xml'))
                self.assertEqual((root.get('id'), root.get('version')),
                                 (addon['id'], addon['version']))

    def test_reproducible_create_only_promotion(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'candidate'
            skin, index, md5 = build(target)
            expected_skin = next(a for a in self.m['addons'] if a['id'] == 'skin.actweeter')
            self.assertEqual(_sha(skin), expected_skin['sha256'])
            self.assertEqual(hashlib.sha256(index.read_bytes()).hexdigest(), self.m['index_sha256'])
            self.assertEqual(md5.read_text().strip(), self.m['index_md5'])
            with self.assertRaisesRegex(ValueError, 'refusing to overwrite'):
                build(target)

    def test_beta_skin_identical_except_stable_metadata_and_release_notes(self):
        beta = ROOT / 'docs/testing/repo/skin.actweeter' / f'skin.actweeter-{BETA_VERSION}.zip'
        stable = ROOT / 'repo/skin.actweeter' / f'skin.actweeter-{STABLE_VERSION}.zip'
        self.assertEqual(_sha(beta), EXPECTED_INPUT_SHA256['skin'])
        with zipfile.ZipFile(beta) as before, zipfile.ZipFile(stable) as after:
            first, second = set(before.namelist()), set(after.namelist())
            self.assertEqual(second - first, {'skin.actweeter/changelog-1.2.31.txt'})
            self.assertEqual(first - second, set())
            self.assertEqual(after.read('skin.actweeter/changelog-1.2.31.txt'), STABLE_NEWS)
            self.assertEqual([path for path in before.namelist()
                              if before.read(path) != after.read(path)],
                             ['skin.actweeter/addon.xml'])
            self.assertEqual(before.read('skin.actweeter/media/actweeter/expand_vertical.png'),
                             after.read('skin.actweeter/media/actweeter/expand_vertical.png'))

    def test_verified_service_xstream_and_historical_artifacts(self):
        for addon, version in [('service.actweeter', '0.4.52'),
                               ('plugin.video.xstream-pro', '1.1.2.15')]:
            name = f'{addon}-{version}.zip'
            self.assertEqual((ROOT / 'repo' / addon / name).read_bytes(),
                             (ROOT / 'docs/testing/repo' / addon / name).read_bytes())
        historical = json.loads((ROOT / 'manifests/unified-stable-20261020.json').read_text())
        self.assertEqual(self.m['previous_stable_index_sha256'], historical['index_sha256'])
        for addon in historical['addons']:
            path = ROOT / 'repo' / addon['id'] / f"{addon['id']}-{addon['version']}.zip"
            self.assertEqual(_sha(path), addon['sha256'])
        self.assertEqual(_sha(ROOT / 'repo/repository.actweeter/repository.actweeter-1.0.3.zip'),
                         EXPECTED_INPUT_SHA256['repository'])


if __name__ == '__main__':
    unittest.main()
