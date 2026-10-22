"""Read-only, exact episode mapping from XStream series-change inventory.

Provider series identity must be verified separately; no title matching or
fabricated episode IDs. Incomplete inventories never authorize import.
"""
import json
from pathlib import Path
from .trakt_series_index import verified_show_records
from .trakt_sync import ProviderIndex, identity


def verified_episode_records(directory, *, profile, snapshot):
    root = Path(directory)
    path = root / ('series_changes_p%s.json' % profile)
    if path.is_symlink():
        raise ValueError('unsafe series inventory')
    raw = json.loads(path.read_text('utf-8'))
    inventories = raw.get('episode_inventory')
    if not isinstance(inventories, dict):
        raise ValueError('missing episode inventory')
    shows = verified_show_records(root, profile=profile)
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
                      'confidence': 'verified'})
    return {'records': exact, 'deferred': deferred}
