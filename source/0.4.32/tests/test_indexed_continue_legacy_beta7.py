"""Preserve legacy resume matching without full provider catalogue reads."""
import ast,os,sys,types,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3]
AID='plugin.video.xstream-pro'
PACKAGE=ROOT/'docs/testing/repo'/AID/(AID+'-1.1.2.44~beta7.zip')
class IndexedContinueLegacy(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  with zipfile.ZipFile(Path(os.environ.get('ACTWEETER_XSTREAM_LIVE_ZIP',PACKAGE))) as z:
   source=z.read(AID+'/resources/lib/premium_routes.py').decode()
  node=next(node for node in ast.parse(source).body if isinstance(node,ast.FunctionDef) and node.name=='_indexed_continue_movies')
  cls.compiled=compile(ast.Module(body=[node],type_ignores=[]),'continue','exec')
 def evaluate(self, entries, hits=None, search=None):
  calls=[]
  hits=hits or {};search=search or []
  class Index:
   def __init__(self,*args,**kwargs):pass
   def page(self,provider_id,**kwargs):
    calls.append(('id',provider_id));return hits.get(provider_id,[]),False
   def search(self,title,**kwargs):
    calls.append(('search',title));return search
  module=types.ModuleType('provider_catalog_index');module.CatalogIndex=Index
  env={'re':__import__('re'), 'urlparse':__import__('urllib.parse',fromlist=['urlparse']).urlparse,
       'provider_id':lambda item,stype:str(item['stream_id'])}
  exec(self.compiled,env)
  g={'_get_credentials_for_profile':lambda p:{'xtream_url':'server','xtream_username':'user','xtream_password':'not-a-real-password'},
     '_cache_path':lambda *a,**kw:'/unused/active-catalog.json',
     '_get_cached_xtream_categories':lambda *a,**kw:[],
     '_get_hidden_subcats':lambda *a:set(),
     '_is_adult_category':lambda v:False,
     '_get_hidden_items':lambda *a:set(),
     '_log':lambda msg:None}
  with patch.dict(sys.modules,{'provider_catalog_index':module}):
   return env['_indexed_continue_movies'](g,1,entries),calls
 def test_one_legacy_entry_does_not_force_bulk_load(self):
  rows=[{'stype':'movie','url':'https://provider/movie/321.mkv','name':'Uno (2026)'},
        {'stype':'movie','url':'plugin://legacy','name':'Dos (2026)'}]
  result,calls=self.evaluate(rows,hits={'321':[{'stream_id':321,'name':'Uno (2026)'}]},
                            search=[{'stream_id':322,'name':'Dos (2026)'}])
  self.assertEqual([item['stream_id'] for item in result[0]],[321,322])
  self.assertIn(('search','Dos (2026)'),calls)
 def test_ambiguous_legacy_item_falls_back(self):
  result,_=self.evaluate([{'stype':'movie','url':'plugin://legacy','name':'Dos (2026)'}],
                         search=[{'stream_id':1,'name':'Dos (2026)'},{'stream_id':2,'name':'Dos (2026)'}])
  self.assertIsNone(result)
 def test_unmatched_legacy_item_falls_back(self):
  result,_=self.evaluate([{'stype':'movie','url':'plugin://legacy','name':'Dos (2026)'}],search=[])
  self.assertIsNone(result)
 def test_duplicate_exact_ids_dedupe_and_do_not_mutate_entries(self):
  rows=[{'stype':'movie','url':'https://provider/321.mp4'}, {'stype':'movie','url':'https://provider/321.mp4'}]
  original=[dict(x) for x in rows]
  result,_=self.evaluate(rows,hits={'321':[{'stream_id':321,'name':'Uno'}]})
  self.assertEqual(len(result[0]),1)
  self.assertEqual(rows,original)
if __name__=='__main__':unittest.main()
