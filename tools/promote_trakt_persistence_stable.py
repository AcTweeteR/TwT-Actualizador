"""Immutable Stable XStream 1.1.2.42 promotion from tested 1.1.2.42~beta1."""
import hashlib,json,zipfile,sys
from pathlib import Path
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
ADDON='plugin.video.xstream-pro'
BETA='1.1.2.42~beta1'
VERSION='1.1.2.42'
BETA_SHA='e7b50639ecea6e2a5b94747bbba368afdd37275af01aaa64823ba2400fe0c34d'
PREVIOUS_SHA='e05b34fc718a8ecf4b70894cdbbee5a59daf81e31d061c2a51b16d5be0cdb107'
RELEASE='actweeter-stable-trakt-persistence-20261105'

def sha(data):return hashlib.sha256(data).hexdigest()
def build(output):
 output=Path(output)
 if output.exists() or output.is_symlink():raise FileExistsError('Stable output exists')
 source=ROOT/'docs/testing/repo'/ADDON/f'{ADDON}-{BETA}.zip'
 if sha(source.read_bytes()) != BETA_SHA:raise ValueError('unverified Beta')
 previous=(ROOT/'repo/addons.xml').read_bytes()
 if sha(previous)!=PREVIOUS_SHA:
  previous=(ROOT/'manifests/archive/trakt-persistence-prior-stable-addons-20261105.xml').read_bytes()
  if sha(previous)!=PREVIOUS_SHA:raise ValueError('unverified predecessor Stable index')
 original=ET.fromstring(previous)
 old=original.find(f"addon[@id='{ADDON}']")
 if old is None or old.get('version')!='1.1.2.41':raise ValueError('wrong predecessor XStream')
 target=output/'repo'/ADDON/f'{ADDON}-{VERSION}.zip'
 target.parent.mkdir(parents=True)
 with zipfile.ZipFile(source) as before,zipfile.ZipFile(target,'x') as after:
  if before.testzip() is not None:raise ValueError('corrupt Beta ZIP')
  for entry in before.infolist():
   b=before.read(entry)
   if entry.filename==f'{ADDON}/addon.xml':
    needle=f'version="{BETA}"'.encode()
    if b.count(needle)!=1:raise ValueError('wrong Beta version')
    b=b.replace(needle,f'version="{VERSION}"'.encode(),1)
    addon=ET.fromstring(b)
   after.writestr(entry,b)
  after.testzip()
 if addon.get('id')!=ADDON or addon.get('version')!=VERSION:raise ValueError('wrong result identity')
 index=list(original).index(old);original.remove(old);original.insert(index,addon)
 serialized=ET.tostring(original,encoding='utf-8',xml_declaration=True)+b'\n'
 (output/'repo/addons.xml').write_bytes(serialized)
 (output/'repo/addons.xml.md5').write_text(hashlib.md5(serialized).hexdigest()+'\n')
 entries=[]
 for node in original:
  aid,ver=node.get('id'),node.get('version')
  f=target if aid==ADDON else ROOT/'repo'/aid/f'{aid}-{ver}.zip'
  if not f.is_file():raise ValueError('missing unchanged package')
  with zipfile.ZipFile(f) as z:
   if z.testzip() is not None:raise ValueError('bad unchanged package')
  entries.append({'id':aid,'version':ver,'path':f'repo/{aid}/{aid}-{ver}.zip','sha256':sha(f.read_bytes())})
 manifest={'release':RELEASE,'channel':'stable','release_date':'2026-11-05','source_beta_sha256':BETA_SHA,
           'previous_index_sha256':PREVIOUS_SHA,'index_sha256':sha(serialized),'index_md5':hashlib.md5(serialized).hexdigest(),
           'addons':entries,'assets':[],'runtime_tvos_verified':False}
 (output/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
 return manifest
if __name__=='__main__':
 if len(sys.argv)!=2:raise SystemExit('Usage: python tools/promote_trakt_persistence_stable.py OUTPUT_DIR')
 print(json.dumps(build(sys.argv[1]),indent=2))
