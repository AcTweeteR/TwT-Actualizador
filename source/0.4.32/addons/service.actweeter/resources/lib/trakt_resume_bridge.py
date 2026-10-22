"""Stage verified Trakt resume points using exact XStream references only."""
from datetime import datetime
import json
import math
import re
from pathlib import Path
from urllib.parse import urlsplit

from .trakt_sync import normalize_ids


def _timestamp(value):
    if type(value) in (int, float):
        return float(value) if math.isfinite(value) and value > 0 else None
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.timestamp() if parsed.tzinfo is not None else None
    except (ValueError, OverflowError):
        return None


def _positive_int(value, *, allow_zero=False):
    if isinstance(value, bool) or not re.fullmatch(r'[0-9]+', str(value)):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if number >= (0 if allow_zero else 1) else None


def _valid_reference(item, reference, profile):
    identity = item.get('identity')
    if not isinstance(identity, dict) or not isinstance(reference, dict):
        return False
    kind, ids = identity.get('kind'), identity.get('ids')
    if (kind not in ('movie', 'episode') or not isinstance(ids, dict)
            or not ids or normalize_ids(ids) != ids):
        return False
    target = reference.get('identity')
    if (reference.get('confidence') not in ('exact', 'verified')
            or str(reference.get('profile', '')) != profile
            or reference.get('kind') != kind
            or str(reference.get('provider_id', '')) != str(item.get('provider_id', ''))
            or not isinstance(target, dict) or target.get('kind') != kind
            or target.get('ids') != ids):
        return False
    name, url = reference.get('name'), reference.get('url')
    if (not isinstance(name, str) or not name.strip()
            or not isinstance(url, str) or not url.startswith(('https://', 'http://'))):
        return False
    if kind == 'movie':
        return True
    return (str(reference.get('series_id', '')) == str(item.get('provider_series_id', ''))
            and str(reference.get('ep_id', '')) == str(item.get('provider_episode_id', ''))
            and _positive_int(reference.get('season_num'), allow_zero=True) == identity.get('season')
            and _positive_int(reference.get('episode_num')) == identity.get('episode'))


def existing_playback_references(xstream_profile, profile, items):
    """Find unique, exact URLs from the selected XStream profile; never infer URLs."""
    if (not str(profile).isdigit() or not 1 <= int(profile) <= 10
            or not isinstance(items, list)):
        raise ValueError('valid XStream profile and plan items required')
    root = Path(xstream_profile)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('unsafe XStream profile directory')
    stores = []
    for filename, expected in (('resume_points_p%s.json' % profile, dict),
                               ('watch_history_p%s.json' % profile, list)):
        path = root / filename
        if path.is_symlink():
            raise ValueError('unsafe XStream playback store')
        if not path.exists():
            stores.append([] if expected is list else {})
            continue
        if not path.is_file():
            raise ValueError('invalid XStream playback store')
        value = json.loads(path.read_text('utf-8'))
        if not isinstance(value, expected):
            raise ValueError('invalid XStream playback store')
        stores.append(value)
    resume, history = stores
    references = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        identity = item.get('identity')
        provider = str(item.get('provider_id', ''))
        if not isinstance(identity, dict) or _positive_int(provider) is None:
            continue
        kind = identity.get('kind')

        def matches(record):
            if not isinstance(record, dict) or record.get('stype') != ('series' if kind == 'episode' else 'movie'):
                return False
            name, url = record.get('name'), record.get('url')
            if not isinstance(name, str) or not name.strip() or not isinstance(url, str):
                return False
            try:
                parsed = urlsplit(url)
            except ValueError:
                return False
            if parsed.scheme not in ('http', 'https') or not parsed.hostname:
                return False
            if kind == 'movie':
                found = re.search(r'/([0-9]+)\.[A-Za-z0-9]+$', parsed.path)
                return bool(found and _positive_int(found.group(1)) == int(provider))
            return (kind == 'episode'
                    and str(record.get('series_id', '')) == str(item.get('provider_series_id', ''))
                    and str(record.get('ep_id', '')) == str(item.get('provider_episode_id', ''))
                    and _positive_int(record.get('season_num'), allow_zero=True) == identity.get('season')
                    and _positive_int(record.get('episode_num')) == identity.get('episode'))

        candidates = [record for record in resume.values() if matches(record)]
        if not candidates:
            candidates = [record for record in history if matches(record)]
        unique = {(record.get('name'), record.get('url')): record for record in candidates}
        if len(unique) != 1:
            continue
        record = next(iter(unique.values()))
        reference = {'confidence': 'exact', 'profile': str(profile), 'kind': kind,
                     'provider_id': provider, 'identity': identity,
                     'name': record['name'], 'url': record['url']}
        if kind == 'episode':
            reference.update(series_id=str(item['provider_series_id']),
                ep_id=str(item['provider_episode_id']), season_num=identity['season'],
                episode_num=identity['episode'])
        for source in ('icon', 'title', 'plot'):
            if isinstance(record.get(source), str) and record[source]:
                reference[source] = record[source]
        references[kind + ':' + provider] = reference
    return references, resume


