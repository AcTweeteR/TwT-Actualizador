"""Apply a small, verified local batch through XStream's coordinated stores."""
import json
import math
import re
from pathlib import Path
from urllib.parse import urlsplit

from trakt_live_queue import verify_batch, write_ack


def _provider_ref(operation, records):
    kind, provider_id = operation['kind'], str(operation['provider_id'])
    matches = []
    for record in records:
        if not isinstance(record, dict) or record.get('stype') != (
                'series' if kind == 'episode' else 'movie'):
            continue
        url, name = record.get('url'), record.get('name')
        if not isinstance(url, str) or not isinstance(name, str) or not name.strip():
            continue
        try:
            parsed = urlsplit(url)
        except ValueError:
            continue
        if parsed.scheme not in ('http', 'https') or not parsed.hostname:
            continue
        if kind == 'movie':
            if re.search(r'/%s\.[A-Za-z0-9]+$' % re.escape(provider_id), parsed.path):
                matches.append(record)
        elif (str(record.get('series_id', '')) == str(operation['series_id'])
              and str(record.get('ep_id', '')) == str(operation['episode_id'])
              and str(record.get('season_num', '')) == str(operation['season'])
              and str(record.get('episode_num', '')) == str(operation['episode'])):
            matches.append(record)
    unique = {(record['name'], record['url']): record for record in matches}
    return next(iter(unique.values())) if len(unique) == 1 else None


