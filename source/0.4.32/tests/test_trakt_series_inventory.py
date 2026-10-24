import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'third_party/xstream'))
import catalog_cache

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

 def test_service_reads_one_committed_generation_instead_of_legacy_files(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory)
   source='https://provider|user|secret'
   (root/'data_cache_p1_xtream_streams_series.json').write_text(json.dumps({'_src':source,'_data':[{'series_id':55}]}))
   values={
    'xtream_streams_movie':[],
    'xtream_cats_movie':[],
    'xtream_streams_series':[{'series_id':77,'tmdb_id':250307}],
    'xtream_cats_series':[{'category_id':'s'}],
   }
   old_values=dict(values)
   old_values['xtream_streams_series']=[{'series_id':66,'tmdb_id':250307}]
   catalog_cache.refresh(root,1,source,{key:(lambda key=key:old_values[key]) for key in catalog_cache.KEYS},force=True)
   catalog_cache.refresh(root,1,source,{key:(lambda key=key:values[key]) for key in catalog_cache.KEYS},force=True)
   (root/'data_cache_p1_premium_meta_series_77_es.json').write_text(json.dumps({'data':{'tmdb_id':250307}}))
   (root/'data_cache_p1_series_info_66.json').write_text(json.dumps({'info':{'tmdb_id':250307}}))
   snapshot={'records':{'one':{'identity':{'kind':'episode','ids':{'tmdb':'250307'},'season':2,'episode':15}}}}
   result=series_inventory(root,profile=1,snapshot=snapshot)
   self.assertEqual(result['provider_series_count'],1)
   self.assertEqual(result['episode_candidates'][0]['provider_series_id'],'77')

 def test_service_rejects_generation_when_any_component_is_corrupt(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory)
   source='https://provider|user|secret'
   old={'xtream_streams_movie':[], 'xtream_cats_movie':[],
        'xtream_streams_series':[{'series_id':66,'tmdb_id':250307}],
        'xtream_cats_series':[{'category_id':'s'}]}
   new=dict(old); new['xtream_streams_series']=[{'series_id':77,'tmdb_id':250307}]
   for values in (old,new):
    catalog_cache.refresh(root,1,source,
        {key:(lambda key=key, values=values:values[key]) for key in catalog_cache.KEYS},force=True)
   active=Path(catalog_cache.cache_path(root,1,source,'xtream_streams_movie'))
   active.write_text('corrupt')
   (root/'data_cache_p1_series_info_66.json').write_text(json.dumps({'info':{'tmdb_id':250307}}))
   snapshot={'records':{'one':{'identity':{'kind':'episode','ids':{'tmdb':'250307'},'season':2,'episode':15}}}}
   result=series_inventory(root,profile=1,snapshot=snapshot)
   self.assertEqual(result['episode_candidates'][0]['provider_series_id'],'66')
