"""Read-only bridge from XStream stores to standard Kodi VideoInfoTag state."""


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0


def _title_key(value):
    import re
    import unicodedata
    value = re.sub(r'\s*\(\d{4}\)\s*$', '', str(value or ''))
    return ''.join(c for c in unicodedata.normalize('NFKD', value).casefold()
                   if c.isalnum())


def series_identity_evidence(title, year, matches, details):
    """Capture evidence only for one exact search result and its own TV details."""
    if (not isinstance(matches, list) or len(matches) != 1
            or not isinstance(matches[0], dict) or not isinstance(details, dict)):
        return None
    year, ident = str(year or '')[:4], str(matches[0].get('tmdb_id') or '')
    if (not year.isdigit() or len(year) != 4 or not ident.isdigit() or int(ident) < 1
            or not _title_key(title) or _title_key(matches[0].get('title')) != _title_key(title)
            or str(matches[0].get('year') or '')[:4] != year
            or str(details.get('id') or '') != ident
            or str(details.get('first_air_date') or '')[:4] != year):
        return None
    rows = details.get('seasons')
    if not isinstance(rows, list):
        return None
    seasons = {}
    for row in rows:
        if not isinstance(row, dict):
            return None
        number, count = row.get('season_number'), row.get('episode_count')
        if (type(number) is not int or type(count) is not int
                or not 0 <= number <= 200 or not 0 <= count <= 2000):
            return None
        if number > 0 and count > 0:
            if str(number) in seasons:
                return None
            seasons[str(number)] = count
    if not seasons or sum(seasons.values()) > 20000:
        return None
    return {'source': 'unique_title_year_search', 'title': str(title or ''),
            'year': year, 'tmdb_id': ident, 'seasons': seasons}


def remember_verified_series(g, item, data, profile_num, inventory):
    """Persist a unique title/year match only after episode inventories agree."""
    import sqlite3
    import time
    from contextlib import closing
    from pathlib import Path
    from series_state import INVENTORY_MAX_AGE_SECONDS

    try:
        evidence = data.get('_identity_evidence') or {}
        sid = str(item.get('series_id') or '')
        tmdb_id = str(evidence.get('tmdb_id') or '')
        year = str(item.get('year') or data.get('year') or '')[:4]
        if (not sid.isdigit() or not tmdb_id.isdigit() or int(tmdb_id) < 1
                or not year.isdigit() or len(year) != 4
                or evidence.get('source') != 'unique_title_year_search'
                or str(evidence.get('year')) != year
                or str(data.get('tmdb_id')) != tmdb_id
                or not _title_key(item.get('name'))
                or _title_key(item.get('name')) != _title_key(evidence.get('title'))
                or not isinstance(inventory, dict) or inventory.get('complete') is not True):
            return False
        checked = inventory.get('checked_at')
        if type(checked) not in (int, float) or not 0 <= time.time() - checked <= INVENTORY_MAX_AGE_SECONDS:
            return False
        supplied = str(item.get('tmdb_id') or item.get('tmdb') or '')
        if supplied and supplied != tmdb_id:
            return False
        expected = evidence.get('seasons')
        if (not isinstance(expected, dict) or not expected
                or any(not isinstance(k, str) or not k.isdigit() or not 1 <= int(k) <= 200
                       or type(v) is not int or not 1 <= v <= 2000 for k, v in expected.items())
                or sum(expected.values()) > 20000):
            return False
        actual = {}
        for row in inventory.get('episodes', []):
            season, episode = int(row['season']), int(row['episode'])
            if season < 1:
                continue
            if episode < 1 or not str(row.get('provider_id') or '').isdigit():
                return False
            numbers = actual.setdefault(str(season), set())
            if episode in numbers:
                return False
            numbers.add(episode)
        if (not actual or not set(actual).issubset(expected)
                or sum(len(numbers) for numbers in actual.values()) < 3
                or any(len(actual[season]) > expected[season]
                       or sorted(actual[season]) != list(range(1, len(actual[season]) + 1))
                       for season in actual)):
            return False
        root = Path(g['xbmcvfs'].translatePath(g['addon'].getAddonInfo('profile')))
        path = root / ('provider_search_%s.sqlite' % int(profile_num))
        if root.is_symlink() or path.is_symlink() or not path.is_file():
            return False
        with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=rw', uri=True, timeout=.1)) as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT title,norm,year FROM items WHERE stype=? AND provider_id=?',
                             ('series', sid)).fetchone()
            if (not row or row[0] != item.get('name') or str(row[2]) != year
                    or db.execute('SELECT COUNT(*) FROM items WHERE stype=? AND norm=? AND year=?',
                                  ('series', row[1], year)).fetchone()[0] != 1):
                return False
            db.execute('CREATE TABLE IF NOT EXISTS identity_matches ('
                       'stype TEXT NOT NULL, provider_id TEXT NOT NULL, title_key TEXT NOT NULL, '
                       'year TEXT NOT NULL, tmdb_id TEXT NOT NULL, '
                       'PRIMARY KEY(stype,provider_id,title_key,year))')
            existing = db.execute('SELECT tmdb_id FROM identity_matches WHERE stype=? AND provider_id=? '
                                  'AND title_key=? AND year=?', ('series', sid, row[1], year)).fetchone()
            if existing and str(existing[0]) != tmdb_id:
                return False
            collision = db.execute('SELECT 1 FROM identity_matches m JOIN items i ON '
                'm.stype=i.stype AND m.provider_id=i.provider_id AND m.title_key=i.norm AND m.year=i.year '
                'WHERE m.stype=? AND m.tmdb_id=? AND m.provider_id<>? LIMIT 1',
                ('series', tmdb_id, sid)).fetchone()
            if collision:
                return False
            db.execute('INSERT OR IGNORE INTO identity_matches VALUES (?,?,?,?,?)',
                       ('series', sid, row[1], year, tmdb_id))
            db.commit()
        g.get('_actweeter_identity_matches', {}).pop((str(profile_num), 'series'), None)
        return True
    except (AttributeError, KeyError, OSError, TypeError, ValueError, sqlite3.Error):
        return False


