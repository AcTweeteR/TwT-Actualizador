"""Bound eager textures without changing widget IDs, routes or focus layout."""
import hashlib,zipfile,os,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
ADDON='skin.actweeter'
OLD=ROOT/'docs/testing/repo'/ADDON/(ADDON+'-1.2.41~beta4.zip')
NEW=ROOT/'docs/testing/repo'/ADDON/(ADDON+'-1.2.41~beta5.zip')
class LightweightSkinTests(unittest.TestCase):
 def test_only_preload_and_release_version_change(self):
  with zipfile.ZipFile(OLD) as old,zipfile.ZipFile(NEW) as new:
   before=old.read(ADDON+'/1080i/IncludesHomeWidgets.xml').decode()
   after=new.read(ADDON+'/1080i/IncludesHomeWidgets.xml').decode()
   self.assertEqual(before.count('<preloaditems>5</preloaditems>')-after.count('<preloaditems>5</preloaditems>'),2)
   self.assertEqual(after.count('<preloaditems>2</preloaditems>')-before.count('<preloaditems>2</preloaditems>'),2)
   self.assertEqual(after.replace('<preloaditems>2</preloaditems>','<preloaditems>5</preloaditems>'),before)
   changed=[n for n in old.namelist() if not n.endswith('/') and old.read(n)!=new.read(n)]
   self.assertEqual(set(changed),{ADDON+'/1080i/IncludesHomeWidgets.xml',ADDON+'/addon.xml'})
if __name__=='__main__':unittest.main()
