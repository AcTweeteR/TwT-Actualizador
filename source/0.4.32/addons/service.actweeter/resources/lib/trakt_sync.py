"""Read-only Trakt import planning. No tokens, provider URLs or remote writes.

The caller supplies an authenticated GET transport and verified catalog IDs.
This module does not import script.trakt or change its scrobbling ownership.
"""
from datetime import datetime
import math
import re


class IncompleteSnapshot(ValueError):
    pass


def _integer(value, minimum=1):
    text = str(value)
    return int(text) if re.fullmatch(r"[0-9]+", text) and int(text) >= minimum else None


def normalize_ids(value):
    if not isinstance(value, dict):
        return {}
    result = {}
    for key in ('tmdb', 'tvdb', 'trakt'):
        number = _integer(value.get(key))
        if number is not None:
            result[key] = str(number)
    imdb = str(value.get('imdb', '')).lower()
    if re.fullmatch(r'tt[0-9]+', imdb):
        result['imdb'] = imdb
    return result


def identity(kind, ids=None, *, show_ids=None, season=None, episode=None):
    """An episode belongs to a show+S/E, never to a movie with the same TMDb ID."""
    values = normalize_ids(show_ids if kind == 'episode' else ids)
    if kind == 'movie':
        values.pop('tvdb', None)
    order = ('tmdb', 'imdb', 'trakt') if kind == 'movie' else ('tmdb', 'tvdb', 'imdb', 'trakt')
    primary = next((name for name in order if name in values), None)
    if kind not in ('movie', 'show', 'episode') or primary is None:
        return None
    result = {'kind': kind, 'ids': values, 'key': kind + ':' + primary + ':' + values[primary]}
    if kind == 'episode':
        season, episode = _integer(season, 0), _integer(episode)
        if season is None or episode is None:
            return None
        result.update(season=season, episode=episode)
        result['key'] += ':s%d:e%d' % (season, episode)
    return result


def _timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return stamp.timestamp() if stamp.tzinfo is not None else None
    except (ValueError, OverflowError):
        return None


class ProviderIndex:
    """Rebuildable, typed index of verified IDs, not a title-matching database."""
    def __init__(self, records, *, profile):
        self.records = []
        self.by_id = {}
        for record in records:
            if str(record.get('profile', '')) != str(profile):
                continue
            if record.get('confidence') not in ('exact', 'verified'):
                continue
            content = identity(record.get('kind'), record.get('ids'),
                               show_ids=record.get('show_ids'), season=record.get('season'),
                               episode=record.get('episode'))
            provider_id = _integer(record.get('provider_id'))
            if content is None or provider_id is None:
                continue
            index = len(self.records)
            self.records.append((content, record))
            for name, value in content['ids'].items():
                key = (content['kind'], name, value, content.get('season'), content.get('episode'))
                self.by_id.setdefault(key, set()).add(index)

    def match(self, content):
        candidates = set()
        for name, value in content['ids'].items():
            key = (content['kind'], name, value, content.get('season'), content.get('episode'))
            candidates.update(self.by_id.get(key, ()))
        valid, conflict = {}, False
        for index in sorted(candidates):
            candidate, record = self.records[index]
            if any(candidate['ids'][name] != value for name, value in content['ids'].items()
                   if name in candidate['ids']):
                conflict = True
                continue
            # Duplicate rows for the same provider ID are not multiple versions.
            valid[str(record['provider_id'])] = record
        if conflict:
            return 'conflict', []
        if not valid:
            return 'unavailable', []
        return ('exact' if len(valid) == 1 else 'ambiguous'), list(valid.values())


def _pages(get, path, cancelled, max_pages):
    page, expected = 1, None
    while True:
        if cancelled():
            raise IncompleteSnapshot('cancelled')
        rows, count = get(path, {'page': page, 'limit': 100, 'extended': 'full'})
        if not isinstance(rows, list) or type(count) is not int or not 1 <= count <= max_pages:
            raise IncompleteSnapshot('invalid pagination or payload')
        if expected is not None and expected != count:
            raise IncompleteSnapshot('pagination changed')
        expected = count
        if not rows and page < count:
            raise IncompleteSnapshot('missing page')
        for row in rows:
            if not isinstance(row, dict):
                raise IncompleteSnapshot('invalid item')
            yield row
        if page == count:
            break
        page += 1


