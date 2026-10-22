"""Offline, exact Xtream VOD identity index from cached provider details."""
import json
from pathlib import Path
from .trakt_sync import normalize_ids


def verified_vod_records(directory, *, profile):
    if not str(profile).isdigit() or int(profile) < 1:
        raise ValueError('invalid profile')
    root = Path(directory)
    records = []
    for path in sorted(root.glob('data_cache_p%s_vod_info_*.json' % profile)):
        if path.is_symlink():
            continue
        provider_id = path.stem.rsplit('_', 1)[-1]
        if not provider_id.isdigit() or int(provider_id) < 1:
            continue
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            info = data['info']
            if str(data['movie_data']['stream_id']) != provider_id:
                continue
            ids = normalize_ids({'tmdb': info.get('tmdb_id')})
            if 'tmdb' not in ids:
                continue
            seconds = info.get('duration_secs')
            if type(seconds) not in (int, float) or not 0 < seconds < 86400:
                seconds = None
            records.append({'profile': str(profile), 'kind': 'movie',
                            'provider_id': provider_id, 'ids': ids,
                            'confidence': 'verified', 'duration_seconds': seconds})
        except (ValueError, TypeError, KeyError, OSError, UnicodeError):
            continue
    return records