def _remembered_tmdb_id(g, stype, provider_id, profile_num):
    """Read visual-only associations from XStream's current provider index."""
    if not str(provider_id or '').isdigit() or not str(profile_num).isdigit():
        return ''
    import sqlite3
    from contextlib import closing
    from pathlib import Path
    try:
        root = Path(g['xbmcvfs'].translatePath(g['addon'].getAddonInfo('profile')))
        path = root / ('provider_search_%s.sqlite' % profile_num)
        cache = g.setdefault('_actweeter_identity_matches', {})
        key = str(profile_num), stype
        def stamp(p):
            try:
                s = p.stat()
                return s.st_ino, s.st_size, s.st_mtime_ns
            except FileNotFoundError:
                return None
        revision = (stamp(path), stamp(Path(str(path) + '-wal')))
        if key not in cache or cache[key][0] != revision:
            with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=.1)) as db:
                exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                                    "AND name='identity_matches'").fetchone()
                matches = {str(identifier): str(tmdb_id) for identifier, tmdb_id in
                              db.execute("SELECT m.provider_id,m.tmdb_id FROM identity_matches m "
                                         "JOIN items i ON m.stype=i.stype AND "
                                         "m.provider_id=i.provider_id AND m.title_key=i.norm "
                                         "AND m.year=i.year WHERE m.stype=?", (stype,))
                              if str(tmdb_id).isdigit() and int(tmdb_id) > 0} if exists else {}
                cache[key] = (revision, matches)
        return cache[key][1].get(str(provider_id), '')
    except (KeyError, AttributeError, OSError, sqlite3.Error, ValueError):
        return ''


def provider_tmdb_id(g, stype, provider_id, profile_num, supplied=''):
    """Read provider IDs only; title-derived artwork is never identity evidence."""
    values = {str(supplied or '').strip()} - {''}
    loader = g.get('_cache_load')
    if callable(loader) and str(provider_id or '').isdigit():
        prefix = 'vod_info_' if stype == 'movie' else 'series_info_'
        cached = loader(prefix + str(provider_id), profile_num=profile_num) or {}
        if isinstance(cached, dict):
            movie_data = cached.get('movie_data') or {}
            if not isinstance(movie_data, dict):
                return ''
            owner = movie_data.get('stream_id')
            if owner is not None and str(owner) != str(provider_id):
                return ''
            info = cached.get('info') or {}
            if isinstance(info, dict):
                values.update(str(info.get(key) or '').strip() for key in ('tmdb_id', 'tmdb'))
                values.discard('')
    if values:
        return (next(iter(values)) if len(values) == 1 and all(
            value.isdigit() and int(value) > 0 for value in values) else '')
    return _remembered_tmdb_id(g, stype, provider_id, profile_num)