def apply_batch(batch_path, ack_directory, *, profile, account, provider_scope,
                addon, history, playing_file='', max_operations=200):
    """Idempotently apply additions; ack only after fresh-reader verification."""
    path = Path(batch_path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
        raise ValueError('unsafe or oversized queue batch')
    batch = verify_batch(json.loads(path.read_text('utf-8')), profile=profile,
                         account=account, provider_scope=provider_scope)
    if len(batch['operations']) > max_operations:
        raise ValueError('batch exceeds bounded application limit')
    if playing_file:
        results = [{'id': operation['id'], 'status': 'deferred',
                    'reason': 'playback_active'} for operation in batch['operations']]
        return write_ack(Path(ack_directory) / (batch['batch_id'] + '.json'),
                         batch, results)
    watched_movies = history.WatchedMovies(addon, profile_num=int(profile))
    watched_episodes = history.WatchedEpisodes(addon, profile_num=int(profile))
    resume = history.ResumePoints(addon, profile_num=int(profile))
    watch_history = history.WatchHistory(addon, profile_num=int(profile))
    recent = resume.get_all()
    recent += watch_history.get_all()
    results, changed = [], {'movie': False, 'episode': False, 'resume': False}
    for operation in batch['operations']:
        op_id = operation['id']
        kind, action = operation.get('kind'), operation.get('action')
        identity = operation.get('identity')
        if (operation.get('confidence') != 'exact' or action not in ('watched', 'resume')
                or kind not in ('movie', 'episode') or not isinstance(identity, dict)
                or identity.get('kind') != kind or not isinstance(identity.get('ids'), dict)
                or not identity['ids'] or not re.fullmatch(r'[0-9]+', str(operation.get('provider_id', '')))
                or type(operation.get('timestamp')) not in (float, int)
                or not math.isfinite(operation['timestamp']) or operation['timestamp'] <= 0):
            raise ValueError('unsupported or unverified operation')
        if kind == 'episode' and (
                not re.fullmatch(r'[0-9]+', str(operation.get('series_id', '')))
                or str(operation.get('episode_id')) != str(operation['provider_id'])
                or type(operation.get('season')) is not int
                or operation['season'] < 0 or type(operation.get('episode')) is not int
                or operation['episode'] < 1
                or identity.get('season') != operation['season']
                or identity.get('episode') != operation['episode']):
            raise ValueError('episode identity mismatch')
        if action == 'resume':
            position, duration = operation.get('position'), operation.get('duration')
            if (type(position) not in (int, float) or type(duration) not in (int, float)
                    or not math.isfinite(position) or not math.isfinite(duration)
                    or duration < 120 or position < 60 or position > duration * .93):
                raise ValueError('invalid resume bounds')
        if action == 'watched':
            active_ref = _provider_ref(operation, recent) if playing_file else None
            if active_ref is not None and active_ref['url'] == playing_file:
                results.append({'id': op_id, 'status': 'deferred', 'reason': 'content_is_playing'})
                continue
            if kind == 'movie':
                key = str(operation['provider_id'])
                if key in watched_movies._data:
                    results.append({'id': op_id, 'status': 'already_applied'})
                else:
                    watched_movies._data[key] = True
                    changed['movie'] = True
                    results.append({'id': op_id, 'status': 'applied'})
            else:
                series, season, episode = (str(operation['series_id']),
                                           str(operation['season']),
                                           str(operation['episode_id']))
                current = watched_episodes._data.setdefault(series, {}).setdefault(season, [])
                if episode in current:
                    results.append({'id': op_id, 'status': 'already_applied'})
                else:
                    current.append(episode)
                    changed['episode'] = True
                    results.append({'id': op_id, 'status': 'applied'})
            continue

        record = _provider_ref(operation, recent)
        if record is None:
            results.append({'id': op_id, 'status': 'deferred', 'reason': 'exact_playback_reference_missing'})
            continue
        url = record['url']
        if playing_file and playing_file == url:
            results.append({'id': op_id, 'status': 'deferred', 'reason': 'content_is_playing'})
            continue
        key = resume._key(record['name'], url)
        current = resume._data.get(key)
        if isinstance(current, dict):
            local_stamp = current.get('timestamp')
            if type(local_stamp) not in (int, float) or local_stamp >= operation['timestamp']:
                results.append({'id': op_id, 'status': 'already_applied' if
                                local_stamp == operation['timestamp'] else 'superseded'})
                continue
        value = {'name': record['name'], 'url': url,
                 'position': operation['position'], 'duration': operation['duration'],
                 'timestamp': operation['timestamp'],
                 'stype': 'series' if kind == 'episode' else 'movie'}
        for field in ('icon', 'title', 'plot'):
            if isinstance(record.get(field), str) and record[field]:
                value[field] = record[field]
        if kind == 'episode':
            value.update(series_id=str(operation['series_id']),
                         season_num=operation['season'], ep_id=str(operation['episode_id']),
                         episode_num=operation['episode'])
        resume._data[key] = value
        changed['resume'] = True
        results.append({'id': op_id, 'status': 'applied'})

    # Each data store is saved through XStream's coordinated writer. A crash
    # between stores is recoverable because every action in this bridge adds.
    if changed['movie']:
        watched_movies._save()
    if changed['episode']:
        watched_episodes._save()
    if changed['resume']:
        resume._save()

    verify_movies = history.WatchedMovies(addon, profile_num=int(profile))
    verify_episodes = history.WatchedEpisodes(addon, profile_num=int(profile))
    verify_resume = history.ResumePoints(addon, profile_num=int(profile))
    for operation, result in zip(batch['operations'], results):
        if result['status'] not in ('applied', 'already_applied', 'superseded'):
            continue
        if operation['action'] == 'watched' and operation['kind'] == 'movie':
            if str(operation['provider_id']) not in verify_movies._data:
                raise OSError('movie watched state was not persisted')
        elif operation['action'] == 'watched':
            if str(operation['episode_id']) not in verify_episodes._data.get(
                    str(operation['series_id']), {}).get(str(operation['season']), []):
                raise OSError('episode watched state was not persisted')
        elif result['status'] != 'superseded':
            record = _provider_ref(operation, recent)
            verified = verify_resume._data.get(verify_resume._key(record['name'], record['url']))
            if not isinstance(verified, dict) or verified.get('timestamp', 0) < operation['timestamp']:
                raise OSError('resume point was not persisted')
    ack = Path(ack_directory) / (batch['batch_id'] + '.json')
    return write_ack(ack, batch, results)
