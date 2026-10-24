import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'addons/service.actweeter/resources'))
from lib.trakt_restore_transaction import stage_complete_restore, stage_restore

class TransactionTests(unittest.TestCase):
 def test_stages_both_stores_and_preserves_originals(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);src=root/'active';src.mkdir();stage=root/'stage';stage.mkdir()
   m=src/'movies.json';e=src/'episodes.json';m.write_text('{"existing":true}');e.write_text('{}')
   plan={'profile':'1','account':'a','items':[
    {'identity':{'kind':'movie'},'provider_id':'12','watched':True},
    {'identity':{'kind':'episode','season':2},'provider_id':'55','provider_series_id':'77','provider_episode_id':'55','watched':True}]}
   result=stage_restore(plan,profile='1',account='a',movie_source=m,episode_source=e,staging_directory=stage)
   self.assertEqual((result['movies'],result['episodes']),(1,1))
   self.assertEqual(json.loads(m.read_text()),{'existing':True})
   self.assertEqual(json.loads(e.read_text()),{})
   self.assertTrue(json.loads((stage/'watched_movies.json').read_text())['12'])
   self.assertEqual(json.loads((stage/'watched_episodes.json').read_text())['77']['2'],['55'])

 def test_missing_profile_stores_are_staged_as_empty_without_creating_sources(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);src=root/'active';src.mkdir();stage=root/'stage';stage.mkdir()
   movie=src/'watched_movies_p2.json';episode=src/'watched_episodes_p2.json'
   plan={'profile':'2','account':'a','items':[]}
   result=stage_restore(plan,profile='2',account='a',movie_source=movie,
      episode_source=episode,staging_directory=stage)
   self.assertEqual(json.loads(Path(result['movie_path']).read_text()),{})
   self.assertEqual(json.loads(Path(result['episode_path']).read_text()),{})
   self.assertFalse(movie.exists());self.assertFalse(episode.exists())

 def test_complete_restore_stages_resume_without_changing_profile_files(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);stage=root/'stage';stage.mkdir()
   movie=root/'watched_movies_p2.json';episode=root/'watched_episodes_p2.json'
   resume=root/'resume_points_p2.json';history=root/'watch_history_p2.json'
   movie.write_text('{}');episode.write_text('{}')
   key='Movie||https://provider.invalid/movie/101.mp4'
   resume.write_text(json.dumps({key:{'name':'Movie','url':'https://provider.invalid/movie/101.mp4',
      'stype':'movie','position':100,'duration':1800,'timestamp':1792670399}}))
   history.write_text('[]')
   plan={'profile':'2','account':'acct','items':[{'identity':{'kind':'movie','ids':{'tmdb':'10'}},
      'provider_id':'101','watched':True,'position':300,'duration':1800,
      'paused_at':'2026-10-22T12:00:00Z'}]}
   before={path:path.read_bytes() for path in (movie,episode,resume,history)}
   result=stage_complete_restore(plan,profile='2',account='acct',xstream_profile=root,
      movie_source=movie,episode_source=episode,staging_directory=stage)
   self.assertFalse(result['resume_error'])
   self.assertEqual((result['movies'],result['resumes_updated']),(1,1))
   staged=json.loads(Path(result['resume_path']).read_text())
   self.assertEqual(staged[key]['position'],300)
   self.assertEqual({path:path.read_bytes() for path in before},before)
