"""Match held local watched marks against a complete Trakt account snapshot.

Never infer absence from partial snapshots or conflicting external identifiers.
"""
from .trakt_sync import normalize_ids


def remote_watched_status(remote, content, *, account):
    if (not isinstance(remote, dict) or remote.get('complete') is not True
            or remote.get('account') != account or not isinstance(remote.get('records'), dict)
            or not isinstance(content, dict) or content.get('kind') not in ('movie', 'episode')):
        return 'unverified'
    ids = normalize_ids(content.get('ids'))
    if not ids:
        return 'unverified'
    seen = False
    for row in remote['records'].values():
        if not isinstance(row, dict) or not isinstance(row.get('identity'), dict):
            return 'unverified'
        remote_id = row['identity']
        if remote_id.get('kind') not in ('movie', 'episode'):
            return 'unverified'
        if remote_id.get('kind') != content['kind']:
            continue
        if content['kind'] == 'episode' and any(
                remote_id.get(k) != content.get(k) for k in ('season', 'episode')):
            continue
        other = normalize_ids(remote_id.get('ids'))
        if not other:
            return 'unverified'
        common = ids.keys() & other.keys()
        if not common:
            continue
        same = any(ids[key] == other[key] for key in common)
        different = any(ids[key] != other[key] for key in common)
        if same and different:
            return 'conflict'
        if same:
            seen = seen or bool(row.get('watched_at'))
    return 'watched' if seen else 'missing'
