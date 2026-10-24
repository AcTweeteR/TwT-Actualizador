"""Read-only bridge from XStream stores to standard Kodi VideoInfoTag state."""


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0


def local_tmdb_id(g, stype, supplied, provider_id, profile_num):
    """Use an existing exact cached identity; never discover it over the network."""
    identity = str(supplied or '').strip()
    if identity.isdigit() and int(identity) > 0:
        return identity
    loader = g.get('_cache_load')
    if not callable(loader) or not str(provider_id or '').isdigit():
        return ''
    import time
    kind = 'movie' if stype == 'movie' else 'series'
    cached = loader('premium_meta_%s_%s_es' % (kind, provider_id), profile_num=profile_num) or {}
    if cached.get('expires', 0) <= time.time():
        return ''
    data = cached.get('data') or {}
    value = str(data.get('tmdb_id') or '').strip()
    return value if value.isdigit() and int(value) > 0 else ''


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
        if provider_id:
            exact_id = str(entry.get('provider_stream_id') or '') == str(provider_id)
        if series_id and episode:
            exact_id = exact_id or (
                str(entry.get('provider_series_id') or '') == str(series_id)
                and str(entry.get('provider_episode_id') or '') == str(provider_id)
                and str(entry.get('season_num') or '') == str(season)
                and str(entry.get('ep_id') or '') == str(episode))
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
        return []
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
