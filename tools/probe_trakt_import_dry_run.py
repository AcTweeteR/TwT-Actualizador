"""Offline account-bound Trakt import feasibility audit against verified Xtream cache."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile

LIB = Path(__file__).resolve().parents[1] / 'source/0.4.32/addons/service.actweeter/resources'
sys.path.insert(0, str(LIB))
from lib.trakt_provider_index import verified_vod_records
from lib.trakt_sync import import_plan
from lib.trakt_projection import project_watched


def audit(export, cache, profile):
    folder = Path(export)
    raw = (folder / 'snapshot.json').read_bytes()
    manifest = json.loads((folder / 'manifest.json').read_text())
    if hashlib.sha256(raw).hexdigest() != manifest['sha256']:
        raise ValueError('unverified Trakt export')
    exported = json.loads(raw)
    if str(exported['profile']) != str(profile):
        raise PermissionError('wrong profile')
    snapshot = exported['snapshot']
    if not isinstance(snapshot.get('records'), dict) or not isinstance(snapshot.get('history'), list):
        raise ValueError('incomplete Trakt export')
    records = verified_vod_records(cache, profile=profile)
    plan = import_plan(snapshot, records, profile=profile, account=snapshot['account'])
    # Both destination stores are synthetic. No user profile or real playback path is written.
    with tempfile.TemporaryDirectory(prefix='actweeter-trakt-restore-') as directory:
        movies = Path(directory) / 'watched_movies.json'
        episodes = Path(directory) / 'watched_episodes.json'
        movies.write_text('{}')
        episodes.write_text('{}')
        preview = project_watched(plan, profile=profile, account=snapshot['account'],
                                  movie_path=movies, episode_path=episodes, dry_run=True)
        if movies.read_text() != '{}' or episodes.read_text() != '{}':
            raise RuntimeError('dry run unexpectedly mutated a store')
        movie_only = dict(plan, items=[item for item in plan['items']
                                      if item['identity']['kind'] == 'movie'])
        project_watched(movie_only, profile=profile, account=snapshot['account'],
                        movie_path=movies, episode_path=episodes, dry_run=False)
        written = json.loads(movies.read_text())
        if len(written) != preview['movies']:
            raise RuntimeError('synthetic movie restore mismatch')
    return {'verified_vod_records': len(records), 'matched': len(plan['items']),
            'watched_movies_restored_to_temporary_store': len(written),
            'resume_positions_planned': sum('position' in item for item in plan['items']),
            'resume_positions_applied': 0, 'unmatched': len(plan['unavailable']),
            'ambiguous': len(plan['ambiguous']), 'conflicts': len(plan['conflicts']),
            'real_kodi_store_writes': 0, 'remote_writes': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('export')
    parser.add_argument('cache')
    parser.add_argument('--profile', default='1')
    args = parser.parse_args()
    print(json.dumps(audit(args.export, args.cache, args.profile), sort_keys=True))