def fetch_snapshot(get, *, cancelled=lambda: False, max_pages=1000):
    """Return only a complete account snapshot; an exception never means empty.

    Uses GET only. Caller must preserve the previous snapshot on any exception.
    Activity stamps fence concurrent remote edits; no local state is applied.
    """
    account, _ = get('/users/settings', {})
    try:
        account_id = str(account['user']['ids']['slug'])
    except (KeyError, TypeError):
        raise IncompleteSnapshot('account identity unavailable') from None
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', account_id):
        raise IncompleteSnapshot('invalid account identity')
    before, _ = get('/sync/last_activities', {})
    if not isinstance(before, dict) or not isinstance(before.get('all'), str):
        raise IncompleteSnapshot('activity stamp unavailable')
    snapshot = {'schema_version': 1, 'account': account_id, 'records': {},
                'history': [], 'unidentified': 0, 'activity': before['all']}
    history_ids = set()

    def add(content, field, stamp, **extra):
        if content is None:
            snapshot['unidentified'] += 1
            return
        if _timestamp(stamp) is None:
            raise IncompleteSnapshot('invalid event timestamp')
        item = snapshot['records'].setdefault(content['key'], {'identity': content})
        old = _timestamp(item.get(field))
        if old is None or _timestamp(stamp) >= old:
            item[field] = stamp
            item.update(extra)

    for row in _pages(get, '/sync/watched/movies', cancelled, max_pages):
        movie = row.get('movie') or {}
        add(identity('movie', movie.get('ids')), 'watched_at', row.get('last_watched_at'))
    for row in _pages(get, '/sync/watched/shows', cancelled, max_pages):
        show = row.get('show') or {}
        seasons = row.get('seasons')
        if not isinstance(seasons, list):
            raise IncompleteSnapshot('missing explicit episode inventory')
        for season in seasons:
            if not isinstance(season, dict) or not isinstance(season.get('episodes'), list):
                raise IncompleteSnapshot('invalid season inventory')
            for episode in season['episodes']:
                if not isinstance(episode, dict):
                    raise IncompleteSnapshot('invalid episode')
                content = identity('episode', show_ids=show.get('ids'),
                                   season=season.get('number'), episode=episode.get('number'))
                add(content, 'watched_at', episode.get('last_watched_at'))
    for kind in ('movies', 'episodes'):
        for row in _pages(get, '/sync/history/' + kind, cancelled, max_pages):
            episode = row.get('episode') or {}
            content = (identity('movie', (row.get('movie') or {}).get('ids')) if kind == 'movies'
                       else identity('episode', show_ids=(row.get('show') or {}).get('ids'),
                                     season=episode.get('season'), episode=episode.get('number')))
            if content is None:
                snapshot['unidentified'] += 1
                continue
            if _timestamp(row.get('watched_at')) is None or _integer(row.get('id')) is None:
                raise IncompleteSnapshot('invalid history event')
            event = {'identity': content, 'id': str(row['id']), 'watched_at': row['watched_at']}
            if event['id'] not in history_ids:
                snapshot['history'].append(event)
                history_ids.add(event['id'])
        for row in _pages(get, '/sync/playback/' + kind, cancelled, max_pages):
            episode = row.get('episode') or {}
            content = (identity('movie', (row.get('movie') or {}).get('ids')) if kind == 'movies'
                       else identity('episode', show_ids=(row.get('show') or {}).get('ids'),
                                     season=episode.get('season'), episode=episode.get('number')))
            progress = row.get('progress')
            if (type(progress) not in (float, int) or not math.isfinite(progress)
                    or not 0 <= progress <= 100):
                raise IncompleteSnapshot('invalid playback percentage')
            add(content, 'paused_at', row.get('paused_at'), progress=progress)
    after, _ = get('/sync/last_activities', {})
    if before != after or cancelled():
        raise IncompleteSnapshot('remote state changed or cancelled')
    final_account, _ = get('/users/settings', {})
    if not isinstance(final_account, dict) or final_account.get('user', {}).get('ids', {}).get('slug') != account_id:
        raise IncompleteSnapshot('account changed during import')
    return snapshot


def import_plan(snapshot, provider_records, *, profile, account, local=None):
    """Propose additions only. No store or remote mutation occurs here."""
    if not profile or snapshot['account'] != account:
        raise ValueError('profile/account binding required')
    index = ProviderIndex(provider_records, profile=profile)
    local = local or {}
    result = {'profile': str(profile), 'account': account, 'items': [], 'conflicts': [],
              'unavailable': [], 'ambiguous': [], 'unidentified': snapshot['unidentified']}
    for key, remote in snapshot['records'].items():
        content = remote['identity']
        status, matches = index.match(content)
        if status != 'exact':
            result[{'conflict': 'conflicts'}.get(status, status)].append(key)
            continue
        provider = matches[0]
        item = {'identity': content, 'provider_id': str(provider['provider_id'])}
        previous = local.get(key, {})
        watched, paused = _timestamp(remote.get('watched_at')), _timestamp(remote.get('paused_at'))
        if watched is not None:
            if previous.get('watched') is False:
                result['conflicts'].append(key)
                continue
            item['watched'] = True
            item['watched_at'] = remote['watched_at']
        if paused is not None and (watched is None or paused > watched):
            local_stamp = _timestamp(previous.get('updated_at'))
            if ('position' in previous or 'progress' in previous) and (local_stamp is None or local_stamp >= paused):
                result['conflicts'].append(key)
                continue
            duration = provider.get('duration_seconds')
            if type(duration) in (int, float) and math.isfinite(duration) and duration > 0:
                item.update(position=duration * remote['progress'] / 100,
                            duration=duration, paused_at=remote['paused_at'])
            else:
                item['resume_deferred'] = 'duration_unknown'
        result['items'].append(item)
    return result
