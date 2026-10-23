import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest

root=Path(__file__).resolve().parents[1]/'addons/service.actweeter/resources/lib'
pkg=types.ModuleType('trakt_series_index_testpkg');pkg.__path__=[str(root)];sys.modules[pkg.__name__]=pkg
for name in ('trakt_sync','trakt_series_index'):
 spec=importlib.util.spec_from_file_location(pkg.__name__+'.'+name,root/(name+'.py'))
 module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
index=sys.modules[pkg.__name__+'.trakt_series_index']

class SeriesIndexTests(unittest.TestCase):
 def test_only_verified_show_tmdb_from_correct_profile(self):
  with tempfile.TemporaryDirectory() as d:
   base=Path(d)
   (base/'data_cache_p1_xtream_streams_series.json').write_text(json.dumps({'_data':[{'series_id':77,'tmdb_id':250307},{'series_id':78}]}))
   (base/'data_cache_p1_premium_meta_series_77_es.json').write_text(json.dumps({'data':{'tmdb_id':250307,'title':'Example'}}))
   (base/'data_cache_p1_premium_meta_series_78_es.json').write_text(json.dumps({'data':{'title':'No ID'}}))
   (base/'data_cache_p2_premium_meta_series_79_es.json').write_text(json.dumps({'data':{'tmdb_id':250307}}))
   found=index.verified_show_records(base,profile=1)
   self.assertEqual(len(found),1)
   self.assertEqual(found[0]['ids']['tmdb'],'250307')
   self.assertEqual(found[0]['provider_id'],'77')

 def test_title_enrichment_alone_does_not_prove_provider_identity(self):
  with tempfile.TemporaryDirectory() as d:
   base=Path(d)
   (base/'data_cache_p1_xtream_streams_series.json').write_text(json.dumps({'_data':[{'series_id':77}]}))
   (base/'data_cache_p1_premium_meta_series_77_es.json').write_text(json.dumps({'data':{'tmdb_id':250307}}))
   self.assertEqual(index.verified_show_records(base,profile=1),[])

 def test_premium_lookup_does_not_add_external_identity_to_provider_show(self):
  with tempfile.TemporaryDirectory() as d:
   base=Path(d)
   (base/'data_cache_p1_xtream_streams_series.json').write_text(json.dumps({'_data':[
    {'series_id':77,'imdb_id':'tt1234567'}]}))
   (base/'data_cache_p1_premium_meta_series_77_es.json').write_text(json.dumps(
    {'data':{'tmdb_id':250307,'title':'Example'}}))
   found=index.verified_show_records(base,profile=1)
   self.assertEqual(found[0]['ids'],{'imdb':'tt1234567'})
