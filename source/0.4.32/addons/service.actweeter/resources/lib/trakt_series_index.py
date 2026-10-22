"""Strict show identity index from XStream premium series metadata cache.

Show-level mappings do not imply any episode is present or playable.
"""
import json
from pathlib import Path
from .trakt_sync import normalize_ids


def verified_show_records(directory, *, profile):
    if not str(profile).isdigit() or int(profile) < 1:
        raise ValueError('invalid profile')
    result = []
    for path in sorted(Path(directory).glob('data_cache_p%s_premium_meta_series_*.json' % profile)):
        if path.is_symlink():
            continue
        provider_id = path.stem.rsplit('_', 2)[-2]
        if not provider_id.isdigit() or int(provider_id) < 1:
            continue
        try:
            payload = json.loads(path.read_text('utf-8'))
            data = payload['data']
            if not isinstance(data, dict):
                continue
            ids = normalize_ids({'tmdb': data.get('tmdb_id'), 'imdb': data.get('imdb_id')})
            if 'tmdb' not in ids:
                continue
            result.append({'profile': str(profile), 'kind': 'show',
                           'provider_id': provider_id, 'ids': ids,
                           'confidence': 'verified', 'evidence': 'premium_series_cache'})
        except (ValueError, TypeError, KeyError, OSError, UnicodeError):
            continue
    return result
