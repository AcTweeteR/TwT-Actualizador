"""Build immutable Beta6: exact-ID indexed Continue movie lookup, preserving fallback."""
from pathlib import Path
from build_test_channel import zip_tree
import tempfile,zipfile,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1]
AID='plugin.video.xstream-pro'
OLD='1.1.2.44~beta5'
NEW='1.1.2.44~beta6'
SOURCE=ROOT/'docs/testing/repo'/AID/(AID+'-'+OLD+'.zip')
HELPER='''def _indexed_continue_movies(g, pnum, entries):
    """Use active provider's immutable indexed byte ranges for exact resume IDs.

    No fuzzy identity, no restored progress writes, and no full catalog decode
    for the common case where every local movie resume URL has a stream ID.
    Recheck hidden/adult categories; any unavailable index falls back intact.
    """
    try:
        from provider_catalog_index import CatalogIndex
        creds = g['_get_credentials_for_profile'](pnum)
        host, user, password = (creds.get(key, '') for key in
                                ('xtream_url', 'xtream_username', 'xtream_password'))
        if not all((host, user, password)):
            return None
        chosen = [entry for entry in entries if entry.get('stype') == 'movie']
        if not chosen:
            return None
        identifiers = []
        for entry in chosen:
            found = re.search(r'/([0-9]+)\\.[A-Za-z0-9]+$',
                              urlparse(entry.get('url', '')).path)
            if not found:
                return None  # preserve old title fallback for legacy resumes
            identifiers.append(found.group(1))
        path = g['_cache_path']('xtream_streams_movie', profile_num=pnum)
        index = CatalogIndex(path, '%s|%s|%s' % (host, user, password),
                             pnum, 'movie', trace=g.get('_performance'))
        categories = g['_get_cached_xtream_categories'](
            host, user, password, 'movie', profile_num=pnum)
        blocked = set(g['_get_hidden_subcats']('movie', pnum))
        blocked.update(str(c.get('category_id', '')) for c in categories
                       if g['_is_adult_category'](c.get('category_name', '')))
        hidden = set(g['_get_hidden_items']('movie', pnum))
        found_items = []
        for sid in dict.fromkeys(identifiers):
            matched, more = index.page(provider_id=sid, browse=True,
                                       blocked_categories=blocked,
                                       hidden_ids=hidden, limit=2)
            if more or len(matched) > 1:
                return None
            found_items.extend(matched)
        return found_items, (host, user, password)
    except Exception as exc:
        trace = g.get('_performance')
        if trace is not None:
            trace.count('continue.index.fallback')
        g['_log']('Continue indexed movie lookup fallback: %s' % type(exc).__name__)
        return None


'''

def build(output):
 output=Path(output)
 if output.exists():raise FileExistsError('create-only output')
 with tempfile.TemporaryDirectory() as tmp:
  for entry in zipfile.ZipFile(SOURCE).infolist():
   if '..' in Path(entry.filename).parts or not entry.filename.startswith(AID+'/'):raise ValueError('unsafe zip')
   if entry.is_dir():continue
   f=Path(tmp)/entry.filename;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(zipfile.ZipFile(SOURCE).read(entry))
  tree=Path(tmp)/AID
  p=tree/'resources/lib/premium_routes.py';s=p.read_text()
  marker='def _trakt_continue_extra(g, stype, seen, limit):'
  if s.count(marker)!=1:raise ValueError('missing merge point')
  s=s.replace(marker,HELPER+marker)
  before='''            if kind not in catalogs:
                catalogs[kind] = catalog(g, kind, pnum)
'''
  after='''            if kind not in catalogs:
                # Preserve full-catalog fallback whenever a verified source
                # index is unavailable or legacy resume URLs lack exact IDs.
                accelerated = (_indexed_continue_movies(g, pnum, entries)
                               if kind == 'movie' else None)
                catalogs[kind] = accelerated if accelerated is not None else catalog(g, kind, pnum)
'''
  if s.count(before)!=1:raise ValueError('unexpected resume implementation')
  s=s.replace(before,after,1);p.write_text(s)
  addon=tree/'addon.xml';xml=addon.read_text();needle='version="'+OLD+'"'
  if xml.count(needle)!=1:raise ValueError('unexpected version')
  addon.write_text(xml.replace(needle,'version="'+NEW+'"',1))
  for file in tree.rglob('*.py'):compile(file.read_bytes(),str(file),'exec')
  zip_tree(tree,output,AID)
 with zipfile.ZipFile(SOURCE) as before,zipfile.ZipFile(output) as after:
  modified=[name for name in before.namelist() if not name.endswith('/') and before.read(name)!=after.read(name)]
  assert set(modified)=={AID+'/addon.xml',AID+'/resources/lib/premium_routes.py'},modified
  assert after.testzip() is None
 return {'version':NEW,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'changed':modified}
if __name__=='__main__':print(json.dumps(build(sys.argv[1]),indent=2))
