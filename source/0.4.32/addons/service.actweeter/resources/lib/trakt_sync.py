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


def _pages(get, path, cancelled, max_pages, require_page_metadata=False):
    page, expected, expected_meta = 1, None, None
    seen_pages = set()
    while True:
        if cancelled():
            raise IncompleteSnapshot('cancelled')
        # Trakt's 2026 watched API requires progress to include explicit episodes.
        extended = 'progress' if path == '/sync/watched/shows' else 'full'
        rows, count = get(path, {'page': page, 'limit': 100, 'extended': extended})
        if isinstance(count, dict):
            meta = count
            count = meta.get('page_count')
            values = (meta.get('page'), meta.get('limit'), meta.get('item_count'), count)
            if (not all(type(value) is int for value in values)
                    or meta['page'] != page or meta['limit'] < 1
                    or meta['item_count'] < 0 or count < 0
                    or count != (math.ceil(meta['item_count'] / meta['limit']) or count)
                    or (meta['item_count'] == 0 and count not in (0, 1))):
                raise IncompleteSnapshot('invalid pagination headers')
            signature = (meta['limit'], meta['item_count'], count)
            if expected_meta is not None and signature != expected_meta:
                raise IncompleteSnapshot('pagination totals changed')
            expected_meta = signature
            remaining = max(0, meta['item_count'] - (page - 1) * meta['limit'])
            if not isinstance(rows, list) or len(rows) != min(meta['limit'], remaining):
                raise IncompleteSnapshot('truncated page')
        elif require_page_metadata:
            raise IncompleteSnapshot('pagination headers required')
        if page == 1 and rows == [] and type(count) is int and count == 0:
            return
        if not isinstance(rows, list) or type(count) is not int or not 1 <= count <= max_pages:
            detail = str(count) if type(count) is int else type(count).__name__
            raise IncompleteSnapshot('invalid pagination or payload: %s (%s, %s)' %
                                     (path, type(rows).__name__, detail))
        if expected is not None and expected != count:
            raise IncompleteSnapshot('pagination changed')
        expected = count
        if count > 1:
            import hashlib
            import json
            try:
                digest = hashlib.sha256(json.dumps(rows, sort_keys=True, allow_nan=False).encode()).digest()
            except (ValueError, TypeError):
                raise IncompleteSnapshot('invalid paginated values') from None
            if digest in seen_pages:
                raise IncompleteSnapshot('repeated page body')
            seen_pages.add(digest)
        # A single empty first page is a valid empty collection (Trakt may
        # report one page); an empty page in a multi-page result is truncated.
        if not rows and (page > 1 or count > 1):
            raise IncompleteSnapshot('missing page')
        for row in rows:
            if not isinstance(row, dict):
                raise IncompleteSnapshot('invalid item')
            yield row
        if page == count:
            break
        page += 1


def fetch_snapshot(get, *, cancelled=lambda: False, max_pages=1000, require_page_metadata=False):
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
    if not isinstance(before, dict) or _timestamp(before.get('all')) is None:
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

    for row in _pages(get, '/sync/watched/movies', cancelled, max_pages, require_page_metadata):
        movie = row.get('movie') or {}
        add(identity('movie', movie.get('ids')), 'watched_at', row.get('last_watched_at'))
    for row in _pages(get, '/sync/watched/shows', cancelled, max_pages, require_page_metadata):
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
        for row in _pages(get, '/sync/history/' + kind, cancelled, max_pages, require_page_metadata):
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
        for row in _pages(get, '/sync/playback/' + kind, cancelled, max_pages, require_page_metadata):
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
    # Completeness is asserted only after every page and both account/activity fences.
    snapshot['complete'] = True
    return snapshot


