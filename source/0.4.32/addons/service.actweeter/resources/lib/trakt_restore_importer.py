"""Account-bound, offline Trakt import preparation for XStream.

No Trakt mutations. No real Kodi writes: this builds and validates a plan.
A separate stopped-Kodi transaction is required to apply both stores.
"""
import hashlib
import json
from pathlib import Path
from .trakt_episode_index import verified_episode_records
from .trakt_provider_index import verified_vod_records
from .trakt_sync import import_plan


def prepare_restore(export_directory, xstream_directory, *, profile, account):
    folder = Path(export_directory)
    if folder.is_symlink():
        raise ValueError('unsafe export path')
    raw = (folder / 'snapshot.json').read_bytes()
    manifest = json.loads((folder / 'manifest.json').read_text('utf-8'))
    if manifest.get('sha256') != hashlib.sha256(raw).hexdigest():
        raise ValueError('snapshot checksum mismatch')
    if manifest.get('status') != 'READ_ONLY_EXPORT_VERIFIED':
        raise ValueError('unverified export')
    payload = json.loads(raw)
    snapshot = payload['snapshot']
    if (payload.get('schema_version') != 1 or snapshot.get('complete') is not True
            or not isinstance(snapshot.get('records'), dict)
            or not isinstance(snapshot.get('history'), list)):
        raise ValueError('complete supported snapshot required')
    if str(payload.get('profile')) != str(profile) or snapshot.get('account') != account:
        raise PermissionError('Trakt account or XStream profile mismatch')
    movies = verified_vod_records(xstream_directory, profile=profile)
    episodes = verified_episode_records(xstream_directory, profile=profile, snapshot=snapshot)
    plan = import_plan(snapshot, movies + episodes['records'], profile=profile, account=account)
    episode_by_id = {record['provider_id']: record for record in episodes['records']}
    for item in plan['items']:
        if item['identity']['kind'] == 'episode':
            provider = episode_by_id[item['provider_id']]
            item['provider_series_id'] = provider['provider_series_id']
            item['provider_episode_id'] = provider['provider_episode_id']
    return plan
