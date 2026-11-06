"""Exact provider lookup never loads full catalogue in warm Trakt overlay."""
import ast,os,sys,types,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3]
AID='plugin.video.xstream-pro'
PACKAGE=ROOT/'docs/testing/repo'/AID/(AID+'-1.1.2.44~beta8.zip')
class TraktOverlayIndexTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  # The exact Beta8 fast-index contract is intentionally absent from the
  # Stable XStream branch; test its retained Beta8 artifact on Stable CI.
  current = (os.environ.get('ACTWEETER_XSTREAM_LIVE_ZIP', str(PACKAGE))
             if os.environ.get('ACTWEETER_RELEASE_CHANNEL') != 'stable' else str(PACKAGE))
  with zipfile.ZipFile(Path(current)) as z:
   src=z.read(AID+'/resources/lib/premium_routes.py').decode()
  funcs=[n for n in ast.parse(src).body if isinstance(n,ast.FunctionDef)
         and n.name in ('_indexed_remote_movie_ids','_trakt_continue_extra')]
  cls.code=compile(ast.Module(body=funcs,type_ignores=[]),'premium','exec')
  cls.source=src
 def fake_context(self,rows=None):
  log=[];rows=rows or {}
  class Index:
   def __init__(self,*args,**kwargs):log.append('index')
   def page(self,provider_id,**kw):log.append(('get',provider_id));return rows.get(provider_id,[]),False
  idx=types.ModuleType('provider_catalog_index');idx.CatalogIndex=Index
  g={'_get_credentials_for_profile':lambda *a:{'xtream_url':'host','xtream_username':'user','xtream_password':'fake'},
     '_cache_path':lambda *a,**kw:'/tmp/provider.json',
     '_get_cached_xtream_categories':lambda *a,**kw:[],
     '_get_hidden_subcats':lambda *a:set(),
     '_is_adult_category':lambda *a:False,
     '_get_hidden_items':lambda *a:set(),
     '_log':lambda x:log.append('log'),
     '_cache_load':lambda key:(_ for _ in ()).throw(AssertionError('bulk provider catalogue must not load'))}
  return idx,g,log
 def test_exact_id_index_without_full_catalog(self):
  idx,g,log=self.fake_context({'123':[{'stream_id':123,'name':'Movie'}]})
  scope={};exec(self.code,scope)
  with patch.dict(sys.modules,{'provider_catalog_index':idx}):
   result=scope['_indexed_remote_movie_ids'](g,'1',['123'])
  self.assertEqual(result['123']['name'],'Movie')
  self.assertEqual(log,['index',('get','123')])
 def test_missing_index_falls_back_without_mutation(self):
  idx,g,log=self.fake_context()
  class Broken:
   def __init__(self,*args,**kwargs):raise FileNotFoundError()
  idx.CatalogIndex=Broken
  scope={};exec(self.code,scope)
  with patch.dict(sys.modules,{'provider_catalog_index':idx}):
   self.assertIsNone(scope['_indexed_remote_movie_ids'](g,'1',['123']))
  self.assertIn('log',log)
 def test_no_remote_entries_skip_movie_profile_cache(self):
  fake=types.ModuleType('trakt');fake.authorized=lambda:True;fake.playback=lambda kind,cached=False:{'results':[]}
  idx,g,log=self.fake_context()
  g.update(_setup_tmdb_routes=lambda:True,
           _tmdb_routes=types.SimpleNamespace(_hydrate_from_tmdb_meta_cache=lambda v:v),
           pm=types.SimpleNamespace(active='1'))
  scope={};exec(self.code,scope)
  with patch.dict(sys.modules,{'trakt':fake,'provider_catalog_index':idx}):
   rows=scope['_trakt_continue_extra'](g,'series',set(),19)
  self.assertEqual(rows,[])
  self.assertEqual(log,[])
 def test_dynamic_resume_and_provider_identity_preserved(self):
  self.assertIn('tag.setResumePoint(',self.source)
  self.assertIn('XStream.ProviderMatched',self.source)
  self.assertIn('_indexed_remote_movie_ids(g, pnum, sorted(requested))',self.source)
  self.assertIn("if not pending:",self.source)
if __name__=='__main__':unittest.main()
