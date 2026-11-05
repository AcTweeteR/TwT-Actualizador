"""Create-only Beta8: avoid full 26k VOD JSON decoding in Trakt Continue overlay."""
from pathlib import Path
import hashlib,json,tempfile,zipfile,sys
from build_test_channel import zip_tree
ROOT=Path(__file__).resolve().parents[1]
AID='plugin.video.xstream-pro';OLD='1.1.2.44~beta7';NEW='1.1.2.44~beta8'
SOURCE=ROOT/'docs/testing/repo'/AID/(AID+'-'+OLD+'.zip')
HELPER='''def _indexed_remote_movie_ids(g, pnum, provider_ids):
    """Lookup verified remote movie IDs from active catalog byte ranges.

    Never infer playback from title and never expose a hidden category. The
    existing provider list decoder remains the fallback for absent indexes.
    """
    if not provider_ids:
        return {}
    try:
        from provider_catalog_index import CatalogIndex
        creds = g['_get_credentials_for_profile'](pnum)
        host, user, password = (creds.get(key, '') for key in
                                ('xtream_url', 'xtream_username', 'xtream_password'))
        if not all((host, user, password)):
            return None
        cache_path = g['_cache_path']('xtream_streams_movie', profile_num=pnum)
        index = CatalogIndex(cache_path, '%s|%s|%s' % (host, user, password),
                             pnum, 'movie', trace=g.get('_performance'))
        categories = g['_get_cached_xtream_categories'](
            host, user, password, 'movie', profile_num=pnum)
        blocked = set(g['_get_hidden_subcats']('movie', pnum))
        blocked.update(str(category.get('category_id', '')) for category in categories
                       if g['_is_adult_category'](category.get('category_name', '')))
        hidden = set(g['_get_hidden_items']('movie', pnum))
        resolved = {}
        for sid in provider_ids:
            entries, more = index.page(provider_id=sid, browse=True,
                                       blocked_categories=blocked,
                                       hidden_ids=hidden, limit=2)
            if more or len(entries) > 1:
                return None
            if entries:
                resolved[sid] = entries[0]
        return resolved
    except Exception as exc:
        g['_log']('Trakt overlay indexed provider lookup fallback: %s' % type(exc).__name__)
        return None


'''

def build(output):
 output=Path(output)
 if output.exists():raise FileExistsError('create only')
 with tempfile.TemporaryDirectory() as tmp:
  with zipfile.ZipFile(SOURCE) as before:
   if before.testzip() is not None:raise ValueError('bad source')
   for member in before.infolist():
    if '..' in Path(member.filename).parts or not member.filename.startswith(AID+'/'):raise ValueError('unsafe source')
    if member.is_dir():continue
    f=Path(tmp)/member.filename;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(before.read(member))
  tree=Path(tmp)/AID;p=tree/'resources/lib/premium_routes.py';s=p.read_text()
  marker='def _trakt_continue_extra(g, stype, seen, limit):'
  if s.count(marker)!=1:raise ValueError('missing insertion')
  s=s.replace(marker,HELPER+marker)
  old='''        # Match exact TMDb IDs against the existing provider's ES metadata
'''
  new='''        if not pending:
            # E.g. Series with no paused remote episodes: do not load movie
            # metadata or the entire VOD catalog just to return an empty row.
            return []
        # Match exact TMDb IDs against the existing provider's ES metadata
'''
  if s.count(old)!=1:raise ValueError('unexpected overlay body')
  s=s.replace(old,new,1)
  old='''        catalog = g['_cache_load']('xtream_streams_movie') or {}
        by_sid = {str(entry.get('stream_id')): entry
                  for entry in catalog.get('_data', []) if isinstance(entry, dict)}
'''
  new='''        requested = {matched[str(item.get('tmdb_id'))][0]
                     for item in pending if item.get('tmdb_type') == 'movie'
                     and matched.get(str(item.get('tmdb_id')))}
        by_sid = _indexed_remote_movie_ids(g, pnum, sorted(requested))
        if by_sid is None:
            # Older installs lacking a verified index retain their original
            # behavior. Index creation is never synchronous in a widget.
            catalog = g['_cache_load']('xtream_streams_movie') or {}
            by_sid = {str(entry.get('stream_id')): entry
                      for entry in catalog.get('_data', []) if isinstance(entry, dict)}
'''
  if s.count(old)!=1:raise ValueError('missing lookup replacement')
  s=s.replace(old,new,1);p.write_text(s)
  addon=tree/'addon.xml';xml=addon.read_text();old='version="'+OLD+'"'
  if xml.count(old)!=1:raise ValueError('unexpected version')
  addon.write_text(xml.replace(old,'version="'+NEW+'"',1))
  for file in tree.rglob('*.py'):compile(file.read_bytes(),str(file),'exec')
  zip_tree(tree,output,AID)
 with zipfile.ZipFile(SOURCE) as old,zipfile.ZipFile(output) as new:
  modified=[n for n in old.namelist() if not n.endswith('/') and old.read(n)!=new.read(n)]
  assert set(modified)=={AID+'/addon.xml',AID+'/resources/lib/premium_routes.py'},modified
  assert new.testzip() is None
 return {'version':NEW,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'changed':modified}
if __name__=='__main__':print(json.dumps(build(sys.argv[1]),indent=2))
