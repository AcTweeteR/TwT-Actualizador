"""Bidirectional Trakt updates with synthetic identities, never real accounts."""
import json
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'third_party/xstream'))
sys.path.insert(0,str(ROOT/'addons/service.actweeter/resources'))
import trakt_local_journal as journal
from lib.trakt_outbox import Outbox,manual_event

SCOPE=dict(account='synthetic',profile='1',provider_scope='a'*64,kodi_profile='b'*64,generation='c'*64)
MOVIE=dict(kind='movie',ids={'tmdb':'42'})
EPISODE=dict(kind='episode',ids={'tmdb':'99'},season=1,episode=2)

class TestBidirectionalTrakt(unittest.TestCase):
 def test_reconcile_held_watched_with_distinct_id_sets(self):
  from lib.trakt_watched_reconcile import remote_watched_status
  record=dict(identity=dict(kind='movie',ids={'tmdb':'42','imdb':'tt0000042'}),
              watched_at='2026-11-05T12:00:00Z')
  remote=dict(account='synthetic',complete=True,records={'movie:tmdb:42':record})
  self.assertEqual(remote_watched_status(remote,MOVIE,account='synthetic'),'watched')
  self.assertEqual(remote_watched_status(remote,dict(kind='movie',ids={'imdb':'tt0000042'}),account='synthetic'),'watched')
  self.assertEqual(remote_watched_status(remote,dict(kind='movie',ids={'tmdb':'41'}),account='synthetic'),'missing')
  self.assertEqual(remote_watched_status(remote,dict(kind='movie',ids={'tmdb':'42','imdb':'tt0000043'}),account='synthetic'),'conflict')

 def test_pause_event_is_bounded_exact_and_contains_no_provider_url(self):
  for kind in (MOVIE,EPISODE):
   event=manual_event('synthetic','1','playback.pause',kind,'e'*32,provider_scope='a'*64,progress=22.123456)
   self.assertEqual(event['endpoint'],'/scrobble/pause')
   self.assertAlmostEqual(event['payload']['progress'],22.12346)
   self.assertNotIn('url',str(event).lower())
   self.assertIn('movie' if kind is MOVIE else 'episode',event['payload'])
  for invalid in (-1,0,93,100,'42',True,float('nan')):
   with self.subTest(invalid=invalid),self.assertRaises(ValueError):
    manual_event('synthetic','1','playback.pause',MOVIE,'f'*32,provider_scope='a'*64,progress=invalid)
  with self.assertRaises(ValueError):
   manual_event('synthetic','1','history.add',MOVIE,'f'*32,'2026-11-05T11:00:00Z',provider_scope='a'*64,progress=30)

 def test_pause_outbox_sends_only_consent_pending_and_receipt_confirms(self):
  with tempfile.TemporaryDirectory() as temp:
   q=Outbox(Path(temp)/'outbox.db')
   event=manual_event('synthetic','1','playback.pause',MOVIE,'e'*32,provider_scope='a'*64,progress=22.5)
   q.enqueue_manual(event,held=True)
   self.assertEqual(q.pending_manual(account='synthetic',profile='1',provider_scope='a'*64,now=100,include_held=False),[])
   self.assertEqual(q.pending_manual(account='synthetic',profile='1',provider_scope='a'*64,now=100,include_held=True),[event['id']])
   calls=[]
   def post(path,payload):
    calls.append((path,payload));return dict(action='pause',progress=22.5)
   result=q.send_manual(event['id'],account='synthetic',profile='1',provider_scope='a'*64,approved=event['id'],post=post,now=101)
   self.assertEqual(result,'confirmed')
   self.assertEqual(len(calls),1)
   self.assertEqual(q.pending_manual(account='synthetic',profile='1',provider_scope='a'*64,now=200,include_held=True),[])
   with self.assertRaises(PermissionError):
    q.send_manual(event['id'],account='other',profile='1',provider_scope='a'*64,approved=event['id'],post=post,now=101)

 def test_unknown_pause_post_not_automatically_replayed(self):
  with tempfile.TemporaryDirectory() as temp:
   q=Outbox(Path(temp)/'outbox.db');event=manual_event('synthetic','1','playback.pause',MOVIE,'e'*32,provider_scope='a'*64,progress=44)
   q.enqueue_manual(event,held=True)
   q.send_manual(event['id'],account='synthetic',profile='1',provider_scope='a'*64,approved=event['id'],post=lambda *a:(_ for _ in ()).throw(OSError('unknown result')),now=1)
   self.assertEqual(q.status(event['id'])['state'],'unknown')
   self.assertEqual(q.pending_manual(account='synthetic',profile='1',provider_scope='a'*64,now=9999,include_held=True),[])

 def test_watched_provider_id_capture_creates_held_event(self):
  fake=types.SimpleNamespace(verified_vod_records=lambda *a,**kw:[dict(provider_id='321',ids={'tmdb':'42'})])
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp); store=root/'watched_movies_p1.json';q=Outbox(root/'outbox.db')
   with patch.dict(sys.modules,{'trakt_provider_index':fake}),patch.object(journal,'_catalog_binding_valid',return_value=True),journal.verified_scope(**SCOPE):
    journal.finish(journal.prepare(store,'WatchedMovies',{}, {'321':True}))
   self.assertEqual(journal.deliver(store,q,scope=SCOPE),1)
   with q.connect() as db: raw,state=db.execute('select event,state from events').fetchone()
   event=json.loads(raw)
   self.assertEqual(event['operation'],'history.add')
   self.assertEqual(event['identity']['ids']['tmdb'],'42')
   self.assertEqual(state,'held')
   self.assertEqual(len(q.pending_manual(account='synthetic',profile='1',provider_scope='a'*64,now=100,include_held=True)),1)

 def test_resume_capture_proves_movie_external_id_without_persisting_url(self):
  fake=types.SimpleNamespace(verified_vod_records=lambda *a,**kw:[dict(provider_id='321',ids={'tmdb':'42'})])
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);store=root/'resume_points_p1.json';q=Outbox(root/'outbox.db')
   url='https://example.invalid/movie/secret-name/secret-password/321.mp4'; key='Title||'+url
   row=dict(stype='movie',name='Title',url=url,position=300,duration=1000,timestamp=1000)
   with patch.dict(sys.modules,{'trakt_provider_index':fake}),patch.object(journal,'_catalog_binding_valid',return_value=True),journal.verified_scope(**SCOPE):
    journal.finish(journal.prepare(store,'ResumePoints',{}, {key:row}))
   self.assertEqual(journal.deliver(store,q,scope=SCOPE),1)
   with q.connect() as db: raw,state=db.execute('select event,state from events').fetchone()
   event=json.loads(raw)
   self.assertEqual(event['operation'],'playback.pause');self.assertEqual(state,'held')
   self.assertEqual(event['progress'],30)
   self.assertNotIn('secret-password',str(event))
   with sqlite3.connect(root/'trakt_local_changes.sqlite') as db:
    self.assertNotIn('secret-password',db.execute('SELECT event FROM changes').fetchone()[0])

 def test_no_exact_id_retains_capture_without_remote_mutation(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);store=root/'resume_points_p1.json';q=Outbox(root/'outbox.db')
   entry={'title||https://example.invalid/movie/user/pass/321.mp4':dict(stype='movie',name='title',url='https://example.invalid/movie/user/pass/321.mp4',position=400,duration=1000,timestamp=100)}
   with patch.object(journal,'_catalog_binding_valid',return_value=False),journal.verified_scope(**SCOPE):
    journal.finish(journal.prepare(store,'ResumePoints',{},entry))
   journal.deliver(store,q,scope=SCOPE)
   with q.connect() as db:states=db.execute('select state from events').fetchall()
   self.assertEqual(states,[('retained',)])

 def test_first_device_resume_url_requires_matching_source_and_duration(self):
  import xml.etree.ElementTree as ET
  from lib.trakt_resume_bridge import existing_playback_references
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder)
   (root/'settings.xml').write_text('<settings><setting id="profile_1_source_type">Xtream Codes</setting><setting id="profile_1_xtream_url">https://example.invalid</setting><setting id="profile_1_xtream_username">user</setting><setting id="profile_1_xtream_password">pass</setting></settings>')
   payload={'_src':'https://example.invalid|user|pass','_data':[{'stream_id':321,'name':'A', 'container_extension':'mp4'}]}
   (root/'data_cache_p1_xtream_streams_movie.json').write_text(json.dumps(payload))
   item=dict(provider_id='321',identity=dict(kind='movie',ids={'tmdb':'42'}),position=400,duration=1000,paused_at='2026-11-05T12:00:00Z')
   refs,_=existing_playback_references(root,'1',[item])
   self.assertIn('movie:321',refs)
   self.assertEqual(refs['movie:321']['url'],'https://example.invalid/movie/user/pass/321.mp4')
   (root/'settings.xml').write_text((root/'settings.xml').read_text().replace('>pass<','>other<'))
   refs,_=existing_playback_references(root,'1',[item])
   self.assertEqual(refs,{})

if __name__=='__main__':unittest.main()
