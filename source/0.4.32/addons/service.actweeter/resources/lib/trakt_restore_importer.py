"""Account-bound, offline Trakt import preparation for XStream.

No Trakt mutations. No real Kodi writes: this builds and validates a plan.
A separate stopped-Kodi transaction is required to apply both stores.
"""
import hashlib
import json
from pathlib import Path
from .trakt_episode_index import verified_episode_records
from .trakt_identity_resolver import resolve_identities
from .trakt_sync import import_plan, validate_export


def prepare_tmdb_restore(export_directory, *, profile, account,
                         reference_directory=None):
    """Project verified Trakt watched states directly onto XStream TMDb IDs.

    This projection deliberately does not inspect or require the Xtream catalog.
    Resume points remain provider-bound and are handled only by the strict path.
    """
    folder = Path(export_directory)
    if folder.is_symlink() or any((folder / name).is_symlink()
                                  for name in ('snapshot.json', 'manifest.json')):
        raise ValueError('unsafe export path')
    raw = (folder / 'snapshot.json').read_bytes()
    manifest = json.loads((folder / 'manifest.json').read_text('utf-8'))
    if manifest.get('sha256') != hashlib.sha256(raw).hexdigest():
        raise ValueError('snapshot checksum mismatch')
    if manifest.get('status') != 'READ_ONLY_EXPORT_VERIFIED':
        raise ValueError('unverified export')
    payload = json.loads(raw)
    reference = None
    if reference_directory is not None:
        folder2 = Path(reference_directory)
        if folder2.is_symlink() or any((folder2 / name).is_symlink()
                                       for name in ('snapshot.json', 'manifest.json')):
            raise ValueError('unsafe reference export')
        raw2 = (folder2 / 'snapshot.json').read_bytes()
        manifest2 = json.loads((folder2 / 'manifest.json').read_text('utf-8'))
        if (manifest2.get('status') != 'READ_ONLY_EXPORT_VERIFIED'
                or hashlib.sha256(raw2).hexdigest() != manifest2.get('sha256')):
            raise ValueError('reference checksum mismatch')
        reference = (json.loads(raw2), manifest2)
    snapshot = validate_export(payload, manifest, profile=profile, account=account,
                               legacy_reference=reference)
    items, missing_tmdb = [], 0
    for record in snapshot['records'].values():
        identity = record['identity']
        kind = identity.get('kind')
        if kind not in ('movie', 'episode') or not record.get('watched_at'):
            continue
        ids = identity.get('ids') or {}
        tmdb_id = ids.get('tmdb')
        if not isinstance(tmdb_id, str) or not tmdb_id.isdigit() or int(tmdb_id) < 1:
            missing_tmdb += 1
            continue
        item = {'identity': identity, 'watched': True,
                'watched_at': record['watched_at']}
        if kind == 'episode':
            season, episode = identity.get('season'), identity.get('episode')
            if type(season) is not int or season < 0 or type(episode) is not int or episode < 1:
                missing_tmdb += 1
                continue
        items.append(item)
    playback_deferred = sum(bool(row.get('paused_at')) for row in snapshot['records'].values())
    return {'schema': 1, 'account': account, 'profile': str(profile),
            'items': items, 'summary': {'watched_tmdb_records': len(items),
                                        'missing_tmdb_identity': missing_tmdb,
                                        'playback_deferred_without_provider_url': playback_deferred}}


def preview_tmdb_changes(plan, xstream_directory, *, profile):
    """Read-only TMDb projection preview against the profile's native stores."""
    root = Path(xstream_directory)
    if root.is_symlink() or not str(profile).isdigit() or int(profile) < 1:
        raise ValueError('unsafe XStream profile')

    def read(name):
        path = root / ('%s_p%s.json' % (name, profile))
        if path.is_symlink():
            raise ValueError('unsafe XStream history store')
        if not path.exists():
            return {}
        value = json.loads(path.read_text('utf-8'))
        if not isinstance(value, dict):
            raise ValueError('invalid XStream history store')
        return value

    watched = read('watched_movies')
    result = {'movies_new': 0, 'episodes_new': 0, 'already_local': 0,
              'conflicts': 0, 'items': []}
    for item in plan.get('items', []):
        identity = item.get('identity') or {}
        ids = identity.get('ids') or {}
        tmdb_id = str(ids.get('tmdb') or '')
        if not tmdb_id.isdigit() or int(tmdb_id) < 1:
            result['conflicts'] += 1
            continue
        if identity.get('kind') == 'movie':
            key = 'tmdb:movie:' + tmdb_id
            target = 'movies_new'
        elif identity.get('kind') == 'episode':
            season, episode = identity.get('season'), identity.get('episode')
            if type(season) is not int or season < 0 or type(episode) is not int or episode < 1:
                result['conflicts'] += 1
                continue
            key = 'tmdb:episode:%s:s%d:e%d' % (tmdb_id, season, episode)
            target = 'episodes_new'
        else:
            result['conflicts'] += 1
            continue
        current = watched.get(key)
        if current is True:
            result['already_local'] += 1
        elif current is False:
            result['conflicts'] += 1
        elif current is not None:
            result['conflicts'] += 1
        else:
            result[target] += 1
            result['items'].append(item)
    return result


