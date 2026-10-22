"""Safe reconciliation of Kodi, Trakt and TMDb collection snapshots.

Pure planning only: never treats an unreachable/partial list as empty, never
infers deletion from a missing item, and never conflates Pending with Favorites.
Identifiers must be verified TMDb IDs. Live channels and folder shortcuts are
not portable movie/TV identities and are intentionally excluded.
"""

COLLECTIONS = ('pending', 'favorites')
SOURCES = ('kodi', 'trakt', 'tmdb')
KINDS = ('movie', 'show')


def key(item):
    if not isinstance(item, dict) or item.get('kind') not in KINDS:
        raise ValueError('unsupported collection item kind')
    number = str(item.get('tmdb_id', ''))
    if not number.isascii() or not number.isdecimal() or int(number) < 1:
        raise ValueError('verified TMDb identity required')
    return item['kind'] + ':tmdb:' + str(int(number))


def snapshot(source, collection, rows, *, account, complete=True):
    if source not in SOURCES or collection not in COLLECTIONS or not account:
        raise ValueError('account, source and collection required')
    if complete is not True or not isinstance(rows, list):
        raise ValueError('incomplete remote/local list cannot be reconciled')
    values = {}
    for row in rows:
        identifier = key(row)
        values[identifier] = {'kind': row['kind'], 'tmdb_id': str(int(row['tmdb_id']))}
    return {'source': source, 'collection': collection, 'account': account,
            'complete': True, 'items': values}


def bootstrap(snapshots, *, account, collection):
    """Safe first sync: union-only additions, with no remote/local removals."""
    sources = {}
    for state in snapshots:
        if (state.get('source') not in SOURCES or state.get('source') in sources or
                state.get('account') != account or state.get('collection') != collection or
                state.get('complete') is not True):
            raise ValueError('invalid, duplicate or foreign collection snapshot')
        for identifier, item in state.get('items', {}).items():
            if key(item) != identifier:
                raise ValueError('tampered collection identity')
        sources[state['source']] = state['items']
    if set(sources) != set(SOURCES):
        raise ValueError('all three complete account-bound snapshots required')
    merged = {}
    for records in sources.values():
        merged.update(records)
    return {'account': account, 'collection': collection,
            'additions': {source: [merged[k] for k in sorted(merged) if k not in rows]
                          for source, rows in sources.items()},
            'removals': {source: [] for source in SOURCES},
            'count': len(merged)}


def delta(previous, current, *, source):
    """Only a complete new observation against a complete known baseline yields removals."""
    if (previous.get('source') != source or current.get('source') != source or
            previous.get('account') != current.get('account') or
            previous.get('collection') != current.get('collection') or
            previous.get('complete') is not True or current.get('complete') is not True):
        raise ValueError('cannot derive changes from incomplete or cross-account data')
    before, after = previous['items'], current['items']
    return {'added': [after[k] for k in sorted(after.keys() - before.keys())],
            'removed': [before[k] for k in sorted(before.keys() - after.keys())]}
