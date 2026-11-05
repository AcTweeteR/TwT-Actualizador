"""Create-only, byte-preserving Beta4 from verified Beta3 for missing provider index."""
from pathlib import Path
import hashlib,zipfile,tempfile,json
from xml.etree import ElementTree as ET
from build_test_channel import zip_tree
ROOT=Path(__file__).resolve().parents[1]
AID='plugin.video.xstream-pro'
OLD='1.1.2.43~beta3'; NEW='1.1.2.43~beta4'
SOURCE=ROOT/'docs/testing/repo'/AID/(AID+'-'+OLD+'.zip')

def build(output):
 output=Path(output)
 if output.exists():raise FileExistsError(output)
 with tempfile.TemporaryDirectory() as folder:
  stage=Path(folder)
  with zipfile.ZipFile(SOURCE) as z:
   if z.testzip() is not None:raise ValueError('bad beta3')
   for info in z.infolist():
    if '..' in Path(info.filename).parts or not info.filename.startswith(AID+'/'):raise ValueError('unsafe archive')
    if info.is_dir():continue
    p=stage/info.filename;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(info))
  tree=stage/AID
  f=tree/'resources/lib/addon.py';s=f.read_text()
  old='''    # Never fetch or rebuild the provider inventory inside a widget directory
    # request: catalogue refresh owns that work and updates this cache.
    cache = _load_provider_availability_cache()
    if not cache or not any((cache.get(kind) or {}).get("titles") for kind in ("movie", "tv")):
        return []
'''
  new='''    # Fresh installations (notably tvOS) may have no availability index yet.
    # Recover using the same verified catalog builder as normal TMDb routes.
    # Never return unverified Trakt titles as playable provider items.
    cache = _load_provider_availability_cache()
    if not cache or not any((cache.get(kind) or {}).get("titles") for kind in ("movie", "tv")):
        _log("Trakt recommendations: missing provider index; rebuilding")
        cache = _refresh_provider_availability_cache_after_profile_load(show_progress=False)
    if not cache or not any((cache.get(kind) or {}).get("titles") for kind in ("movie", "tv")):
        _log("Trakt recommendations: no verified provider inventory")
        return []
'''
  if s.count(old)!=1:raise ValueError('unexpected filter source')
  f.write_text(s.replace(old,new))
  addon=tree/'addon.xml';raw=addon.read_text();needle='version="'+OLD+'"'
  if raw.count(needle)!=1:raise ValueError('unexpected version')
  addon.write_text(raw.replace(needle,'version="'+NEW+'"',1))
  for py in tree.rglob('*.py'):compile(py.read_bytes(),str(py),'exec')
  zip_tree(tree,output,AID)
 with zipfile.ZipFile(SOURCE) as before,zipfile.ZipFile(output) as after:
  changed=[n for n in before.namelist() if not n.endswith('/') and before.read(n)!=after.read(n)]
  assert set(changed)=={AID+'/addon.xml',AID+'/resources/lib/addon.py'},changed
  assert after.testzip() is None
 return {'version':NEW,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'changed':changed}
if __name__=='__main__':
 import sys
 print(json.dumps(build(sys.argv[1]),indent=2))
