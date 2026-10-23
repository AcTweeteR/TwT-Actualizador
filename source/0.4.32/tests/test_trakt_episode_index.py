import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'addons/service.actweeter/resources'))
from lib.trakt_episode_index import verified_episode_records

class EpisodeIndexTests(unittest.TestCase):
 def test_exact_episode_requires_complete_inventory(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory)
   (root/'data_cache_p1_xtream_streams_series.json').write_text(json.dumps({'_data':[{'series_id':77}]}))
   (root/'data_cache_p1_premium_meta_series_77_es.json').write_text(json.dumps({'data':{'tmdb_id':250307}}))
   inventory={'episode_inventory':{'77':{'complete':True,'episodes':[{'season':2,'episode':15,'provider_id':'555'}]}}}
   (root/'series_changes_p1.json').write_text(json.dumps(inventory))
   snapshot={'records':{'x':{'identity':{'kind':'episode','ids':{'tmdb':'250307'},'season':2,'episode':15}}}}
   result=verified_episode_records(root,profile=1,snapshot=snapshot)
   self.assertEqual(len(result['records']),1)
   self.assertEqual(result['records'][0]['provider_episode_id'],'555')
   inventory['episode_inventory']['77']['complete']=False
   (root/'series_changes_p1.json').write_text(json.dumps(inventory))
   self.assertEqual(verified_episode_records(root,profile=1,snapshot=snapshot)['records'],[])
