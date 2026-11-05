"""Exact Trakt export evidence and fresh-device resume read-back (offline)."""
import hashlib,json,sys,tempfile,time,types,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'third_party/xstream'),str(ROOT/'addons/service.actweeter/resources/lib'),str(ROOT/'addons/service.actweeter/resources')]
import trakt_live_consumer as consumer
from trakt_live_queue import build_batch,write_batch,provider_fingerprint

class ExportConsumerTests(unittest.TestCase):
 def test_planner_premium_identity_is_accepted_by_consumer_only_with_valid_snapshot(self):
  from trakt_snapshot import export_snapshot
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);scope=provider_fingerprint('1','Xtream Codes','https://provider.invalid','user')
   for kind,rows in [('movie',[{'stream_id':'321','name':'Example','year':'2026','duration_secs':6000}]),('series',[])]:
    (root/f'data_cache_p1_xtream_streams_{kind}.json').write_text(json.dumps({'_src':'https://provider.invalid|user|pass','_data':rows}))
   (root/'data_cache_p1_premium_meta_movie_321_en.json').write_text(json.dumps({'expires':time.time()+3600,'data':{'title':'Example','tmdb_id':42}}))
   movie={'ids':{'tmdb':42},'title':'Example','year':2026}
   stamp='2026-11-05T12:00:00Z'; activity={'all':stamp}
   def get(path,query):
    if path=='/users/settings':return {'user':{'ids':{'slug':'synthetic'}}},1
    if path=='/sync/last_activities':return activity,1
    data=([{'movie':movie,'paused_at':stamp,'progress':30.0,'id':1}] if path=='/sync/playback/movies' else [])
    return data,{'page':query['page'],'limit':100,'page_count':1,'item_count':len(data)}
   archive=root/'trakt_exports';archive.mkdir(mode=0o700)
   export_snapshot(get,archive,'1')
   folder=next(archive.glob('snapshot-*'))
   item=dict(identity={'kind':'movie','ids':{'tmdb':'42'},'key':'movie:tmdb:42'},provider_id='321',position=1800,duration=6000,paused_at=stamp)
   digest=hashlib.sha256(json.dumps(activity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
   batch=build_batch({'profile':'1','account':'synthetic','items':[item]},provider_scope=scope,consent=True,source_export=str(folder.relative_to(root)),activity_fingerprint=digest)
   self.assertFalse(consumer._catalog_identity_exact(batch['operations'][0],consumer._verified_catalog_index(batch['operations'],root,'1')))
   index=consumer._verified_catalog_index(batch['operations'],root,'1',batch=batch,account='synthetic')
   self.assertTrue(consumer._catalog_identity_exact(batch['operations'][0],index))
   self.assertFalse(consumer._catalog_identity_exact(batch['operations'][0],consumer._verified_catalog_index(batch['operations'],root,'1',batch=batch,account='wrong')))
   (folder/'manifest.json').write_text('{}')
   self.assertFalse(consumer._catalog_identity_exact(batch['operations'][0],consumer._verified_catalog_index(batch['operations'],root,'1',batch=batch,account='synthetic')))

 def test_fresh_device_new_resume_reference_survives_readback_without_prior_playback(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp)
   op=dict(identity={'kind':'movie','ids':{'tmdb':'42'},'key':'movie:tmdb:42'},provider_id='321',position=200,duration=1000,paused_at='2026-11-05T12:00:00Z')
   batch=build_batch({'profile':'1','account':'synthetic','items':[op]},provider_scope='a'*64,consent=True)
   path=write_batch(root/'queue',batch)
   class Watched:
    def __init__(self,*args,**kwargs):self._data={}
    def _save(self):raise AssertionError('watched must remain unchanged')
   class Resume:
    def __init__(self,*args,**kwargs):
     self._path=root/'resume.json'
     self._data=json.loads(self._path.read_text()) if self._path.exists() else {}
    @staticmethod
    def _key(name,url):return name+'||'+url
    def get_all(self):return list(self._data.values())
    def _save(self):self._path.write_text(json.dumps(self._data))
   class History:
    def __init__(self,*args,**kwargs):pass
    def get_all(self):return []
   module=types.SimpleNamespace(WatchedMovies=Watched,WatchedEpisodes=Watched,
                                ResumePoints=Resume,WatchHistory=History)
   record={'name':'Example','url':'https://provider.invalid/movie/user/pass/321.mp4','stype':'movie','title':'Example'}
   with patch.object(consumer,'_catalog_scope_verified',return_value=True),\
        patch.object(consumer,'_verified_catalog_index',return_value=object()),\
        patch.object(consumer,'_catalog_identity_exact',return_value=True),\
        patch.object(consumer,'_verified_remote_reference',return_value=record):
    ack=consumer.apply_batch(path,root/'acks',profile='1',account='synthetic',provider_scope='a'*64,
                             addon=object(),history=module,catalog_root=root)
   self.assertEqual(ack['results'][0]['status'],'applied')
   self.assertEqual(len(Resume().get_all()),1)
   self.assertEqual(Resume().get_all()[0]['position'],200.0)
if __name__=='__main__':unittest.main()
