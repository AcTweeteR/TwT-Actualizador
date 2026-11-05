"""Stable XStream is the tested Beta bytes, changing only release metadata."""
import hashlib,sys,tempfile,unittest,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
import promote_trakt_recommendations_stable as promoter
import verify_current_stable

class TraktRecommendationsStablePromotionTests(unittest.TestCase):
 def test_pinned_source_and_current_release_match(self):
  index=verify_current_stable.verify()
  self.assertEqual(index,promoter.PROMOTED)
  self.assertEqual(hashlib.sha256((ROOT/'manifests/archive/trakt-recommendations-prior-stable-addons-20261105.xml').read_bytes()).hexdigest(),promoter.PREVIOUS)

 def test_create_only_rebuild_matches_published_release(self):
  with tempfile.TemporaryDirectory() as tmp:
   output=Path(tmp)/'rebuild'
   result=promoter.build(output)
   self.assertEqual(result['index_sha256'],promoter.PROMOTED)
   self.assertEqual((output/'repo/addons.xml').read_bytes(),(ROOT/'repo/addons.xml').read_bytes())
   self.assertEqual((output/'manifest.json').read_bytes(),(ROOT/'manifests/actweeter-stable-trakt-recommendations-20261105.json').read_bytes())
   rebuilt=output/'repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.45.zip'
   published=ROOT/'repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.45.zip'
   self.assertEqual(rebuilt.read_bytes(),published.read_bytes())
   source=ROOT/'docs/testing/repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.44~beta5.zip'
   with zipfile.ZipFile(source) as old,zipfile.ZipFile(rebuilt) as new:
    self.assertEqual(old.namelist(),new.namelist())
    self.assertEqual(new.testzip(),None)
    self.assertEqual([name for name in old.namelist() if not name.endswith('/') and old.read(name)!=new.read(name)],['plugin.video.xstream-pro/addon.xml'])
    self.assertEqual(ET.fromstring(new.read('plugin.video.xstream-pro/addon.xml')).get('version'),'1.1.2.45')
   with self.assertRaises(FileExistsError):promoter.build(output)

if __name__=='__main__':unittest.main()
