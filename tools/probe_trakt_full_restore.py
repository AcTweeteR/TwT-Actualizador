"""Dry-run full Trakt watched projection into disposable XStream stores."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'source/0.4.32/addons/service.actweeter/resources'))
from lib.trakt_episode_index import verified_episode_records
from lib.trakt_provider_index import verified_vod_records
from lib.trakt_projection import project_watched
from lib.trakt_restore_importer import prepare_restore


def run(export, cache, profile='1'):
    folder=Path(export)
    raw=(folder/'snapshot.json').read_bytes()
    manifest=json.loads((folder/'manifest.json').read_text())
    if hashlib.sha256(raw).hexdigest()!=manifest['sha256']:
        raise ValueError('snapshot checksum mismatch')
    payload=json.loads(raw)
    if str(payload['profile'])!=str(profile):
        raise PermissionError('wrong profile')
    snapshot=payload['snapshot']
    if manifest.get('status') != 'READ_ONLY_EXPORT_VERIFIED' or not isinstance(payload.get('responses'), list):
        raise ValueError('unverified export provenance')
    plan=prepare_restore(folder,cache,profile=profile,account=snapshot['account'])
    with tempfile.TemporaryDirectory(prefix='actweeter-trakt-full-') as directory:
        movie=Path(directory)/'watched_movies.json'
        episode=Path(directory)/'watched_episodes.json'
        movie.write_text('{}');episode.write_text('{}')
        for kind in ('movie','episode'):
            subset=dict(plan,items=[row for row in plan['items'] if row['identity']['kind']==kind])
            project_watched(subset,profile=profile,account=snapshot['account'],movie_path=movie,
                            episode_path=episode,dry_run=False)
        movies=json.loads(movie.read_text());shows=json.loads(episode.read_text())
        episode_count=sum(len(eps) for seasons in shows.values() for eps in seasons.values())
        expected_movies=sum(row.get('watched') is True and row['identity']['kind']=='movie' for row in plan['items'])
        expected_episodes=sum(row.get('watched') is True and row['identity']['kind']=='episode' for row in plan['items'])
        if len(movies)!=expected_movies or episode_count!=expected_episodes:
            raise RuntimeError('temporary store verification failed: movies=%s/%s episodes=%s/%s' % (len(movies),expected_movies,episode_count,expected_episodes))
    return {'matched':len(plan['items']),'watched_movies_restored':len(movies),
            'watched_episodes_restored':episode_count,'resume_positions_planned':sum('position' in x for x in plan['items']),
            'resume_positions_restored':0,'unmatched':len(plan['unavailable']),
            'ambiguous':len(plan['ambiguous']),'conflicts':len(plan['conflicts']),
            'real_kodi_writes':0,'remote_writes':0}

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('export');parser.add_argument('cache');parser.add_argument('--profile',default='1')
    args=parser.parse_args();print(json.dumps(run(args.export,args.cache,args.profile),sort_keys=True))
