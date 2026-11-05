#!/usr/bin/env python3
"""Create-only Stable from exact 2026-11-05 validated Beta packages."""
from pathlib import Path
from xml.etree import ElementTree as ET
import hashlib, json, sys, zipfile
ROOT=Path(__file__).resolve().parents[1]
VERSIONS={'service.actweeter':('0.4.101~beta1','0.4.101'),'plugin.video.xstream-pro':('1.1.2.44~beta4','1.1.2.44')}
EXPECTED={'service.actweeter':'a493c9aeb7b1f0ebd109fcd60e57eeded75333c2769bfe806ab54ead79972fdf','plugin.video.xstream-pro':'a77401fa119e40f581f9ef09afb1796fdedb1a2f539a2664d3dd9f0be0c583e2'}
PRIOR='8663fe695a935c9718310bffbe501b3b0b6c04532bddb787ff51daad8c2e7eea'
def sha(data):return hashlib.sha256(data).hexdigest()
def build(out):
 out=Path(out)
 if out.exists():raise FileExistsError(out)
 old=(ROOT/'repo/addons.xml').read_bytes()
 if sha(old)!=PRIOR:raise ValueError('Stable changed; refusing stale release')
 if hashlib.md5(old).hexdigest()!=(ROOT/'repo/addons.xml.md5').read_text().strip():raise ValueError('prior md5')
 root=ET.fromstring(old)
 for aid,(beta,stable) in VERSIONS.items():
  source=ROOT/'docs/testing/repo'/aid/f'{aid}-{beta}.zip'
  if sha(source.read_bytes())!=EXPECTED[aid]:raise ValueError('Beta hash mismatch: '+aid)
  with zipfile.ZipFile(source) as z:
   if z.testzip() is not None:raise ValueError('bad Beta CRC')
   assert ET.fromstring(z.read(aid+'/addon.xml')).get('version')==beta
  node=root.find(f"addon[@id='{aid}']")
  if node is None or tuple(map(int,stable.split('.')))<=tuple(map(int,node.get('version').split('.'))):raise ValueError('not an upgrade')
 out.mkdir(parents=True)
 for aid,(beta,stable) in VERSIONS.items():
  source=ROOT/'docs/testing/repo'/aid/f'{aid}-{beta}.zip'
  target=out/'repo'/aid/f'{aid}-{stable}.zip'
  published=ROOT/'repo'/aid/target.name
  if published.exists() or published.is_symlink():raise FileExistsError('refusing overwrite '+str(published))
  target.parent.mkdir(parents=True,exist_ok=True)
  with zipfile.ZipFile(source) as before,zipfile.ZipFile(target,'x') as after:
   for info in before.infolist():
    data=before.read(info)
    if info.filename==aid+'/addon.xml':
     prior=f'version="{beta}"'.encode()
     if data.count(prior)!=1:raise ValueError('unexpected manifest version')
     data=data.replace(prior,f'version="{stable}"'.encode(),1)
     addon=ET.fromstring(data)
     if aid=='service.actweeter':
      dep=addon.find("requires/import[@addon='plugin.video.xstream-pro']")
      if dep is None:raise ValueError('missing XStream dependency')
      dep.set('version','1.1.2.44')
      data=ET.tostring(addon,encoding='utf-8',xml_declaration=True)
    after.writestr(info,data)
  with zipfile.ZipFile(target) as z:
   if z.testzip() is not None:raise ValueError('bad stable CRC')
  node=root.find(f"addon[@id='{aid}']");idx=list(root).index(node);root.remove(node);root.insert(idx,addon)
 index=ET.tostring(root,encoding='utf-8',xml_declaration=True)+b'\n'
 (out/'repo/addons.xml').write_bytes(index)
 (out/'repo/addons.xml.md5').write_text(hashlib.md5(index).hexdigest()+'\n')
 entries=[]
 for node in root:
  aid,version=node.get('id'),node.get('version');rel=f'repo/{aid}/{aid}-{version}.zip'
  path=out/rel if aid in VERSIONS else ROOT/rel
  if not path.is_file():raise ValueError('missing '+rel)
  with zipfile.ZipFile(path) as z:
   if z.testzip() is not None:raise ValueError('bad package '+rel)
   addon=ET.fromstring(z.read(aid+'/addon.xml'))
   if addon.get('version')!=version:raise ValueError('manifest version differs '+aid)
   for dep in addon.findall('requires/import'):
    if '~beta' in (dep.get('version') or ''):raise ValueError('Beta dependency')
  entries.append({'id':aid,'version':version,'path':rel,'sha256':sha(path.read_bytes())})
 manifest={'release':'actweeter-stable-trakt-continue-20261105','channel':'stable','release_date':'2026-11-05','previous_index_sha256':PRIOR,'index_sha256':sha(index),'index_md5':hashlib.md5(index).hexdigest(),'source_beta_sha256':EXPECTED,'addons':entries,'assets':[],'runtime_tvos_verified':False,'runtime_lenovo_verified':False}
 (out/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
 return manifest
if __name__=='__main__':
 print(json.dumps(build(sys.argv[1]),indent=2))