def local_tmdb_id(g, stype, supplied, provider_id, profile_num):
    """Use explicit/provider metadata IDs; premium title matches stay artwork only."""
    return provider_tmdb_id(g, stype, provider_id, profile_num, supplied)


def tmdb_watched_state(g, item, movies, episodes):
    """Derive aggregates from current exact episode inventory, never legacy marks."""
    tmdb_id = str(item.get('tmdb_id') or '')
    kind = item.get('tmdb_type') or 'movie'
    season, episode = item.get('season'), item.get('episode')
    if not tmdb_id.isdigit() or int(tmdb_id) <= 0:
        return None
    if kind == 'movie':
        value = movies._data.get('tmdb:movie:' + tmdb_id)
        return value if type(value) is bool else None
    exact_episode = (episode is not None and str(episode) != ''
                     and season is not None and str(season) != '')
    if exact_episode:
        if not (str(season).isdigit() and str(episode).isdigit() and int(episode) > 0):
            return None
        key = 'tmdb:episode:{0}:s{1}:e{2}'.format(tmdb_id, int(season), int(episode))
        value = movies._data.get(key)
        if type(value) is bool:
            return value
        # A show/season mark cannot authorize an episode added afterwards.
    changes = g.get('series_changes')
    if changes is None or not g.get('addon'):
        return None
    profile = str(getattr(g.get('pm'), 'active', '1'))
    cached = g.get('_actweeter_watched_inventory')
    if cached is None or cached[0] is not movies or cached[1] != profile:
        cached = (movies, profile, changes.inventory_map(g['addon'], int(profile)))
        g['_actweeter_watched_inventory'] = cached
    from series_state import derive_series_state
    states = []
    episode_known = False
    for provider_id, record in cached[2].items():
        if not isinstance(record, dict) or provider_tmdb_id(
                g, 'series', provider_id, profile,
                record.get('tmdb_id') or record.get('tmdb')) != tmdb_id:
            continue
        if exact_episode:
            for row in record.get('episodes', []):
                if (isinstance(row, dict) and str(row.get('season')) == str(season)
                        and str(row.get('episode')) == str(episode)):
                    episode_known = True
                    if episodes.is_watched(provider_id, season, row.get('provider_id')):
                        return True
            continue
        if season is not None and str(season) != '':
            record = dict(record, episodes=[row for row in record.get('episodes', [])
                if isinstance(row, dict) and str(row.get('season')) == str(season)])
        state = derive_series_state(tmdb_id, provider_id, record, episodes,
                                    tmdb_watched_store=movies)
        complete = state.get('complete')
        states.append(complete if type(complete) is bool else None)
    if exact_episode:
        return False if episode_known else None
    if not states or any(state is None for state in states):
        return None
    return all(states)


def watched_state(g, stype, tmdb_id, season='', episode='', profile_num=1,
                  provider_id='', series_id=''):
    """Read namespaced TMDb state first, then exact provider identity."""
    identity = local_tmdb_id(g, stype, tmdb_id, provider_id if stype == 'movie' else series_id, profile_num)
    try:
        movies = g['WatchedMovies'](g['addon'], profile_num=profile_num)
        if stype == 'movie':
            value = movies._data.get('tmdb:movie:' + identity) if identity else None
            if type(value) is bool:
                return value
            value = movies._data.get(str(provider_id or ''))
            return value if type(value) is bool else None
        if stype == 'episode' and season != '' and episode != '':
            key = 'tmdb:episode:{0}:s{1}:e{2}'.format(identity, int(season), int(episode))
            value = movies._data.get(key) if identity else None
            if type(value) is bool:
                return value
            if provider_id and series_id:
                store = g['WatchedEpisodes'](g['addon'], profile_num=profile_num)
                return bool(store.is_watched(series_id, season, provider_id))
    except Exception:
        return None
    return None


