"""Offline provider membership validation for TMDb-verified XStream shows.

A series stream list is not an episode inventory. Never synthesize episode IDs.
"""
import json
from pathlib import Path
from .trakt_series_index import verified_show_records
from .trakt_provider_index import catalog_generation_path
from .trakt_sync import ProviderIndex, identity


def series_inventory(directory, *, profile, snapshot):
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get('records'), dict):
        raise ValueError('snapshot records required')
    if not str(profile).isdigit() or int(profile) < 1:
        raise ValueError('invalid profile')
    root = Path(directory)
    stream_key = 'xtream_streams_series'
    legacy = root / ('data_cache_p%s_%s.json' % (profile, stream_key))
    stream_path = catalog_generation_path(root, profile, stream_key, legacy)
    if stream_path.is_symlink():
        raise ValueError('unsafe series cache')
    streams = json.loads(stream_path.read_text('utf-8'))['_data']
    if not isinstance(streams, list):
        raise ValueError('invalid series stream list')
    ids = [str(row['series_id']) for row in streams if isinstance(row, dict)
           and str(row.get('series_id', '')).isdigit() and int(row['series_id']) > 0]
    # Xtream legitimately repeats a series in several provider categories.
    available = set(ids)
    verified = [row for row in verified_show_records(root, profile=profile)
                if row['provider_id'] in available]
    index = ProviderIndex(verified, profile=profile)
    candidates = []
    unavailable = 0
    for row in snapshot['records'].values():
        content = row.get('identity', {})
        if content.get('kind') != 'episode':
            continue
        show = identity('show', content.get('ids'))
        if show is None:
            continue
        status, matches = index.match(show)
        if status == 'exact':
            candidates.append({'provider_series_id': matches[0]['provider_id'],
                               'season': content['season'], 'episode': content['episode'],
                               'episode_id_verified': False})
        else:
            unavailable += 1
    return {'provider_series_count': len(available), 'verified_show_count': len(verified),
            'episode_candidates': candidates, 'unmatched_episodes': unavailable,
            'verified_episode_count': 0}