def prepare_restore(export_directory, xstream_directory, *, profile, account,
                    reference_directory=None, include_candidates=False):
    folder = Path(export_directory)
    if folder.is_symlink() or any((folder / name).is_symlink() for name in ('snapshot.json', 'manifest.json')):
        raise ValueError('unsafe export path')
    raw = (folder / 'snapshot.json').read_bytes()
    manifest = json.loads((folder / 'manifest.json').read_text('utf-8'))
    if manifest.get('sha256') != hashlib.sha256(raw).hexdigest():
        raise ValueError('snapshot checksum mismatch')
    if manifest.get('status') != 'READ_ONLY_EXPORT_VERIFIED':
        raise ValueError('unverified export')
    payload = json.loads(raw)
    reference = None
    if reference_directory is not None:
        folder2 = Path(reference_directory)
        if folder2.is_symlink() or any((folder2 / name).is_symlink() for name in ('snapshot.json', 'manifest.json')):
            raise ValueError('unsafe reference export')
        raw2 = (folder2 / 'snapshot.json').read_bytes()
        manifest2 = json.loads((folder2 / 'manifest.json').read_text('utf-8'))
        if (manifest2.get('status') != 'READ_ONLY_EXPORT_VERIFIED'
                or hashlib.sha256(raw2).hexdigest() != manifest2.get('sha256')):
            raise ValueError('reference checksum mismatch')
        reference = (json.loads(raw2), manifest2)
    snapshot = validate_export(payload, manifest, profile=profile, account=account,
                               legacy_reference=reference)
    resolution = resolve_identities(xstream_directory, profile=profile,
                                    export_payload=payload,
                                    include_candidates=include_candidates)
    movies = [item for item in resolution['verified'] if item['kind'] == 'movie']
    strict_shows = [item for item in resolution['verified'] if item['kind'] == 'show']
    if resolution['summary'].get('provider_scope_available'):
        episodes = verified_episode_records(xstream_directory, profile=profile, snapshot=snapshot,
                                            show_records=strict_shows)
    else:
        episodes = {'records': [], 'deferred': sum(
            record.get('identity', {}).get('kind') == 'episode'
            for record in snapshot.get('records', {}).values())}
    plan = import_plan(snapshot, movies + episodes['records'], profile=profile, account=account)
    episode_by_id = {record['provider_id']: record for record in episodes['records']}
    for item in plan['items']:
        if item['identity']['kind'] == 'episode':
            provider = episode_by_id[item['provider_id']]
            item['provider_series_id'] = provider['provider_series_id']
            item['provider_episode_id'] = provider['provider_episode_id']
    plan['identity_resolution'] = dict(resolution['summary'],
        verified_episodes=len(episodes['records']), deferred_episodes=episodes['deferred'])
    return plan


def preview_changes(plan, xstream_directory, *, profile):
    """Exact additive delta against current stores, with no writes of any kind."""
    from .trakt_resume_bridge import existing_playback_references, stage_resume
    root = Path(xstream_directory)
    def store(name):
        path = root / (name + '_p' + str(profile) + '.json')
        if path.is_symlink():
            raise ValueError('unsafe personal store')
        data = json.loads(path.read_text('utf-8')) if path.exists() else {}
        if not isinstance(data, dict):
            raise ValueError('invalid personal store')
        return data
    movies, episodes = store('watched_movies'), store('watched_episodes')
    references, existing = existing_playback_references(root, str(profile), plan['items'])
    resume = stage_resume(plan, references, existing)
    accepted_resume = set()
    for item in plan['items']:
        if 'position' not in item:
            continue
        checked = stage_resume(dict(plan, items=[item]), references, existing)
        if checked['added'] + checked['updated']:
            accepted_resume.add((item['identity']['kind'], item['provider_id']))
    summary = {'matched': len(plan['items']), 'movies_watched_added': 0,
               'episodes_watched_added': 0, 'watched_already_local': 0,
               'local_unwatched_conflicts': 0, 'resumes_added': resume['added'],
               'resumes_updated': resume['updated'],
               'resumes_local_preserved': len(existing) - resume['updated'],
               'resumes_deferred': len(resume['deferred'])}
    delta = []
    for original in plan['items']:
        item = dict(original)
        kind = item['identity']['kind']
        if item.get('watched'):
            if kind == 'movie':
                current = movies.get(item['provider_id'])
                if current is not None and type(current) is not bool:
                    raise ValueError('invalid movie watched value')
                present = current is True
                blocked = current is False
            else:
                seasons = episodes.get(item['provider_series_id'], {})
                if not isinstance(seasons, dict):
                    raise ValueError('invalid episode watched store')
                values = seasons.get(str(item['identity']['season']), [])
                if not isinstance(values, list):
                    raise ValueError('invalid season watched store')
                present = str(item['provider_episode_id']) in set(map(str, values))
                blocked = False
            if present or blocked:
                item.pop('watched', None); item.pop('watched_at', None)
                summary['local_unwatched_conflicts' if blocked else 'watched_already_local'] += 1
            else:
                summary['movies_watched_added' if kind == 'movie' else 'episodes_watched_added'] += 1
        if (kind, item['provider_id']) not in accepted_resume:
            for key in ('position', 'duration', 'paused_at'):
                item.pop(key, None)
        if item.get('watched') or 'position' in item:
            delta.append(item)
    return {'plan': dict(plan, items=delta), 'summary': summary, 'resume_deferred': resume['deferred']}