def stage_resume(plan, playback_references, existing=None):
    """Merge only newer, identity-bound remote progress into an in-memory store."""
    if (not isinstance(plan, dict) or not str(plan.get('profile', '')).isdigit()
            or not 1 <= int(plan['profile']) <= 10 or not isinstance(plan.get('items'), list)
            or not isinstance(playback_references, dict)
            or not isinstance(existing, (dict, type(None)))):
        raise ValueError('verified plan, profile, references and existing store required')
    profile = str(plan['profile'])
    staged, deferred = dict(existing or {}), []
    added = updated = 0
    for item in plan['items']:
        if not isinstance(item, dict) or 'position' not in item:
            continue
        provider = str(item.get('provider_id', ''))
        identity = item.get('identity')
        kind = identity.get('kind', '') if isinstance(identity, dict) else ''
        reference = playback_references.get(kind + ':' + provider)
        if _positive_int(provider) is None or not _valid_reference(item, reference, profile):
            deferred.append({'provider_id': provider, 'reason': 'identity_unverified'})
            continue
        position, duration = item.get('position'), item.get('duration')
        if (type(position) not in (int, float) or type(duration) not in (int, float)
                or not math.isfinite(position) or not math.isfinite(duration)
                or duration < 120 or position < 60 or position > duration * 0.93):
            deferred.append({'provider_id': provider, 'reason': 'duration_or_position_invalid'})
            continue
        remote_stamp = _timestamp(item.get('paused_at'))
        if remote_stamp is None:
            deferred.append({'provider_id': provider, 'reason': 'remote_timestamp_unknown'})
            continue
        name, url = reference['name'], reference['url']
        key = name + '||' + url
        current = staged.get(key)
        if current is not None:
            local_stamp = _timestamp(current.get('timestamp')) if isinstance(current, dict) else None
            if local_stamp is None or local_stamp >= remote_stamp:
                deferred.append({'provider_id': provider,
                    'reason': 'local_timestamp_unknown' if local_stamp is None else 'local_is_not_older'})
                continue
            updated += 1
        else:
            added += 1
        entry = {'name': name, 'url': url, 'position': float(position),
                 'duration': float(duration), 'timestamp': remote_stamp,
                 'stype': 'series' if kind == 'episode' else 'movie'}
        for field in ('title', 'plot', 'icon'):
            if isinstance(reference.get(field), str) and reference[field]:
                entry[field] = reference[field]
        if kind == 'episode':
            entry.update(series_id=str(item['provider_series_id']),
                season_num=int(identity['season']), ep_id=str(item['provider_episode_id']),
                episode_num=int(identity['episode']))
        staged[key] = entry
    return {'staged': staged, 'added': added, 'updated': updated, 'deferred': deferred}
