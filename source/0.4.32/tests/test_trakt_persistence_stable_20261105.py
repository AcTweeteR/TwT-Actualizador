"""Promotion cannot edit historical packages or provider function payload."""
import hashlib,json,sys,tempfile,unittest,zipfile
from pathlib import Path
from xml.etree import ElementTree as E
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
import promote_trakt_persistence_stable as release
import verify_current_stable

class TraktStablePromotionTests(unittest.TestCase):
 def test_two_rebuilds_are_identical_and_touch_only_metadata(self):
  with tempfile.TemporaryDirectory() as tmp:
   a,b=Path(tmp)/'a',Path(tmp)/'b'
   x=release.build(a);y=release.build(b)
   self.assertEqual(x,y)
   self.assertEqual((a/'repo/addons.xml').read_bytes(),(b/'repo/addons.xml').read_bytes())
   self.assertEqual((a/'repo/addons.xml').read_bytes(),(ROOT/'manifests/archive/trakt-bidirectional-prior-stable-addons-20261105.xml').read_bytes())
   target=a/'repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.42.zip'
   self.assertEqual(target.read_bytes(),(ROOT/'repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.42.zip').read_bytes())
   beta=ROOT/'docs/testing/repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.42~beta1.zip'
   with zipfile.ZipFile(beta) as before,zipfile.ZipFile(target) as after:
    self.assertEqual(before.namelist(),after.namelist())
    self.assertEqual(after.testzip(),None)
    changed=[name for name in before.namelist() if before.read(name)!=after.read(name)]
    self.assertEqual(changed,['plugin.video.xstream-pro/addon.xml'])
    for name in ('resources/lib/trakt.py','resources/lib/tmdb_routes.py'):
     f='plugin.video.xstream-pro/'+name
     self.assertEqual(before.read(f),after.read(f))
    self.assertEqual(E.fromstring(after.read('plugin.video.xstream-pro/addon.xml')).get('version'),'1.1.2.42')
   with self.assertRaises(FileExistsError):release.build(a)
 def test_stable_integrity_matches_manifest(self):
  manifest=json.loads((ROOT/'manifests/actweeter-stable-trakt-persistence-20261105.json').read_text())
  self.assertEqual(verify_current_stable.verify(),__import__('json').loads((ROOT/'manifests/actweeter-stable-trakt-bidirectional-20261105.json').read_text())['index_sha256'])
  self.assertFalse(manifest['runtime_tvos_verified'])

if __name__=='__main__':unittest.main()
