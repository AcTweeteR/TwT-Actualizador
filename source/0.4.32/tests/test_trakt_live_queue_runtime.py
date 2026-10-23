"""Exercise the durable hand-off against XStream's real history.py classes."""
import os
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = r'''
import importlib.util, json, subprocess, sys, tempfile, types
from pathlib import Path
service_lib = sys.argv[2]
sys.path.insert(0, service_lib)
sys.path.insert(0, str(Path(service_lib).parent))
from trakt_live_queue import build_batch, write_batch, checkpoint_from_ack
root = Path(tempfile.mkdtemp())
xbmc = types.ModuleType('xbmc'); xbmc.LOGWARNING=2; xbmc.log=lambda *a: None
xbmc.getCondVisibility=lambda *a: False; sys.modules['xbmc']=xbmc
xbmcaddon=types.ModuleType('xbmcaddon'); xbmcaddon.Addon=lambda *a: None; sys.modules['xbmcaddon']=xbmcaddon
vfs=types.ModuleType('xbmcvfs'); vfs.translatePath=lambda p: str(root); sys.modules['xbmcvfs']=vfs
sys.path.insert(0, sys.argv[1] + '/plugin.video.xstream-pro/resources/lib')
import history
from trakt_live_consumer import apply_batch
addon=types.SimpleNamespace(getAddonInfo=lambda k: str(root), getSetting=lambda key: 'Xtream Codes')
def cache(name, value):
    if 'xtream_streams_' in name: value=dict(value,_src='https://provider.invalid|user|secret')
    (root/name).write_text(json.dumps(value))
cache('data_cache_p2_xtream_streams_movie.json', {'_data':[{'stream_id':101},{'stream_id':303}]})
cache('data_cache_p2_vod_info_101.json', {'movie_data':{'stream_id':101},'info':{'tmdb_id':'500'}})
cache('data_cache_p2_vod_info_303.json', {'movie_data':{'stream_id':303},'info':{'tmdb_id':'900'}})
cache('data_cache_p2_xtream_streams_series.json', {'_data':[
    {'series_id':55,'tmdb_id':'600'},{'series_id':56,'tmdb_id':'901'}]})
cache('data_cache_p2_premium_meta_series_55_en.json', {'data':{'tmdb_id':'600'}})
cache('data_cache_p2_premium_meta_series_56_en.json', {'data':{'tmdb_id':'901'}})
cache('series_changes_p2.json', {'episode_inventory':{
    '55':{'complete':True,'episodes':[{'season':1,'episode':2,'provider_id':'202'}]},
    '56':{'complete':True,'episodes':[{'season':1,'episode':9,'provider_id':'304'}]}}})
url_movie='https://provider.invalid/movie/101.mp4'
url_episode='https://provider.invalid/series/202.mkv'
history.ResumePoints(addon, 2).save_position('Movie', url_movie, 90, 1800,
    {'stype':'movie'}, force=True, timestamp=1000)
history.WatchHistory(addon, 2).add('Movie', url_movie, '', 'movie')
history.WatchHistory(addon, 2).add('Episode', url_episode, '', 'series',
    {'series_id':'55','ep_id':'202','season_num':1,'episode_num':2})
profile_root=root/'service'; queue_root=profile_root/'trakt_live'/'queue'
from trakt_live_queue import provider_fingerprint
scope=provider_fingerprint('2','Xtream Codes','https://provider.invalid','user')
movie={'identity':{'kind':'movie','ids':{'tmdb':'500'}},'provider_id':'101',
       'watched':True,'watched_at':1100,'position':300,'duration':1800,'paused_at':1200}
episode={'identity':{'kind':'episode','ids':{'tmdb':'600'},'season':1,'episode':2},
         'provider_id':'202','provider_series_id':'55','provider_episode_id':'202',
         'watched':True,'watched_at':1101,'position':600,'duration':2400,'paused_at':1201}
batch=build_batch({'profile':'2','account':'test-account','items':[movie,episode]},
                  provider_scope=scope, consent=True, batch_id='1'*32)
path=write_batch(queue_root,batch)
collision=build_batch({'profile':'2','account':'test-account','items':[
    {'identity':{'kind':'movie','ids':{'tmdb':'999'}},'provider_id':'101',
     'watched':True,'watched_at':1090},
    {'identity':{'kind':'episode','ids':{'tmdb':'600'},'season':1,'episode':99},
     'provider_id':'202','provider_series_id':'55','provider_episode_id':'202',
     'watched':True,'watched_at':1091}]}, provider_scope=scope, consent=True,
    batch_id='3'*32)
collision_path=write_batch(queue_root,collision)
collision_ack=apply_batch(collision_path, profile_root/'trakt_live'/'acks', profile='2',
    account='test-account',provider_scope=scope,addon=addon,history=history,catalog_root=root)
assert all(row['status']=='deferred' for row in collision_ack['results'])
assert '101' not in history.WatchedMovies(addon,2)._data
try: checkpoint_from_ack(collision_ack,collision)
except RuntimeError: pass
else: raise AssertionError('provider ID collision was checkpointed')
ack=apply_batch(path, profile_root/'trakt_live'/'acks', profile='2',
    account='test-account',provider_scope=scope,addon=addon,history=history,catalog_root=root)
assert len(ack['results']) == 4
assert all(row['status']=='applied' for row in ack['results'])
checkpoint=checkpoint_from_ack(ack,batch)
assert checkpoint['profile']=='2'
assert '101' in history.WatchedMovies(addon,2)._data
assert '202' in history.WatchedEpisodes(addon,2)._data['55']['1']
assert history.ResumePoints(addon,2)._data['Movie||'+url_movie]['position']==300
assert history.ResumePoints(addon,2)._data['Episode||'+url_episode]['position']==600
# Replay the durable request: no extra writes, no duplicate episodes, stable ack.
replay=apply_batch(path, profile_root/'trakt_live'/'acks', profile='2',
    account='test-account',provider_scope=scope,addon=addon,history=history,catalog_root=root)
assert all(row['status'] in ('already_applied','superseded') for row in replay['results'])
assert len(history.WatchedEpisodes(addon,2)._data['55']['1'])==1
# A crash after the movie store commits but before episode persistence leaves
# no ack; retry merges the existing movie and finishes the remaining store.
partial=build_batch({'profile':'2','account':'test-account','items':[
    {'identity':{'kind':'movie','ids':{'tmdb':'900'}},'provider_id':'303',
     'watched':True,'watched_at':1300},
    {'identity':{'kind':'episode','ids':{'tmdb':'901'},'season':1,'episode':9},
     'provider_id':'304','provider_series_id':'56','provider_episode_id':'304',
     'watched':True,'watched_at':1301}]}, provider_scope=scope, consent=True,
    batch_id='2'*32)
partial_path=write_batch(queue_root,partial)
original_save=history.WatchedEpisodes._save
history.WatchedEpisodes._save=lambda self: (_ for _ in ()).throw(OSError('simulated interruption'))
try:
    try: apply_batch(partial_path, profile_root/'trakt_live'/'acks', profile='2',
        account='test-account',provider_scope=scope,addon=addon,history=history,catalog_root=root)
    except OSError: pass
    else: raise AssertionError('simulated store interruption was ignored')
finally:
    history.WatchedEpisodes._save=original_save
assert '2'*32+'.json' not in [p.name for p in (profile_root/'trakt_live'/'acks').glob('*.json')]
recovered=apply_batch(partial_path, profile_root/'trakt_live'/'acks', profile='2',
    account='test-account',provider_scope=scope,addon=addon,history=history,catalog_root=root)
assert all(row['status'] in ('applied','already_applied') for row in recovered['results'])
assert '303' in history.WatchedMovies(addon,2)._data
assert '304' in history.WatchedEpisodes(addon,2)._data['56']['1']
# Wrong account/profile/provider and malformed checksum fail closed.
for kwargs in ({'profile':'1','account':'test-account','provider_scope':scope},
               {'profile':'2','account':'other','provider_scope':scope},
               {'profile':'2','account':'test-account','provider_scope':'b'*64}):
    try: apply_batch(path, profile_root/'trakt_live'/'acks', **kwargs, addon=addon,
                     history=history,catalog_root=root)
    except (PermissionError, ValueError): pass
    else: raise AssertionError('scope mismatch was accepted')
bad=dict(batch); bad['operations']=[]
badpath=queue_root/('2'*32+'.json'); badpath.write_text(json.dumps(bad))
try: apply_batch(badpath, profile_root/'trakt_live'/'acks', profile='2',
    account='test-account',provider_scope=scope,addon=addon,history=history,catalog_root=root)
except ValueError: pass
else: raise AssertionError('bad checksum accepted')
# Playback-active defers all operations and cannot advance a checkpoint.
active=apply_batch(path, profile_root/'trakt_live'/'acks', profile='2',
    account='test-account',provider_scope=scope,addon=addon,history=history,catalog_root=root,
    playing_file=url_movie)
assert all(row['status']=='deferred' for row in active['results'])
try: checkpoint_from_ack(active,batch)
except RuntimeError: pass
else: raise AssertionError('deferred batch checkpointed')

# The actual XStream stores and consumer are exercised through the service's
# opt-in cycle: no remote network and no active Kodi profile are touched.
cache('data_cache_p2_xtream_streams_movie.json', {'_data':[{'stream_id':101},
    {'stream_id':303},{'stream_id':404}]})
cache('data_cache_p2_vod_info_404.json', {'movie_data':{'stream_id':404},
    'info':{'tmdb_id':'1000'}})
from trakt_sync_consent import grant
from lib.trakt_auto_cycle import run_cycle
cycle_service=root/'cycle-service'
consent_path=cycle_service/'trakt_live'/'consent.json'
grant(consent_path, account='test-account', profile='2', provider_scope=scope)
from trakt_snapshot import export_snapshot as make_export
exports=root/'synthetic-exports'
def fixture_get(path, query):
    if path == '/users/settings': return {'user':{'ids':{'slug':'test-account'}}}, 1
    if path == '/sync/last_activities': return {'all':'2026-10-22T12:00:00Z'}, 1
    rows = ([{'movie':{'ids':{'tmdb':1000}}, 'last_watched_at':'2026-10-22T12:00:00Z'}]
            if path == '/sync/watched/movies' else [])
    return rows, {'page':query['page'],'limit':100,'page_count':1,'item_count':len(rows)}
make_export(fixture_get, exports, '2')
export=next(exports.glob('snapshot-*'))
activity={'all':'2026-10-22T12:00:00Z'}; activity_calls=[]; export_calls=[]
def get_activity():
    activity_calls.append(1); return 'test-account', activity
def get_export():
    export_calls.append(1); return export
cycle_args=dict(account='test-account',profile='2',provider_scope=scope,
    activity_get=get_activity,export_snapshot=get_export,apply_batch=apply_batch,
    addon=addon,history=history,consent_path=consent_path)
queued=run_cycle(cycle_service,root,**cycle_args)
assert queued['status']=='queued' and queued['operations']==1
applied=run_cycle(cycle_service,root,**cycle_args)
assert applied['status']=='applied' and '404' in history.WatchedMovies(addon,2)._data
unchanged=run_cycle(cycle_service,root,**cycle_args)
assert unchanged['status']=='unchanged' and len(export_calls)==1
assert len(activity_calls)==2
assert not list((cycle_service/'trakt_live'/'queue').glob('*.json'))
import threading
lock_service=root/'locked-cycle-service'
lock_consent=lock_service/'trakt_live'/'consent.json'
grant(lock_consent, account='test-account', profile='2', provider_scope=scope)
entered=threading.Event(); release=threading.Event(); threaded_result=[]
def slow_activity():
    entered.set(); release.wait(2)
    return 'test-account', {'all':'2026-10-23T12:00:00Z'}
lock_args=dict(cycle_args,activity_get=slow_activity,consent_path=lock_consent)
thread=threading.Thread(target=lambda: threaded_result.append(
    run_cycle(lock_service,root,**lock_args)))
thread.start(); assert entered.wait(1)
assert run_cycle(lock_service,root,**lock_args)['status']=='busy'
release.set(); thread.join(3)
assert threaded_result and threaded_result[0]['status']=='queued'
# A lock owned by this process is live; a lock owned by a dead process is recoverable.
dead_service=root/'dead-lock-service'
dead_root=dead_service/'trakt_live'; dead_root.mkdir(mode=0o700,parents=True)
dead_process=subprocess.Popen([sys.executable,'-c','pass'])
dead_process.wait(timeout=5)
(dead_root/'cycle.lock').write_text(str(dead_process.pid))
dead_args=dict(cycle_args,consent_path=lock_consent)
dead_result=run_cycle(dead_service,root,**dead_args)
assert dead_result['status']=='queued', dead_result
# One confirmed sync uses the same consumer but never enables recurring sync.
once_service=root/'once-service'
once_args=dict(cycle_args,activity_get=lambda: ('test-account',
    {'all':'2026-10-24T12:00:00Z'}),one_shot=True)
once_queued=run_cycle(once_service,root,**once_args)
assert once_queued['status']=='queued', once_queued
once_applied=run_cycle(once_service,root,**once_args)
assert once_applied['status']=='applied', once_applied
once_state=once_service/'trakt_live'
assert not (once_state/'consent.json').exists()
assert not (once_state/'scheduler.json').exists()
assert json.loads((once_state/'remote'/'profile_2.json').read_text())['activity_fingerprint']
print('XStream live queue integration: PASS')
'''


class TraktLiveQueueRuntimeTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('ACTWEETER_XSTREAM_LIVE_ZIP'),
                         'set ACTWEETER_XSTREAM_LIVE_ZIP to the reproducible patched XStream ZIP')
    def test_queue_to_real_xstream_stores_and_durable_ack(self):
        with zipfile.ZipFile(os.environ['ACTWEETER_XSTREAM_LIVE_ZIP']) as archive:
            self.assertIsNone(archive.testzip())
            members = set(archive.namelist())
            self.assertIn('plugin.video.xstream-pro/resources/lib/trakt_auto_routes.py', members)
            self.assertIn('plugin.video.xstream-pro/resources/lib/trakt_pkce.py', members)
            self.assertIn(b'xstream_trakt_sync_cycle', archive.read(
                'plugin.video.xstream-pro/resources/lib/addon.py'))
            self.assertIn(b'trakt_sync_cycle_route', archive.read(
                'plugin.video.xstream-pro/resources/lib/tmdb_routes.py'))
            self.assertIn(b'xstream_trakt_sync_once', archive.read(
                'plugin.video.xstream-pro/resources/lib/addon.py'))
            self.assertIn(b'trakt_sync_once_route', archive.read(
                'plugin.video.xstream-pro/resources/lib/tmdb_routes.py'))
            self.assertIn(b'trakt_pkce.begin(', archive.read(
                'plugin.video.xstream-pro/resources/lib/tmdb_routes.py'))
        result = subprocess.run([sys.executable, '-c', SCRIPT,
            os.environ['ACTWEETER_XSTREAM_LIVE_ZIP'],
            str(ROOT / 'addons/service.actweeter/resources/lib')],
            text=True, capture_output=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS', result.stdout)

    def test_applied_live_sync_invalidates_continue_widgets_selectively(self):
        service_source = (ROOT / 'addons/service.actweeter/resources/lib/diagnostic_plugin.py').read_text()
        route_source = (ROOT / 'third_party/xstream/trakt_auto_routes.py').read_text()
        self.assertIn("params.get('action') == ['trakt_continue_refresh']", service_source)
        self.assertIn("invalidate_continue_widgets(xbmc, 'trakt_sync')", service_source)
        self.assertIn("action=trakt_continue_refresh", route_source)
        self.assertIn("XSTREAM_SYNC_ONCE", (ROOT /
            "addons/service.actweeter/resources/lib/trakt_restore_ui.py").read_text())


if __name__ == '__main__':
    unittest.main()
