"""Exact current-provider show identities; no inferred episodes or title matches."""
from pathlib import Path
try:
    from .trakt_provider_index import catalog_members, read_object, external_ids
except ImportError:
    from trakt_provider_index import catalog_members, read_object, external_ids


def verified_show_records(directory, *, profile):
    root = Path(directory)
    members = catalog_members(root, profile, 'series')
    state = read_object(root / ('series_changes_p%s.json' % profile)) or {}
    inventories = state.get('episode_inventory', {})
    enriched = {}
    for path in root.glob('data_cache_p%s_premium_meta_series_*.json' % profile):
        enriched.setdefault(path.stem.rsplit('_', 2)[-2], []).append(path)
    result = []
    for provider_id, row in members.items():
        sources = [external_ids(row)]
        details = read_object(root / ('data_cache_p%s_series_info_%s.json' % (profile, provider_id)))
        if details:
            sources.append(external_ids(details.get('info')))
        for path in sorted(enriched.get(provider_id, [])):
            value = read_object(path)
            if value:
                sources.append(external_ids(value.get('data')))
        inventory = inventories.get(provider_id, {}) if isinstance(inventories, dict) else {}
        sources.append(external_ids(inventory))
        ids, conflict = {}, False
        for source in sources:
            if any(ids[key] != value for key, value in source.items() if key in ids):
                conflict = True; break
            ids.update(source)
        if ids and not conflict:
            result.append({'profile': str(profile), 'kind': 'show', 'provider_id': provider_id,
                           'ids': ids, 'confidence': 'verified', 'evidence': 'current_catalog_metadata'})
    return result
