"""Account-bound, offline Trakt import preparation for XStream.

No Trakt mutations. No real Kodi writes: this builds and validates a plan.
A separate stopped-Kodi transaction is required to apply both stores.
"""
import hashlib
import json
from pathlib import Path
from .trakt_episode_index import verified_episode_records
from .trakt_provider_index import verified_vod_records
from .trakt_sync import import_plan, validate_export


def prepare_restore(export_directory, xstream_directory, *, profile, account, reference_directory=None):
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
