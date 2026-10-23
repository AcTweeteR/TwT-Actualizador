"""Exercise the durable hand-off against XStream's real history.py classes."""
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = r'''
import importlib.util, json, sys, tempfile, types
from pathlib import Path
service_lib = sys.argv[2]
sys.path.insert(0, service_lib)
from trakt_live_queue import build_batch, write_batch, checkpoint_from_ack
root = Path(tempfile.mkdtemp())
xbmc = types.ModuleType('xbmc'); xbmc.LOGWARNING=2; xbmc.log=lambda *a: None
xbmc.getCondVisibility=lambda *a: False; sys.modules['xbmc']=xbmc
xbmcaddon=types.ModuleType('xbmcaddon'); xbmcaddon.Addon=lambda *a: None; sys.modules['xbmcaddon']=xbmcaddon
vfs=types.ModuleType('xbmcvfs'); vfs.translatePath=lambda p: str(root); sys.modules['xbmcvfs']=vfs
sys.path.insert(0, sys.argv[1] + '/plugin.video.xstream-pro/resources/lib')
import history
from trakt_live_consumer import apply_batch
addon=types.SimpleNamespace(getAddonInfo=lambda k: str(root))
def cache(name, value):
    (root/name).write_text(json.dumps(value))
cache('data_cache_p2_xtream_streams_movie.json', {'_data':[{'stream_id':101},{'stream_id':303}]})
cache('data_cache_p2_vod_info_101.json', {'movie_data':{'stream_id':101},'info':{'tmdb_id':'500'}})
cache('data_cache_p2_vod_info_303.json', {'movie_data':{'stream_id':303},'info':{'tmdb_id':'900'}})
cache('data_cache_p2_xtream_streams_series.json', {'_data':[{'series_id':55},{'series_id':56}]})
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
scope='a'*64
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
print('XStream live queue integration: PASS')
'''


class TraktLiveQueueRuntimeTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('ACTWEETER_XSTREAM_LIVE_ZIP'),
                         'set ACTWEETER_XSTREAM_LIVE_ZIP to the reproducible patched XStream ZIP')
    def test_queue_to_real_xstream_stores_and_durable_ack(self):
        result = subprocess.run([sys.executable, '-c', SCRIPT,
            os.environ['ACTWEETER_XSTREAM_LIVE_ZIP'],
            str(ROOT / 'addons/service.actweeter/resources/lib')],
            text=True, capture_output=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS', result.stdout)


if __name__ == '__main__':
    unittest.main()
