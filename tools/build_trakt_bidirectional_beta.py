"""Create-only, deterministic bounded Beta built on the verified current Stable ZIPs."""
import hashlib,json,tempfile,zipfile,stat
from pathlib import Path
from xml.etree import ElementTree as ET
from build_test_channel import zip_tree
ROOT=Path(__file__).resolve().parents[1]
BASE_VERSIONS={'service.actweeter':'0.4.99','plugin.video.xstream-pro':'1.1.2.42'}
BETA_VERSIONS={'service.actweeter':'0.4.100~beta2','plugin.video.xstream-pro':'1.1.2.43~beta3'}
CHANGED={
 'service.actweeter':['resources/lib/trakt_outbox.py','resources/lib/trakt_resume_bridge.py','resources/lib/trakt_watched_reconcile.py'],
 'plugin.video.xstream-pro':['resources/lib/trakt_local_journal.py','resources/lib/trakt_live_consumer.py','resources/lib/trakt_auto_routes.py']}


def build(output):
 out=Path(output)
 if out.exists():raise FileExistsError(out)
 out.mkdir(parents=True)
 result={}
 for aid,old in BASE_VERSIONS.items():
  path=ROOT/'repo'/aid/(aid+'-'+old+'.zip')
  version=BETA_VERSIONS[aid];new=out/(aid+'-'+version+'.zip')
  if aid == 'service.actweeter':
   # Service Beta2 is already published: retain its exact immutable bytes.
   existing=ROOT/'docs/testing/repo/service.actweeter/service.actweeter-0.4.100~beta2.zip'
   if hashlib.sha256(existing.read_bytes()).hexdigest() != '3e37f4c8d5e2872322640af72ba2f6b3a2defc0fbdef282b3d3e334d21c837ed':
    raise ValueError('published Service Beta2 hash changed')
   new.write_bytes(existing.read_bytes())
   result[aid]={'version':version,'sha256':hashlib.sha256(new.read_bytes()).hexdigest()}
   continue
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder)
   with zipfile.ZipFile(path) as original:
    if original.testzip() is not None:raise ValueError('baseline CRC invalid')
    for info in original.infolist():
     if not info.filename.startswith(aid+'/') or '..' in Path(info.filename).parts:
      raise ValueError('unsafe baseline name')
     if info.is_dir():continue
     dest=root/info.filename;dest.parent.mkdir(parents=True,exist_ok=True)
     dest.write_bytes(original.read(info))
   tree=root/aid
   for rel in CHANGED[aid]:
    src=ROOT/('source/0.4.32/addons/service.actweeter' if aid=='service.actweeter' else 'source/0.4.32/third_party/xstream')
    src=src/rel if aid=='service.actweeter' else src/Path(rel).name
    if not src.is_file():raise ValueError('missing source '+str(src))
    (tree/rel).write_bytes(src.read_bytes())
   manifest=tree/'addon.xml'; xml=ET.parse(manifest).getroot()
   if xml.get('version')!=old:raise ValueError('wrong baseline')
   xml.set('version',version)
   if aid=='service.actweeter':
    for node in xml.findall("requires/import[@addon='plugin.video.xstream-pro']"):
     node.set('version','1.1.2.42')
   ET.ElementTree(xml).write(manifest,encoding='utf-8',xml_declaration=True)
   for py in tree.rglob('*.py'):
    compile(py.read_bytes(),str(py),'exec')
   zip_tree(tree,new,aid)
  with zipfile.ZipFile(new) as z:
   if z.testzip() is not None:raise ValueError('bad output ZIP')
  result[aid]={'version':version,'sha256':hashlib.sha256(new.read_bytes()).hexdigest()}
 return result

if __name__=='__main__':
 import sys
 print(json.dumps(build(sys.argv[1]),indent=2))
