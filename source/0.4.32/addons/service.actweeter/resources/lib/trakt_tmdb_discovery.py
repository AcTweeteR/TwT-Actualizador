"""Offline, opt-in TMDb candidate discovery. Never writes Kodi/Trakt state.

This module produces a report, not verified restore identities. A separate
provider-bound validation is mandatory before any restore plan may use it.
"""
import json
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

from .trakt_identity_resolver import _title_key, _year
from .trakt_provider_index import catalog_members


def candidate_index(directory, profile):
    indexes = {}
    for kind, stype, field in (("movie", "movie", "stream_id"), ("show", "series", "series_id")):
        index = defaultdict(lambda: defaultdict(set))
        for provider_id, row in catalog_members(directory, profile, stype).items():
            title = _title_key(row.get('title') or row.get('name'))
            year = _year(row.get('year'))
            if title and year:
                index[(title, year)][provider_id].add(field)
        indexes[kind] = index
    return indexes


def discover(snapshot, directory, profile, fetch, limit=None):
    """Only exact, unique title/year matches; never actionable by themselves."""
    index = candidate_index(directory, profile)
    targets = {'movie': set(), 'show': set()}
    for record in snapshot.get('records', {}).values():
        identity = record.get('identity', {})
        kind = 'movie' if identity.get('kind') == 'movie' else 'show' if identity.get('kind') == 'episode' else None
        if kind and identity.get('ids', {}).get('tmdb'):
            targets[kind].add(str(identity['ids']['tmdb']))
    output = []
    for kind in ('show', 'movie'):
        for tmdb_id in sorted(targets[kind], key=lambda x: int(x)):
            if limit is not None and len(output) >= limit:
                return output
            try:
                meta = fetch(kind, tmdb_id)
                title = meta.get('title') or meta.get('name')
                year = _year(meta.get('release_date') or meta.get('first_air_date'))
                titles = {title, meta.get('original_title'), meta.get('original_name')}
                matches = {}
                for candidate_title in titles:
                    if candidate_title:
                        matches.update(index[kind].get((_title_key(candidate_title), year), {}))
                providers = matches
                status = 'candidate' if len(providers) == 1 else 'ambiguous' if len(providers) > 1 else 'pending'
                output.append({'kind': kind, 'tmdb_id': tmdb_id, 'status': status,
                               'provider_id': next(iter(providers)) if status == 'candidate' else None,
                               'year': year, 'title': title})
            except (OSError, ValueError, KeyError, TimeoutError) as exc:
                output.append({'kind': kind, 'tmdb_id': tmdb_id, 'status': 'lookup_error',
                               'error_type': type(exc).__name__})
    return output


def tmdb_fetch(api_key, timeout=8, pause=0.12):
    def fetch(kind, tmdb_id):
        query = urllib.parse.urlencode({'api_key': api_key, 'language': 'es-ES'})
        url = 'https://api.themoviedb.org/3/%s/%s?%s' % ('movie' if kind == 'movie' else 'tv', tmdb_id, query)
        with urllib.request.urlopen(url, timeout=timeout) as response:
            data = json.load(response)
        time.sleep(pause)
        return data
    return fetch
