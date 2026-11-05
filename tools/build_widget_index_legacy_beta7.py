"""Create-only Beta7: resolve legacy title-only movie resume entries by validated index search."""
from pathlib import Path
from build_test_channel import zip_tree
import tempfile,zipfile,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1]
AID='plugin.video.xstream-pro';OLD='1.1.2.44~beta6';NEW='1.1.2.44~beta7'
SOURCE=ROOT/'docs/testing/repo'/AID/(AID+'-'+OLD+'.zip')
def build(output):
 output=Path(output)
 if output.exists():raise FileExistsError('create only')
 with tempfile.TemporaryDirectory() as tmp:
  with zipfile.ZipFile(SOURCE) as src:
   for member in src.infolist():
    if '..' in Path(member.filename).parts or not member.filename.startswith(AID+'/'):raise ValueError('unsafe')
    if member.is_dir():continue
    f=Path(tmp)/member.filename;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(src.read(member))
  tree=Path(tmp)/AID;p=tree/'resources/lib/premium_routes.py';s=p.read_text()
  old='''        identifiers = []
        for entry in chosen:
            found = re.search(r'/([0-9]+)\\.[A-Za-z0-9]+$',
                              urlparse(entry.get('url', '')).path)
            if not found:
                return None  # preserve old title fallback for legacy resumes
            identifiers.append(found.group(1))
'''
  new='''        # A single legacy title-only entry must not make all exact-ID
        # movies decode the entire 26k-item provider catalogue again.
        # Unknown or ambiguous names still use the complete legacy resolver.
'''
  if s.count(old)!=1:raise ValueError('unexpected indexed helper prefix')
  s=s.replace(old,new,1)
  old='''        found_items = []
        for sid in dict.fromkeys(identifiers):
            matched, more = index.page(provider_id=sid, browse=True,
                                       blocked_categories=blocked,
                                       hidden_ids=hidden, limit=2)
            if more or len(matched) > 1:
                return None
            found_items.extend(matched)
        return found_items, (host, user, password)
'''
  new='''        found_items = []
        unique_ids = set()
        for entry in chosen:
            found = re.search(r'/([0-9]+)\\.[A-Za-z0-9]+$',
                              urlparse(entry.get('url', '')).path)
            if found:
                matched, more = index.page(provider_id=found.group(1), browse=True,
                                           blocked_categories=blocked,
                                           hidden_ids=hidden, limit=2)
                if more or len(matched) > 1:
                    return None
            else:
                # Same strict identity predicate as the full-catalog path.
                # The SQLite search narrows candidates without changing
                # title matching, sort order or provider eligibility.
                title = entry.get('title') or entry.get('name', '')
                if not title:
                    return None
                candidates = index.search(title, blocked_categories=blocked,
                                          hidden_ids=hidden, limit=100)
                matched = [item for item in candidates
                           if item.get('name') in (title, entry.get('name'))
                           or entry.get('name', '').startswith(item.get('name', '') + ' - ')]
                if len(matched) != 1:
                    return None
            for item in matched:
                sid = provider_id(item, 'movie')
                if sid not in unique_ids:
                    unique_ids.add(sid)
                    found_items.append(item)
        return found_items, (host, user, password)
'''
  if s.count(old)!=1:raise ValueError('unexpected indexed helper suffix')
  s=s.replace(old,new,1);p.write_text(s)
  addon=tree/'addon.xml';xml=addon.read_text();old='version="'+OLD+'"'
  if xml.count(old)!=1:raise ValueError('version')
  addon.write_text(xml.replace(old,'version="'+NEW+'"',1))
  for f in tree.rglob('*.py'):compile(f.read_bytes(),str(f),'exec')
  zip_tree(tree,output,AID)
 with zipfile.ZipFile(SOURCE) as old,zipfile.ZipFile(output) as new:
  changes=[n for n in old.namelist() if not n.endswith('/') and old.read(n)!=new.read(n)]
  assert set(changes)=={AID+'/addon.xml',AID+'/resources/lib/premium_routes.py'},changes
  assert new.testzip() is None
 return {'version':NEW,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'changed':changes}
if __name__=='__main__':print(json.dumps(build(sys.argv[1]),indent=2))
