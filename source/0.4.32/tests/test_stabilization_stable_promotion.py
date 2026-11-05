"""Create-only Stable 0.4.99 from pinned 0.4.99~beta4."""
import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
import promote_stabilization_stable as promotion
import verify_current_stable as verifier

class StabilizationStableTests(unittest.TestCase):
    def test_rebuild_is_reproducible_preserves_exact_functional_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=Path(tmp)/'one',Path(tmp)/'two'
            first=promotion.build(a)
            self.assertEqual(first,promotion.build(b))
            self.assertEqual((a/'repo/addons.xml').read_bytes(),(b/'repo/addons.xml').read_bytes())
            stable=a/'repo/service.actweeter/service.actweeter-0.4.99.zip'
            self.assertEqual(stable.read_bytes(),(b/'repo/service.actweeter/service.actweeter-0.4.99.zip').read_bytes())
            beta=ROOT/'docs/testing/repo/service.actweeter/service.actweeter-0.4.99~beta4.zip'
            with zipfile.ZipFile(beta) as source, zipfile.ZipFile(stable) as promoted:
                self.assertEqual(promoted.testzip(),None)
                self.assertEqual(set(promoted.namelist())-set(source.namelist()),{'service.actweeter/changelog-0.4.99.txt'})
                for name in source.namelist():
                    if name!='service.actweeter/addon.xml':
                        self.assertEqual(source.read(name),promoted.read(name),name)
                before=ET.fromstring(source.read('service.actweeter/addon.xml'))
                after=ET.fromstring(promoted.read('service.actweeter/addon.xml'))
                self.assertEqual((before.get('version'),after.get('version')),('0.4.99~beta4','0.4.99'))
                self.assertEqual(after.findtext("extension[@point='xbmc.addon.metadata']/news"),'changelog-0.4.99.txt')
            self.assertEqual(hashlib.sha256(stable.read_bytes()).hexdigest(),first['addons'][2]['sha256'])
            expected={item['id']:item['version'] for item in first['addons']}
            self.assertEqual(expected['skin.actweeter'],'1.2.41')
            self.assertEqual(expected['plugin.video.xstream-pro'],'1.1.2.41')
            with self.assertRaises(FileExistsError): promotion.build(a)

    def test_current_published_release_matches_immutable_manifest(self):
        self.assertEqual(verifier.verify(),
                         json.loads(verifier.MANIFEST.read_text())['index_sha256'])

if __name__=='__main__': unittest.main()
