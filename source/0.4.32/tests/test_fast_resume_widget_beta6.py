"""Verify Beta6 exact provider-index read and untouched dynamic resume states."""
import ast,os,sys,types,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3]
ADDON='plugin.video.xstream-pro'
BETA=ROOT/'docs/testing/repo'/ADDON/(ADDON+'-1.1.2.44~beta6.zip')
class IndexedContinueTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  package=BETA  # Immutable Beta6 regression; Beta7 has its own dedicated tests.
  with zipfile.ZipFile(package) as archive:
   source=archive.read(ADDON+'/resources/lib/premium_routes.py').decode()
  node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='_indexed_continue_movies')
  cls.code=compile(ast.Module(body=[node],type_ignores=[]),'_indexed_continue_movies','exec')
  cls.source=source
 def g(self,rows):
  calls=[]
  class Index:
   def __init__(self,path,source,profile,stype,trace=None):
    calls.append(('index',stype))
   def page(self,provider_id,**kwargs):
    calls.append(('lookup',provider_id,kwargs))
    return rows.get(provider_id,[]),False
  env={'re':__import__('re'),'urlparse':__import__('urllib.parse',fromlist=['urlparse']).urlparse,
       'CatalogIndex':Index}
  addon=types.ModuleType('provider_catalog_index');addon.CatalogIndex=Index
  env['g']={
    '_get_credentials_for_profile':lambda p:{'xtream_url':'server','xtream_username':'user','xtream_password':'secret'},
    '_cache_path':lambda key,profile_num:'/tmp/indexed-provider-movie.json',
    '_get_cached_xtream_categories':lambda *a,**k:[],
    '_get_hidden_subcats':lambda *a:set(),
    '_is_adult_category':lambda x:False,
    '_get_hidden_items':lambda *a:set(),
    '_log':lambda x:calls.append(('log',x)),
  }
  exec(self.code,env)
  return env,addon,calls
 def test_exact_movie_id_uses_index_and_skips_full_catalog(self):
  env,stub,calls=self.g({'992':[{'stream_id':992,'name':'Example'}]})
  with patch.dict(sys.modules,{'provider_catalog_index':stub}):
   result=env['_indexed_continue_movies'](env['g'],1,[{'stype':'movie','url':'https://provider/movie/u/p/992.mp4'}])
  self.assertEqual(result[0][0]['stream_id'],992)
  self.assertIn(('index','movie'),calls)
  self.assertTrue(any(row[0]=='lookup' and row[1]=='992' for row in calls))
 def test_missing_stream_id_never_uses_fuzzy_index(self):
  env,stub,calls=self.g({})
  with patch.dict(sys.modules,{'provider_catalog_index':stub}):
   result=env['_indexed_continue_movies'](env['g'],1,[{'stype':'movie','url':'plugin://legacy','name':'Example'}])
  self.assertIsNone(result)
  self.assertFalse(any(row[0]=='index' for row in calls))
 def test_ambiguous_provider_identity_fails_closed(self):
  env,stub,calls=self.g({'99':[{'stream_id':99},{'stream_id':99}]})
  with patch.dict(sys.modules,{'provider_catalog_index':stub}):
   result=env['_indexed_continue_movies'](env['g'],1,[{'stype':'movie','url':'https://provider/99.mp4'}])
  self.assertIsNone(result)
 def test_dynamic_state_remains_unpersisted(self):
  self.assertIn("g['ResumePoints'](g['addon'], profile_num=pnum).get_all()",self.source)
  self.assertIn("tag.setResumePoint(float(entry.get('position')",self.source)
  self.assertIn("_indexed_continue_movies(g, pnum, entries)",self.source)
  self.assertIn("catalog(g, kind, pnum)",self.source)
  self.assertIn("plugin.endOfDirectory, handle, cacheToDisc=False",self.source)
if __name__=='__main__':unittest.main()
