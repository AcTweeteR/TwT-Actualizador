#!/usr/bin/env python3
"""Private deterministic Trakt-to-Mac preview and read-only performance probe."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import resource
import statistics
import sys
import time
import tracemalloc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / 'source/0.4.32/addons/service.actweeter/resources'))
from lib.trakt_restore_importer import prepare_restore, preview_changes
from lib.trakt_provider_index import catalog_members
from lib.trakt_episode_index import verified_episode_records
from lib.trakt_identity_resolver import resolve_identities
from lib.trakt_auto_cycle import catalog_generation
from lib.trakt_sync import ProviderIndex, identity


def safe_write(path, value):
    with path.open('x') as stream:
        path.chmod(0o600); json.dump(value,stream,indent=2,ensure_ascii=False)


def fingerprints(root, profile):
    names=['watched_movies','watched_episodes','resume_points','watch_history','favorites']
    return {name:hashlib.sha256((root/(name+'_p'+profile+'.json')).read_bytes()).hexdigest()
            for name in names if (root/(name+'_p'+profile+'.json')).exists()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export',type=Path,required=True)
    parser.add_argument('--catalog',type=Path)
    parser.add_argument('--local',type=Path,default=Path.home()/'Library/Application Support/Kodi/userdata/addon_data/plugin.video.xstream-pro')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--samples',type=int,default=10)
    parser.add_argument('--profile',default='1')
    args=parser.parse_args()
    if not 1<=args.samples<=100 or args.output.is_symlink():parser.error('safe output and sample count required')
    output=args.output.resolve()
    kodi=Path.home()/'Library/Application Support/Kodi'
    if (output==ROOT or ROOT in output.parents or output==kodi or kodi in output.parents):
        parser.error('private output outside repository and Kodi required')
    output.mkdir(mode=0o700,parents=True,exist_ok=True)
    if output.stat().st_mode&0o077:parser.error('mode-0700 output required')
    payload=json.loads((args.export/'snapshot.json').read_text());snapshot=payload['snapshot']
    catalog=args.catalog or args.local
    before=fingerprints(args.local,args.profile)
    samples=[]
    for _ in range(args.samples):
        start,cpu=time.perf_counter(),time.process_time()
        plan=prepare_restore(args.export,catalog,profile=args.profile,account=snapshot['account'])
        preview=preview_changes(plan,args.local,profile=args.profile)
        samples.append({'wall_ms':(time.perf_counter()-start)*1000,'cpu_ms':(time.process_time()-cpu)*1000})
    resolution=resolve_identities(catalog,profile=args.profile,export_payload=payload,
                                  include_candidates=True)
    movies=[row for row in resolution['verified'] if row['kind']=='movie']
    shows=[row for row in resolution['verified'] if row['kind']=='show']
    episodes=(verified_episode_records(catalog,profile=args.profile,snapshot=snapshot,
                                       show_records=shows)
              if resolution['summary'].get('provider_scope_available') else
              {'records':[], 'deferred':sum(r.get('identity',{}).get('kind')=='episode'
                                            for r in snapshot.get('records',{}).values())})
    show_index=ProviderIndex(shows,profile=args.profile)
    unresolved={'movie_identity_pending':0,'show_identity_pending':0,'episode_inventory_pending':0}
    for key in plan['unavailable']:
        content=snapshot['records'][key]['identity']
        if content['kind']=='movie':unresolved['movie_identity_pending']+=1
        else:
            status,_=show_index.match(identity('show',content['ids']))
            unresolved['episode_inventory_pending' if status=='exact' else 'show_identity_pending']+=1
    metrics={}
    for key in ('wall_ms','cpu_ms'):
        values=sorted(row[key] for row in samples)
        metrics[key]={'p50':round(statistics.median(values),3),
                      'p90':round(values[math.ceil(len(values)*.9)-1],3),
                      'min':round(values[0],3),'max':round(values[-1],3)}
    stamps=[]
    for _ in range(10):
        start=time.perf_counter(); catalog_generation(catalog,args.profile)
        stamps.append((time.perf_counter()-start)*1000)
    tracemalloc.start()
    prepare_restore(args.export,catalog,profile=args.profile,account=snapshot['account'])
    peak=tracemalloc.get_traced_memory()[1];tracemalloc.stop()
    after=fingerprints(args.local,args.profile)
    if before!=after:raise RuntimeError('active stores changed during preview; repeat on a stable snapshot')
    counts=preview['summary']
    summary=dict(counts,remote_watched_movies=sum(r['identity']['kind']=='movie' and 'watched_at' in r for r in snapshot['records'].values()),
        remote_watched_episodes=sum(r['identity']['kind']=='episode' and 'watched_at' in r for r in snapshot['records'].values()),
        remote_playback=sum('paused_at' in r for r in snapshot['records'].values()),
        matched_movies=sum(i['identity']['kind']=='movie' for i in plan['items']),
        matched_episodes=sum(i['identity']['kind']=='episode' for i in plan['items']),
        ambiguous=len(plan['ambiguous']),
        metadata_pending=len(plan['unavailable']),confirmed_not_available=0,
        available_movie_provider_ids=len(catalog_members(catalog,args.profile,'movie')),
        available_series_provider_ids=len(catalog_members(catalog,args.profile,'series')),
        verified_movie_provider_ids=len(movies),verified_show_provider_ids=len(shows),
        provider_verified_movies=resolution['summary']['provider_verified_movies'],
        provider_verified_shows=resolution['summary']['provider_verified_shows'],
        xstream_matched_movies=resolution['summary']['xstream_matched_movies'],
        xstream_matched_shows=resolution['summary']['xstream_matched_shows'],
        xstream_cache_entries=resolution['summary']['xstream_cache_entries'],
        xstream_cache_pending=resolution['summary']['xstream_cache_pending'],
        xstream_cache_missing_provider_item=resolution['summary']['xstream_cache_missing_provider_item'],
        exact_episode_records=len(episodes['records']),availability_unknown=len(plan['unavailable']),
        candidate_trakt_items=resolution['summary']['candidate_trakt_items'],
        candidate_links=resolution['summary']['candidate_links'],
        candidate_ambiguous_items=sum(len(row['provider_ids']) > 1 for row in resolution['candidates']),
        identity_conflicts=len(resolution['conflicts']),
        pending_reasons=unresolved,unavailable_is_not_inferred_from_unmatched=True,
        samples=args.samples,performance=metrics,python_peak_bytes=peak,
        generation_check_p50_ms=round(statistics.median(stamps),3),
        active_stores_unchanged=True,remote_writes=0,kodi_state_writes=0)
    safe_write(output/'summary.json',summary)
    safe_write(output/'private-operations.json',preview)
    safe_write(output/'timing-samples.json',samples)
    safe_write(output/'store-fingerprints.json',before)
    print(json.dumps(summary,sort_keys=True))


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'status':'FAILED','error_type':type(error).__name__}))
        raise SystemExit(1)
