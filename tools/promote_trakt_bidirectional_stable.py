"""Create-only Stable 0.4.100 / XStream 1.1.2.43 from immutable Beta."""
from pathlib import Path
from xml.etree import ElementTree as ET
import hashlib,json,zipfile,sys
ROOT=Path(__file__).resolve().parents[1]
VERSIONS={'service.actweeter':('0.4.100~beta2','0.4.100'),'plugin.video.xstream-pro':('1.1.2.43~beta4','1.1.2.43')}
SOURCE_SHA={'service.actweeter':'3e37f4c8d5e2872322640af72ba2f6b3a2defc0fbdef282b3d3e334d21c837ed','plugin.video.xstream-pro':'666e5a7e43278f22b6dcfef72e08a8a80b22e815ad00cc9b7cf2bc8a8ddf2abc'}
PREVIOUS='manifests/archive/trakt-bidirectional-prior-stable-addons-20261105.xml'
def sha(b):return hashlib.sha256(b).hexdigest()
def build(out):
 out=Path(out)
 if out.exists():raise FileExistsError(out)
 out.mkdir(parents=True)
 previous=(ROOT/PREVIOUS).read_bytes()
 if sha(previous)!='52c89db406c9cc4d2890c8f7e962e811b7d6fc1209e2d05f51399df7f94b6a3a':raise ValueError('wrong predecessor index')
 feed=ET.fromstring(previous)
 for aid,(beta,stable) in VERSIONS.items():
  source=ROOT/'docs/testing/repo'/aid/(aid+'-'+beta+'.zip')
  if sha(source.read_bytes())!=SOURCE_SHA[aid]:raise ValueError('unverified Beta '+aid)
  dest=out/'repo'/aid/(aid+'-'+stable+'.zip');dest.parent.mkdir(parents=True)
  with zipfile.ZipFile(source) as before,zipfile.ZipFile(dest,'x') as after:
   if before.testzip() is not None:raise ValueError('bad Beta CRC')
   for info in before.infolist():
    data=before.read(info)
    if info.filename==aid+'/addon.xml':
     old=('version="'+beta+'"').encode();assert data.count(old)==1
     data=data.replace(old,('version="'+stable+'"').encode(),1)
     addon=ET.fromstring(data)
     if aid=='service.actweeter':
      for req in addon.findall("requires/import[@addon='plugin.video.xstream-pro']"):
       req.set('version','1.1.2.43')
      data=ET.tostring(addon,encoding='utf-8',xml_declaration=True)
    after.writestr(info,data)
  with zipfile.ZipFile(dest) as verified:
   if verified.testzip() is not None:raise ValueError("Stable CRC")
  node=feed.find("addon[@id='"+aid+"']")
  if node is None:raise ValueError('missing stable addon')
  i=list(feed).index(node);feed.remove(node);feed.insert(i,addon)
 index=ET.tostring(feed,encoding='utf-8',xml_declaration=True)+b'\n'
 (out/'repo/addons.xml').write_bytes(index)
 (out/'repo/addons.xml.md5').write_text(hashlib.md5(index).hexdigest()+'\n')
 entries=[]
 for node in feed:
  aid=node.get('id');ver=node.get('version');rel=f'repo/{aid}/{aid}-{ver}.zip'
  path=out/rel if aid in VERSIONS else ROOT/rel
  if not path.exists():raise ValueError('missing unchanged '+rel)
  with zipfile.ZipFile(path) as z:
   if z.testzip() is not None:raise ValueError('bad '+rel)
  entries.append({'id':aid,'version':ver,'path':rel,'sha256':sha(path.read_bytes())})
 manifest={'release':'actweeter-stable-trakt-bidirectional-20261105','channel':'stable','release_date':'2026-11-05','previous_index_sha256':sha(previous),'index_sha256':sha(index),'index_md5':hashlib.md5(index).hexdigest(),'source_beta_sha256':SOURCE_SHA,'addons':entries,'assets':[],'runtime_tvos_verified':False}
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
 return manifest
if __name__=='__main__':print(json.dumps(build(sys.argv[1]),indent=2))
