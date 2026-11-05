"""Create-only Beta: show authenticated Trakt playback alongside local ResumePoints."""
from pathlib import Path
import tempfile, zipfile, hashlib, json
from xml.etree import ElementTree as ET
from build_test_channel import zip_tree

ROOT = Path(__file__).resolve().parents[1]
AID = 'plugin.video.xstream-pro'
OLD = '1.1.2.44~beta3'
NEW = '1.1.2.44~beta4'
SOURCE = ROOT/'docs/testing/repo'/AID/(AID + '-' + OLD + '.zip')

def replace_one(data, old, new):
    if data.count(old) != 1:
        raise ValueError('unexpected XStream baseline')
    return data.replace(old, new, 1)

def build(output):
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    with tempfile.TemporaryDirectory() as folder:
        tree = Path(folder)/AID
        with zipfile.ZipFile(SOURCE) as archive:
            if archive.testzip() is not None:
                raise ValueError('bad Beta1')
            for member in archive.infolist():
                if '..' in Path(member.filename).parts or not member.filename.startswith(AID+'/'):
                    raise ValueError('unsafe archive')
                if member.is_dir():
                    continue
                path = Path(folder)/member.filename
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(archive.read(member))
        premium = tree/'resources/lib/premium_routes.py'
        s = premium.read_text()
        helper = '''def _trakt_continue_extra(g, stype, seen, limit):
    """Read-only remote-only cards when local URLs are unavailable.

    A remote percentage is NOT a duration or safe seek offset. Cards open the
    existing TMDb provider selector; local verified ResumePoints remain the
    only direct resume playback source. No writes, credentials or fuzzy joins.
    """
    if limit < 1 or stype not in ('movie', 'series', 'both'):
        return []
    try:
        import trakt
        if not trakt.authorized():
            return []
        if not g['_setup_tmdb_routes']():
            return []
        routes = g.get('_tmdb_routes')
        if routes is None:
            return []
        wanted = ('movies', 'episodes') if stype == 'both' else (
            ('movies',) if stype == 'movie' else ('episodes',))
        pending = []
        for media_kind in wanted:
            data = trakt.playback(media_kind, cached=True)
            for item in data.get('results', []):
                kind, tmdb_id = item.get('tmdb_type'), str(item.get('tmdb_id') or '')
                season, episode = str(item.get('season') or ''), str(item.get('episode') or '')
                raw = item.get('raw')
                if (kind not in ('movie', 'tv') or not tmdb_id.isdigit()
                        or not isinstance(raw, dict) or not isinstance(raw.get('progress'), (int, float))):
                    continue
                identifier = (kind, tmdb_id, season if kind == 'tv' else '',
                              episode if kind == 'tv' else '')
                if identifier in seen:
                    continue
                seen.add(identifier)
                pending.append(item)
        # Match exact TMDb IDs against the existing provider's ES metadata
        # cache. This cache is already populated by provider search and avoids
        # displaying Trakt's English-only synopsis or placeholder artwork.
        # Do not guess from a similar title or construct a playback URL.
        import glob
        import os
        from urllib.parse import urlparse
        base = g['xbmcvfs'].translatePath(g['addon'].getAddonInfo('profile'))
        pnum = str(g['pm'].active)
        matched = {}
        for path in glob.glob(os.path.join(base,
                'data_cache_p%s_premium_meta_movie_*_es.json' % pnum)):
            try:
                with open(path, encoding='utf-8') as stream:
                    cache = json.load(stream)
                meta = cache.get('data') or {}
                tmdb_id = str(meta.get('tmdb_id') or '')
                sid = os.path.basename(path).split('premium_meta_movie_', 1)[1].split('_es.json')[0]
                if (not tmdb_id.isdigit() or not sid.isdigit()
                        or cache.get('expires', 0) <= time.time()):
                    continue
                if tmdb_id in matched:
                    matched[tmdb_id] = None  # ambiguous ID: never auto-select
                else:
                    matched[tmdb_id] = (sid, meta)
            except (OSError, ValueError, TypeError, KeyError):
                continue
        catalog = g['_cache_load']('xtream_streams_movie') or {}
        by_sid = {str(entry.get('stream_id')): entry
                  for entry in catalog.get('_data', []) if isinstance(entry, dict)}
        pending = routes._hydrate_from_tmdb_meta_cache(pending)
        results = []
        remote_metadata_fetches = 0
        for item in pending[:limit]:
            tmdb_id = str(item.get('tmdb_id') or '')
            candidate = matched.get(tmdb_id) if item.get('tmdb_type') == 'movie' else None
            if candidate and candidate[0] in by_sid:
                sid, meta = candidate
                provider = by_sid[sid]
                # The provider metadata is already keyed to a verified TMDb
                # ID, and the same stream ID must exist in this profile.
                data = dict(meta)
                data['title'] = data.get('title') or provider.get('name') or item.get('title') or ''
                data['plot'] = data.get('plot') or provider.get('plot') or ''
                data['poster_url'] = data.get('poster_url') or provider.get('stream_icon') or ''
                data['fanart_url'] = data.get('fanart_url') or provider.get('backdrop_path') or ''
                li = listitem(g, provider, 'movie', data, profile_num=pnum)
                url = g['build_url']({'mode':'premium','view':'play','stype':'movie',
                                      'id':sid,'profile_num':pnum})
                li.setProperty('XStream.ProviderMatched', 'true')
                li.setProperty('XStream.TraktProgress', str(item['raw']['progress']))
                li.setProperty('path', url)
                folder = False
            else:
                # An exact Trakt TMDb ID is sufficient to retrieve its Spanish
                # poster and overview even if no provider metadata was cached.
                # Bound cold-start network work to three titles per render.
                if remote_metadata_fetches < 3:
                    remote_metadata_fetches += 1
                    try:
                        import tmdb
                        detail = tmdb.meta_summary_cached(item['tmdb_type'], tmdb_id)
                        if isinstance(detail, dict):
                            for field in ('poster', 'fanart', 'plot', 'title', 'year'):
                                if detail.get(field):
                                    item[field] = detail[field]
                    except Exception:
                        pass
                url, li, folder = routes._media_item(item)
                li.setProperty('XStream.RemoteOnly', 'true')
            li.setProperty('XStream.ResumeOrigin', 'Trakt')
            if url:
                results.append((url, li, folder))
        return results
    except Exception as exc:
        logger = g.get('_log')
        if callable(logger):
            logger('Trakt continue remote overlay unavailable: %s' % type(exc).__name__)
        return []


'''
        start_helper = s.index('def _trakt_continue_extra(')
        end_helper = s.index('def dispatch(g, params):', start_helper)
        s = s[:start_helper] + helper + s[end_helper:]
        premium.write_text(s)
        manifest = tree/'addon.xml'
        raw = manifest.read_text()
        raw = replace_one(raw, 'version="'+OLD+'"', 'version="'+NEW+'"')
        manifest.write_text(raw)
        for path in tree.rglob('*.py'):
            compile(path.read_bytes(), str(path), 'exec')
        zip_tree(tree, output, AID)
    with zipfile.ZipFile(SOURCE) as before, zipfile.ZipFile(output) as after:
        changed = [n for n in before.namelist() if not n.endswith('/') and before.read(n)!=after.read(n)]
        assert set(changed)=={AID+'/addon.xml', AID+'/resources/lib/premium_routes.py'},changed
        if after.testzip() is not None:
            raise ValueError('bad output CRC')
    return {'version':NEW,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'changed':changed}

if __name__ == '__main__':
    import sys
    print(json.dumps(build(sys.argv[1]),indent=2))