def validate_export(payload, manifest, *, profile, account, legacy_reference=None):
    """Replay a complete response transcript; a manifest flag alone proves nothing.

    Legacy v1 omitted account settings and the complete flag. Accept it only
    with both activity fences, every numbered response, identical rebuilt data,
    and a fresh strict export attesting the same account state.
    Account/profile are explicitly supplied by the authenticated caller.
    """
    if not isinstance(payload, dict) or payload.get('schema_version') not in (1, 2):
        raise IncompleteSnapshot('complete supported snapshot required')
    snapshot = payload.get('snapshot')
    if not isinstance(snapshot, dict):
        raise IncompleteSnapshot('complete supported snapshot required')
    if str(payload.get('profile')) != str(profile) or snapshot.get('account') != account:
        raise PermissionError('Trakt account or XStream profile mismatch')
    if (not str(profile).isdigit() or int(profile) < 1 or not account
            or snapshot.get('complete') is False):
        raise IncompleteSnapshot('complete supported snapshot required')
    responses = payload.get('responses')
    if not isinstance(responses, list) or not responses:
        raise IncompleteSnapshot('complete supported snapshot response evidence required')
    legacy = payload['schema_version'] == 1
    cursor = iter(responses)
    consumed = []
    def replay(path, params):
        if legacy and path == '/users/settings':
            return {'user': {'ids': {'slug': account}}}, 1
        try:
            row = next(cursor)
        except StopIteration:
            raise IncompleteSnapshot('missing response evidence') from None
        if (not isinstance(row, dict) or row.get('path') != path
                or row.get('params') != params or 'data' not in row or 'pages' not in row):
            raise IncompleteSnapshot('response order or page mismatch')
        if isinstance(row.get('pagination'), dict) and row['pages'] != row['pagination'].get('page_count'):
            raise IncompleteSnapshot('conflicting pagination evidence')
        consumed.append(row)
        return row['data'], row.get('pagination', row['pages'])
    rebuilt = fetch_snapshot(replay, require_page_metadata=not legacy)
    if next(cursor, None) is not None:
        raise IncompleteSnapshot('unexpected extra response evidence')
    if legacy:
        groups = {}
        for row in consumed:
            if row['params'].get('page'):
                groups.setdefault(row['path'], []).append(row)
        for rows in groups.values():
            limit = len(rows[0]['data'])
            if (any(len(row['data']) != limit for row in rows[:-1])
                    or len(rows[-1]['data']) > limit):
                raise IncompleteSnapshot('inconsistent legacy page lengths')
    original = dict(snapshot)
    original.pop('complete', None)
    comparable = dict(rebuilt)
    comparable.pop('complete', None)
    if original != comparable:
        raise IncompleteSnapshot('snapshot does not match complete response evidence')
    expected = {'records': len(rebuilt['records']), 'history': len(rebuilt['history']),
                'unidentified': rebuilt['unidentified'], 'responses': len(responses)}
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise IncompleteSnapshot('manifest counts do not match response evidence')
    if not legacy and (snapshot.get('complete') is not True
                       or manifest.get('contract_version') != 2
                       or manifest.get('complete') is not True):
        raise IncompleteSnapshot('unsupported export contract')
    if legacy:
        # Page-count-only archives cannot prove the final page's item total.
        # A fresh strict export may attest identical state, never a manufactured flag.
        if legacy_reference is None:
            raise IncompleteSnapshot('legacy export requires a fresh verified reference')
        reference, proof = legacy_reference
        if reference.get('schema_version') != 2:
            raise IncompleteSnapshot('strict reference required')
        import hashlib
        import json
        encoded = json.dumps(reference, ensure_ascii=False, sort_keys=True, allow_nan=False).encode('utf-8')
        if hashlib.sha256(encoded).hexdigest() != proof.get('sha256'):
            raise IncompleteSnapshot('reference checksum mismatch')
        current = validate_export(reference, proof, profile=profile, account=account)
        if rebuilt != current:
            raise IncompleteSnapshot('legacy state differs from fresh complete reference')
    return rebuilt


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
