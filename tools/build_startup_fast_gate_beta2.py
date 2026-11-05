"""Create-only Service Beta2: suppress repeated Home startup work after verified initialization."""
import hashlib,json,tempfile,zipfile,sys
from pathlib import Path
from build_test_channel import zip_tree
ROOT=Path(__file__).resolve().parents[1]
AID='service.actweeter';OLD='0.4.101~beta1';NEW='0.4.101~beta2'
SOURCE=ROOT/'docs/testing/repo'/AID/(AID+'-'+OLD+'.zip')

def build(output):
 output=Path(output)
 if output.exists():raise FileExistsError('create only')
 with tempfile.TemporaryDirectory() as tmp:
  with zipfile.ZipFile(SOURCE) as old:
   if old.testzip():raise ValueError('corrupt Beta')
   for info in old.infolist():
    if '..' in Path(info.filename).parts or not info.filename.startswith(AID+'/'):raise ValueError('unsafe path')
    if info.is_dir():continue
    target=Path(tmp)/info.filename;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(old.read(info))
  tree=Path(tmp)/AID
  p=tree/'setup.py';s=p.read_text()
  old='''        xbmc.log("[AcTweeteR] FIRST_RUN_FLOW status=entered", xbmc.LOGINFO)
        # Claim the whole startup UI flow after the intro gate; repeated Home
'''
  new='''        # A verified, unchanged Home layout needs no second startup flow.
        # Home can be activated repeatedly while the Kodi process remains up;
        # avoid starting nested skin inspections/first-run prompts each time.
        # Repair and newly installed skin versions still use the existing
        # migration validation path (including explicit Repair Interface).
        if not resume and window.getProperty("AcTweeteR.InterfaceReady") == "1":
            try:
                current_skin = xbmcaddon.Addon('skin.actweeter').getAddonInfo('version')
                if window.getProperty('AcTweeteR.ReadySkinVersion') == current_skin:
                    xbmc.log('[AcTweeteR] FIRST_RUN_FLOW status=fast_reused', xbmc.LOGDEBUG)
                    return
            except (RuntimeError, AttributeError, KeyError):
                pass
        xbmc.log("[AcTweeteR] FIRST_RUN_FLOW status=entered", xbmc.LOGINFO)
        # Claim the whole startup UI flow after the intro gate; repeated Home
'''
  if s.count(old)!=1:raise ValueError('first run gate source changed')
  s=s.replace(old,new,1)
  # Only record an exact skin version after a verified generated layout. The
  # current fast reuse branch is never entered while the version differs.
  old='''    if not interface_preparation_needed(migration_due, generated_ready):
        window.setProperty("AcTweeteR.InterfaceReady", "1")
        return "CURRENT"
'''
  new='''    if not interface_preparation_needed(migration_due, generated_ready):
        window.setProperty("AcTweeteR.InterfaceReady", "1")
        window.setProperty("AcTweeteR.ReadySkinVersion", active_skin_version)
        return "CURRENT"
'''
  if s.count(old)!=1:raise ValueError('reuse guard source changed')
  s=s.replace(old,new,1)
  old='''    window.setProperty(marker_name, marker)
    xbmc.log("[AcTweeteR] INTERFACE_LAYOUT_UPDATE status=verified target=%d" %
'''
  new='''    window.setProperty(marker_name, marker)
    window.setProperty("AcTweeteR.ReadySkinVersion", active_skin_version)
    xbmc.log("[AcTweeteR] INTERFACE_LAYOUT_UPDATE status=verified target=%d" %
'''
  if s.count(old)!=1:raise ValueError('successful migration source changed')
  s=s.replace(old,new,1)
  p.write_text(s)
  addon=tree/'addon.xml';s=addon.read_text();v='version="'+OLD+'"'
  if s.count(v)!=1:raise ValueError('addon version changed')
  addon.write_text(s.replace(v,'version="'+NEW+'"',1))
  for source in tree.rglob('*.py'):compile(source.read_bytes(),str(source),'exec')
  zip_tree(tree,output,AID)
 with zipfile.ZipFile(SOURCE) as old,zipfile.ZipFile(output) as new:
  changed=[n for n in old.namelist() if not n.endswith('/') and old.read(n)!=new.read(n)]
  assert set(changed)=={AID+'/addon.xml',AID+'/setup.py'},changed
  assert new.testzip() is None
 return {'version':NEW,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'changed':changed}
if __name__=='__main__':print(json.dumps(build(sys.argv[1]),indent=2))