def resume_entry(g, profile_num, provider_id='', series_id='', season='',
                 episode='', play_url=''):
    """Match exact provider IDs when stored, else exact playback URL only."""
    try:
        entries = g['ResumePoints'](g['addon'], profile_num=profile_num).get_all()
    except Exception:
        return None
    matches = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        exact_id = False
        if provider_id and not series_id and entry.get('stype') == 'movie':
            exact_id = str(entry.get('provider_stream_id') or '') == str(provider_id)
            if not exact_id:
                from urllib.parse import urlsplit
                import re
                try:
                    parsed = urlsplit(entry.get('url') or '')
                    leaf = parsed.path.rsplit('/', 1)[-1]
                    exact_id = (parsed.scheme in ('http', 'https') and bool(parsed.hostname)
                                and bool(re.fullmatch(re.escape(str(provider_id)) + r'\.[A-Za-z0-9]+', leaf)))
                except ValueError:
                    exact_id = False
        if series_id and episode:
            exact_id = exact_id or (
                str(entry.get('provider_series_id') or entry.get('series_id') or '') == str(series_id)
                and str(entry.get('provider_episode_id') or entry.get('ep_id') or '') == str(provider_id)
                and str(entry.get('season_num') if entry.get('season_num') is not None else '') == str(season)
                and (entry.get('episode_num') is None or str(entry['episode_num']) == str(episode)))
        exact_url = bool(play_url) and entry.get('url') == play_url
        if exact_id or exact_url:
            position = _number(entry.get('position'))
            duration = _number(entry.get('duration'))
            if 0 < position < duration:
                matches.append(entry)
    return max(matches, key=lambda row: _number(row.get('timestamp'))) if matches else None


def apply_to_listitem(g, listitem, stype, profile_num=1, tmdb_id='', season='',
                      episode='', provider_id='', series_id='', play_url=''):
    """Translate existing state only; never writes, guesses, or logs identities."""
    tag = listitem.getVideoInfoTag()
    watched = watched_state(g, stype, tmdb_id, season, episode, profile_num,
                            provider_id, series_id)
    if watched is not None:
        tag.setPlaycount(1 if watched else 0)
    resume = resume_entry(g, profile_num, provider_id, series_id, season,
                          episode, play_url)
    if resume:
        position = _number(resume.get('position'))
        duration = _number(resume.get('duration'))
        if duration > 0 and 0 < position < duration:
            tag.setDuration(int(duration))
            tag.setResumePoint(position, duration)
    return {'watched': watched, 'has_resume': bool(resume)}


def watched_context(g, stype, tmdb_id, season='', episode='', profile_num=1):
    """Expose XStream's existing explicit mark/unmark action where IDs are exact."""
    state = watched_state(g, stype, tmdb_id, season, episode, profile_num)
    if state is None:
        # Unknown is not unwatched: expose an explicit action only for an
        # exact, valid TMDb identity; never guess from title or provider ID.
        identity = str(tmdb_id or '').strip()
        if not identity.isdigit() or int(identity) <= 0:
            return []
        state = False
    route = g['build_url']({'mode':'toggle_tmdb_watched', 'tmdb_id':str(tmdb_id),
        'tmdb_type':'movie' if stype == 'movie' else 'tv', 'season':str(season or ''),
        'episode':str(episode or ''), 'profile_num':str(profile_num or 1)})
    label = g['_t'](31082 if state else 31081)
    # Kodi also contributes a native action with this label; distinguish the
    # plugin action so it remains visible and unambiguous in the context menu.
    return [(label + ' (AcTweeteR)', 'RunPlugin(%s)' % route)]


def add_context_actions(listitem, *groups):
    """Submit all actions in one call: Kodi re-indexes context items per call."""
    actions = [action for group in groups for action in (group or [])]
    if actions:
        listitem.addContextMenuItems(actions)
    return actions


def apply_remote_progress(listitem, item):
    """Display exact Trakt percentages without inventing an absolute seek point."""
    import math
    raw = item.get('raw')
    if not isinstance(raw, dict):
        return False
    media = raw.get('movie') or raw.get('show')
    ids = media.get('ids') if isinstance(media, dict) else None
    if (not isinstance(ids, dict) or not str(item.get('tmdb_id') or '').isdigit()
            or str(ids.get('tmdb') or '') != str(item['tmdb_id'])):
        return False
    if raw.get('show'):
        episode = raw.get('episode')
        if (not isinstance(episode, dict)
                or str(episode.get('season')) != str(item.get('season'))
                or str(episode.get('number')) != str(item.get('episode'))):
            return False
    progress = raw.get('progress')
    if type(progress) not in (int, float) or not math.isfinite(progress) or not 0 < progress < 100:
        return False
    listitem.setProperty('XStream.RemoteProgress', ('%.1f' % progress).rstrip('0').rstrip('.'))
    return True
