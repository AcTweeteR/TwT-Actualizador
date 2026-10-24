"""Read-only, exact episode mapping from XStream series-change inventory.

Provider series identity must be verified separately; no title matching or
fabricated episode IDs. Incomplete inventories never authorize import.
"""
import json
from pathlib import Path
try:
    from .trakt_provider_index import read_object, duration_seconds
except ImportError:
    from trakt_provider_index import read_object, duration_seconds
try:
    from .trakt_sync import ProviderIndex, identity
except ImportError:
    from trakt_sync import ProviderIndex, identity


def verified_episode_records(directory, *, profile, snapshot, show_records):
    root = Path(directory)
    path = root / ('series_changes_p%s.json' % profile)
    if path.is_symlink():
        raise ValueError('unsafe series inventory')
    raw = read_object(path) or {}
    inventories = raw.get('episode_inventory')
    if inventories is None:
        inventories = {}
    if not isinstance(inventories, dict):
        raise ValueError('missing episode inventory')
    if not isinstance(show_records, list) or any(
            not isinstance(show, dict) or show.get('kind') != 'show'
            or str(show.get('profile')) != str(profile)
            or (show.get('status') != 'VERIFIED' and show.get('confidence') != 'verified')
            or not str(show.get('provider_id', '')).isdigit()
            or not isinstance(show.get('ids'), dict) or not show['ids']
            for show in show_records):
        raise ValueError('invalid verified show identities')
    shows = show_records
    show_by_id = {x['provider_id']: x for x in shows}
    index = ProviderIndex(shows, profile=profile)
    exact = []
    deferred = 0
    for record in snapshot.get('records', {}).values():
        content = record.get('identity', {})
        if content.get('kind') != 'episode':
            continue
        show = identity('show', content.get('ids'))
        if show is None:
            deferred += 1
            continue
        status, matches = index.match(show)
        if status != 'exact':
            deferred += 1
            continue
        series_id = matches[0]['provider_id']
        inventory = inventories.get(series_id, {})
        details = read_object(root / ('data_cache_p%s_series_info_%s.json' % (profile, series_id)))
        if details is not None:
            grouped = details.get('episodes')
            rows, valid = [], isinstance(grouped, dict)
            for season, episodes in (grouped.items() if valid else []):
                if not str(season).isdigit() or not isinstance(episodes, list):
                    valid = False; break
                for episode in episodes:
                    if (not isinstance(episode, dict) or not str(episode.get('id', '')).isdigit()
                            or int(episode['id']) < 1 or not str(episode.get('episode_num', '')).isdigit()
                            or int(episode['episode_num']) < 1
                            or (episode.get('season') is not None and str(episode['season']) != str(season))):
                        valid = False; break
                    rows.append({'season': int(season), 'episode': int(episode['episode_num']),
                                 'provider_id': str(episode['id']),
                                 'duration_seconds': duration_seconds(episode.get('info') or {})})
            inventory = {'complete': valid, 'episodes': rows}
        if inventory.get('complete') is not True or not isinstance(inventory.get('episodes'), list):
            deferred += 1
            continue
        candidates = [ep for ep in inventory['episodes'] if isinstance(ep, dict)
                      and str(ep.get('season')) == str(content['season'])
                      and str(ep.get('episode')) == str(content['episode'])]
        if len(candidates) != 1:
            deferred += 1
            continue
        provider_episode = str(candidates[0].get('provider_id', ''))
        if not provider_episode.isdigit() or int(provider_episode) < 1:
            deferred += 1
            continue
        exact.append({'profile': str(profile), 'kind': 'episode',
                      'provider_id': provider_episode, 'provider_series_id': series_id,
                      'provider_episode_id': provider_episode,
                      'show_ids': show_by_id[series_id]['ids'],
                      'season': content['season'], 'episode': content['episode'],
                      'confidence': 'verified',
                      'duration_seconds': candidates[0].get('duration_seconds')})
    return {'records': exact, 'deferred': deferred}
