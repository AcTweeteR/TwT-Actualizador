"""Create-only Beta: show authenticated Trakt playback alongside local ResumePoints."""
from pathlib import Path
import tempfile, zipfile, hashlib, json
from xml.etree import ElementTree as ET
from build_test_channel import zip_tree

ROOT = Path(__file__).resolve().parents[1]
AID = 'plugin.video.xstream-pro'
OLD = '1.1.2.44~beta1'
NEW = '1.1.2.44~beta2'
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
        trakt = tree/'resources/lib/trakt.py'
        s = trakt.read_text()
        s = replace_one(s,
            '''def playback(media_kind="movies", page=1):
    kind = "episodes" if media_kind == "episodes" else "movies"
    payload, total_pages = request(
        "/sync/playback/{0}".format(kind),
        params={"extended": "full", "page": page, "limit": TRAKT_PAGE_LIMIT},
        auth=True,
    )
''',
            '''def playback(media_kind="movies", page=1, cached=False):
    kind = "episodes" if media_kind == "episodes" else "movies"
    params = {"extended": "full", "page": page, "limit": TRAKT_PAGE_LIMIT}
    path = "/sync/playback/{0}".format(kind)
    # Home widgets share a short per-account cache to avoid repeated GETs.
    # The explicit Trakt playback menu always requests fresh remote progress.
    payload, total_pages = (cached_request(path, params, auth=True, ttl=180, timeout=2)
                            if cached else request(path, params=params, auth=True))
''')
        trakt.write_text(s)
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
        # Only cache-backed artwork hydration; no synchronous TMDb requests.
        pending = routes._hydrate_from_tmdb_meta_cache(pending)
        results = []
        for item in pending[:limit]:
            url, li, folder = routes._media_item(item)
            li.setProperty('XStream.ResumeOrigin', 'Trakt')
            # A remote-only card uses the standard provider chooser, not an
            # invented Xtream URL or estimated resume position.
            li.setProperty('XStream.RemoteOnly', 'true')
            if url:
                results.append((url, li, folder))
        return results
    except Exception as exc:
        logger = g.get('_log')
        if callable(logger):
            logger('Trakt continue remote overlay unavailable: %s' % type(exc).__name__)
        return []


'''
        s = replace_one(s, 'def dispatch(g, params):\n', helper+'def dispatch(g, params):\n')
        s = replace_one(s, '''        valid_count = 0
        has_more = False
        for entry in entries:
''', '''        valid_count = 0
        has_more = False
        local_shown = 0
        seen_resume_ids = set()
        for entry in entries:
''')
        s = replace_one(s, '''            content_state.add_context_actions(li, context_actions, watched_actions)
            plugin.addDirectoryItem(handle, build({'mode':'premium', 'view':'resume',
                'stype':kind, 'key':resume_key(entry), 'profile_num':pnum}), li, False)
        if has_more and get('actweeter_expand') == '1':
''', '''            content_state.add_context_actions(li, context_actions, watched_actions)
            plugin.addDirectoryItem(handle, build({'mode':'premium', 'view':'resume',
                'stype':kind, 'key':resume_key(entry), 'profile_num':pnum}), li, False)
            local_shown += 1
            remote_type = 'movie' if kind == 'movie' else 'tv'
            verified = str(data.get('_verified_tmdb_id') or '')
            episode_match = re.search(r'S(\\d+)E(\\d+)', entry.get('name', ''), re.I)
            if verified.isdigit() and (kind == 'movie' or episode_match):
                seen_resume_ids.add((remote_type, verified,
                    episode_match.group(1) if episode_match else '',
                    episode_match.group(2) if episode_match else ''))
        if view == 'continue' and page == 1:
            for extra_url, extra_li, extra_folder in _trakt_continue_extra(
                    g, stype, seen_resume_ids, limit - local_shown):
                plugin.addDirectoryItem(handle, extra_url, extra_li, extra_folder)
        if has_more and get('actweeter_expand') == '1':
''')
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
        assert set(changed)=={AID+'/addon.xml', AID+'/resources/lib/trakt.py', AID+'/resources/lib/premium_routes.py'},changed
        if after.testzip() is not None:
            raise ValueError('bad output CRC')
    return {'version':NEW,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'changed':changed}

if __name__ == '__main__':
    import sys
    print(json.dumps(build(sys.argv[1]),indent=2))
