"""Create-only Stable 1.1.2.45 from tested Trakt recommendation Beta5."""
from pathlib import Path
from xml.etree import ElementTree as ET
import hashlib,json,sys,zipfile
ROOT=Path(__file__).resolve().parents[1]
AID='plugin.video.xstream-pro'
BETA='1.1.2.44~beta5'
STABLE='1.1.2.45'
BETA_SHA='f8b310ed35b77d54d7353b93520a96e5d49e4d812212b88c0622dcd855dcce46'
PREVIOUS='87a926cf7a33bbb7676d26ca93e826c26a2e2e50b0fd438a89badf41559a259c'
PROMOTED='006ab64927071d2f185fa7ec6003b47e4ec3a56618891b1aa273f8cd9dc2e858'
def sha(data):return hashlib.sha256(data).hexdigest()
def build(output):
 output=Path(output)
 if output.exists():raise FileExistsError('create-only output already exists')
 current=(ROOT/'repo/addons.xml').read_bytes()
 if sha(current) not in (PREVIOUS,PROMOTED,sha((ROOT/'manifests/archive/trakt-recommendations-stable-addons-20261105.xml').read_bytes()),json.loads((ROOT/'manifests/actweeter-stable-tv-recent-20261106.json').read_text())['index_sha256']):raise ValueError('unexpected active Stable release')
 if hashlib.md5(current).hexdigest()!=(ROOT/'repo/addons.xml.md5').read_text().strip():raise ValueError('current checksum mismatch')
 # Historical predecessor must be archived verbatim so the promotion is
 # independently reproducible after Stable advances to this release.
 before=(ROOT/'manifests/archive/trakt-recommendations-prior-stable-addons-20261105.xml').read_bytes()
 if sha(before)!=PREVIOUS:raise ValueError('historical prior Stable index mismatch')
 beta=ROOT/'docs/testing/repo'/AID/f'{AID}-{BETA}.zip'
 if sha(beta.read_bytes())!=BETA_SHA:raise ValueError('unexpected candidate source')
 root=ET.fromstring(before)
 previous=root.find(f"addon[@id='{AID}']")
 if previous is None or previous.get('version')!='1.1.2.44':raise ValueError('unexpected XStream version')
 output.mkdir(parents=True)
 target=output/'repo'/AID/f'{AID}-{STABLE}.zip';target.parent.mkdir(parents=True)
 with zipfile.ZipFile(beta) as source,zipfile.ZipFile(target,'x') as result:
  if source.testzip() is not None:raise ValueError('source invalid')
  for entry in source.infolist():
   data=source.read(entry)
   if entry.filename==AID+'/addon.xml':
    old=f'version="{BETA}"'.encode()
    if data.count(old)!=1:raise ValueError('version metadata ambiguous')
    data=data.replace(old,f'version="{STABLE}"'.encode(),1)
    addon=ET.fromstring(data)
    if addon.get('id')!=AID or addon.get('version')!=STABLE:raise ValueError('inconsistent addon metadata')
   result.writestr(entry,data)
 if zipfile.ZipFile(target).testzip() is not None:raise ValueError('candidate CRC failed')
 i=list(root).index(previous);root.remove(previous);root.insert(i,addon)
 # Service requirement must remain satisfied without changing Service itself.
 service=root.find("addon[@id='service.actweeter']")
 if service is None or service.get('version')!='0.4.101':raise ValueError('unexpected service dependency')
 dep=service.find("requires/import[@addon='plugin.video.xstream-pro']")
 if dep is None or tuple(map(int,(dep.get('version') or '').split('.')))>tuple(map(int,STABLE.split('.'))):raise ValueError('dependency not satisfied')
 index=ET.tostring(root,encoding='utf-8',xml_declaration=True)+b'\n'
 (output/'repo/addons.xml').write_bytes(index)
 (output/'repo/addons.xml.md5').write_text(hashlib.md5(index).hexdigest()+'\n')
 entries=[]
 for node in root:
  aid,version=node.get('id'),node.get('version')
  rel=f'repo/{aid}/{aid}-{version}.zip'
  f=target if aid==AID else ROOT/rel
  if not f.is_file():raise ValueError('missing dependency '+rel)
  with zipfile.ZipFile(f) as archive:
   if archive.testzip() is not None:raise ValueError('bad dependency '+rel)
   if ET.fromstring(archive.read(aid+'/addon.xml')).get('version')!=version:raise ValueError('package version mismatch')
  entries.append({'id':aid,'version':version,'path':rel,'sha256':sha(f.read_bytes())})
 manifest={'release':'actweeter-stable-trakt-recommendations-20261105','channel':'stable','release_date':'2026-11-05','previous_index_sha256':PREVIOUS,'index_sha256':sha(index),'index_md5':hashlib.md5(index).hexdigest(),'source_beta_sha256':BETA_SHA,'addons':entries,'assets':[],'runtime_tvos_verified':False,'runtime_lenovo_verified':False}
 (output/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
 return manifest
if __name__=='__main__':print(json.dumps(build(sys.argv[1]),indent=2))
