"""Create-only Beta5: recommendations rebuild their catalog regardless of TMDb provider-only preference."""
import hashlib, json, tempfile, zipfile
from pathlib import Path
from build_test_channel import zip_tree
ROOT=Path(__file__).resolve().parents[1]
AID='plugin.video.xstream-pro'
PREV='1.1.2.44~beta4'
NEXT='1.1.2.44~beta5'
SOURCE=ROOT/'docs/testing/repo'/AID/(AID+'-'+PREV+'.zip')

def build(output):
 output=Path(output)
 if output.exists():raise FileExistsError(output)
 with tempfile.TemporaryDirectory() as tmp:
  with zipfile.ZipFile(SOURCE) as old:
   if old.testzip() is not None:raise ValueError('corrupt source')
   for entry in old.infolist():
    if '..' in Path(entry.filename).parts or not entry.filename.startswith(AID+'/'):raise ValueError('unsafe entry')
    if entry.is_dir():continue
    dest=Path(tmp)/entry.filename;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(old.read(entry))
  base=Path(tmp)/AID
  f=base/'resources/lib/addon.py';code=f.read_text()
  old='''        cache = _refresh_provider_availability_cache_after_profile_load(show_progress=False)
    if not cache or not any((cache.get(kind) or {}).get("titles") for kind in ("movie", "tv")):
        _log("Trakt recommendations: no verified provider inventory")
'''
  new='''        # Recommendations MUST build the provider index even when the
        # independent tmdb_provider_only_available setting is disabled.
        # That preference gates TMDb browsing, not Trakt recommendations.
        try:
            cache = _rebuild_provider_availability_cache(show_progress=False)
        except Exception as exc:
            _log("Trakt recommendations: provider rebuild unavailable (%s)" % type(exc).__name__)
            cache = None
    if not cache or not any((cache.get(kind) or {}).get("titles") for kind in ("movie", "tv")):
        _log("Trakt recommendations: no verified provider inventory")
'''
  if code.count(old)!=1:raise ValueError('old filtering code changed')
  code=code.replace(old,new,1)
  f.write_text(code)
  addon=base/'addon.xml';xml=addon.read_text();needle='version="'+PREV+'"'
  if xml.count(needle)!=1:raise ValueError('unexpected addon version')
  addon.write_text(xml.replace(needle,'version="'+NEXT+'"',1))
  for file in base.rglob('*.py'):compile(file.read_bytes(),str(file),'exec')
  zip_tree(base,output,AID)
 with zipfile.ZipFile(SOURCE) as before,zipfile.ZipFile(output) as after:
  changes=[n for n in before.namelist() if not n.endswith('/') and before.read(n)!=after.read(n)]
  assert set(changes)=={AID+'/addon.xml',AID+'/resources/lib/addon.py'},changes
  assert after.testzip() is None
 return {'version':NEXT,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'changed':changes}
if __name__=='__main__':
 import sys
 print(json.dumps(build(sys.argv[1]),indent=2))
