import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'addons/service.actweeter/resources'))
from lib.trakt_restore_transaction import stage_restore

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
