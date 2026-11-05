"""Create-only Beta5 skin: reduce eager per-row artwork allocations on slower GPUs."""
from pathlib import Path
import hashlib,json,tempfile,zipfile,sys
from build_test_channel import zip_tree
ROOT=Path(__file__).resolve().parents[1]
AID='skin.actweeter';OLD='1.2.41~beta4';NEW='1.2.41~beta5'
SOURCE=ROOT/'docs/testing/repo'/AID/(AID+'-'+OLD+'.zip')

def patch(source):
 start=source.index('    <include name="widget_base_normal">')
 end=source.index('<include name="widget_base_categories">',start)
 part=source[start:end]
 if part.count('<preloaditems>5</preloaditems>')!=1:raise ValueError('unexpected normal widget preload')
 source=source[:start]+part.replace('<preloaditems>5</preloaditems>','<preloaditems>2</preloaditems>',1)+source[end:]
 start=source.index('<include name="widget_base_categories">')
 end=source.index('<include name="widget_base_content_normal">',start)
 part=source[start:end]
 if part.count('<preloaditems>5</preloaditems>')!=1:raise ValueError('unexpected category preload')
 return source[:start]+part.replace('<preloaditems>5</preloaditems>','<preloaditems>2</preloaditems>',1)+source[end:]

def build(output):
 output=Path(output)
 if output.exists():raise FileExistsError('create only')
 with tempfile.TemporaryDirectory() as tmp:
  with zipfile.ZipFile(SOURCE) as src:
   if src.testzip():raise ValueError('bad source CRC')
   for member in src.infolist():
    if '..' in Path(member.filename).parts or not member.filename.startswith(AID+'/'):raise ValueError('unsafe zip entry')
    if member.is_dir():continue
    path=Path(tmp)/member.filename;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(src.read(member))
  tree=Path(tmp)/AID
  file=tree/'1080i/IncludesHomeWidgets.xml';file.write_text(patch(file.read_text()))
  addon=tree/'addon.xml';s=addon.read_text();old='version="'+OLD+'"'
  if s.count(old)!=1:raise ValueError('unexpected addon version')
  addon.write_text(s.replace(old,'version="'+NEW+'"',1))
  import xml.etree.ElementTree as ET
  for p in tree.rglob('*.xml'):ET.parse(p)
  zip_tree(tree,output,AID)
 with zipfile.ZipFile(SOURCE) as before,zipfile.ZipFile(output) as after:
  changed=[n for n in before.namelist() if not n.endswith('/') and before.read(n)!=after.read(n)]
  assert set(changed)=={AID+'/addon.xml',AID+'/1080i/IncludesHomeWidgets.xml'},changed
  assert after.testzip() is None
 return {'version':NEW,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'changed':changed}
if __name__=='__main__':print(json.dumps(build(sys.argv[1]),indent=2))
