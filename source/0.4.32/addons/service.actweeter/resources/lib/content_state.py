"""Read-only bridge from XStream stores to standard Kodi VideoInfoTag state."""


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0


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
    return (next(iter(values)) if len(values) == 1 and all(
        value.isdigit() and int(value) > 0 for value in values) else '')


def local_tmdb_id(g, stype, supplied, provider_id, profile_num):
    """Use explicit/provider metadata IDs; premium title matches stay artwork only."""
    identity = str(supplied or '').strip()
    if identity.isdigit() and int(identity) > 0:
        return identity
    return provider_tmdb_id(g, stype, provider_id, profile_num)


def tmdb_watched_state(g, item, movies, episodes):
    """Derive aggregates from current exact episode inventory, never legacy marks."""
    tmdb_id = str(item.get('tmdb_id') or '')
    kind = item.get('tmdb_type') or 'movie'
    season, episode = item.get('season'), item.get('episode')
    if not tmdb_id.isdigit() or int(tmdb_id) <= 0:
        return False
    if kind == 'movie':
        return movies._data.get('tmdb:movie:' + tmdb_id) is True
    exact_episode = (episode is not None and str(episode) != ''
                     and season is not None and str(season) != '')
    if exact_episode:
        if not (str(season).isdigit() and str(episode).isdigit() and int(episode) > 0):
            return False
        key = 'tmdb:episode:{0}:s{1}:e{2}'.format(tmdb_id, int(season), int(episode))
        if key in movies._data:
            return movies._data[key] is True
        # A show/season mark cannot authorize an episode added afterwards.
    changes = g.get('series_changes')
    if changes is None or not g.get('addon'):
        return False
    profile = str(getattr(g.get('pm'), 'active', '1'))
    cached = g.get('_actweeter_watched_inventory')
    if cached is None or cached[0] is not movies or cached[1] != profile:
        cached = (movies, profile, changes.inventory_map(g['addon'], int(profile)))
        g['_actweeter_watched_inventory'] = cached
    from series_state import derive_series_state
    states = []
    for provider_id, record in cached[2].items():
        if not isinstance(record, dict) or str(record.get('tmdb_id') or '') != tmdb_id:
            continue
        if exact_episode:
            for row in record.get('episodes', []):
                if (isinstance(row, dict) and str(row.get('season')) == str(season)
                        and str(row.get('episode')) == str(episode)
                        and episodes.is_watched(provider_id, season, row.get('provider_id'))):
                    return True
            continue
        if season is not None and str(season) != '':
            record = dict(record, episodes=[row for row in record.get('episodes', [])
                if isinstance(row, dict) and str(row.get('season')) == str(season)])
        state = derive_series_state(tmdb_id, provider_id, record, episodes,
                                    tmdb_watched_store=movies)
        states.append(state.get('complete') is True)
    return bool(states) and all(states)


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
