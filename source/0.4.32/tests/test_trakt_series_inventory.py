import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'addons/service.actweeter/resources'))
from lib.trakt_series_inventory import series_inventory

class SeriesInventoryTests(unittest.TestCase):
 def test_series_membership_does_not_invent_episode_identity(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory)
   (root/'data_cache_p1_xtream_streams_series.json').write_text(json.dumps({'_data':[{'series_id':77,'tmdb_id':250307}]}))
   (root/'data_cache_p1_premium_meta_series_77_es.json').write_text(json.dumps({'data':{'tmdb_id':250307}}))
   snapshot={'records':{'one':{'identity':{'kind':'episode','ids':{'tmdb':'250307'},'season':2,'episode':15}}}}
   result=series_inventory(root,profile=1,snapshot=snapshot)
   self.assertEqual(len(result['episode_candidates']),1)
   self.assertEqual(result['verified_episode_count'],0)
   self.assertFalse(result['episode_candidates'][0]['episode_id_verified'])

 def test_missing_provider_series_is_not_a_match(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory)
   (root/'data_cache_p1_xtream_streams_series.json').write_text(json.dumps({'_data':[]}))
   (root/'data_cache_p1_premium_meta_series_77_es.json').write_text(json.dumps({'data':{'tmdb_id':250307}}))
   snapshot={'records':{'one':{'identity':{'kind':'episode','ids':{'tmdb':'250307'},'season':2,'episode':15}}}}
   self.assertEqual(series_inventory(root,profile=1,snapshot=snapshot)['episode_candidates'],[])
