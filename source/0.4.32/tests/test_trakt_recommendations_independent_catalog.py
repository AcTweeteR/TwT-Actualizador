"""The Trakt provider intersection must not depend on TMDb-only browsing mode."""
import ast,os,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
AID='plugin.video.xstream-pro'
SOURCE=ROOT/'docs/testing/repo'/AID/(AID+'-1.1.2.44~beta5.zip')

class RecommendationsIndependentCatalog(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  path=Path(os.environ.get('ACTWEETER_XSTREAM_LIVE_ZIP',SOURCE))
  with zipfile.ZipFile(path) as z:code=z.read(AID+'/resources/lib/addon.py').decode()
  func=next(node for node in ast.parse(code).body if isinstance(node,ast.FunctionDef) and node.name=='_filter_provider_trakt_recommendations')
  cls.compiled=compile(ast.Module(body=[func],type_ignores=[]),'recommendations','exec')

 def run_case(self,cache=None,rebuild=None,match=True,fail=False):
  events=[]
  def rebuild_fn(**kw):
   events.append(('rebuild',kw))
   if fail:raise IOError('no provider network')
   return rebuild
  env={'_load_provider_availability_cache':lambda:cache,
       '_rebuild_provider_availability_cache':rebuild_fn,
       '_refresh_provider_availability_cache_after_profile_load':lambda **kw:(_ for _ in ()).throw(AssertionError('incorrectly depends on TMDb-only flag')),
       '_provider_match_cached':lambda item,index,strict_title_year:events.append(('match',strict_title_year)) or match,
       '_log':lambda message:events.append(('log',message))}
  exec(self.compiled,env)
  source=[{'tmdb_type':'movie','tmdb_id':'123','title':'Example','year':'2026'}]
  return env['_filter_provider_trakt_recommendations'](source),events

 def test_missing_cache_rebuilds_even_with_provider_only_mode_disabled(self):
  result,events=self.run_case(rebuild={'movie':{'titles':{'example':['2026']}}})
  self.assertEqual(len(result),1)
  self.assertIn(('rebuild',{'show_progress':False}),events)
  self.assertIn(('match',True),events)

 def test_existing_index_never_rebuilds(self):
  result,events=self.run_case(cache={'movie':{'titles':{'example':['2026']}}})
  self.assertEqual(len(result),1)
  self.assertFalse(any(kind=='rebuild' for kind,*_ in events))

 def test_failed_rebuild_does_not_invent_provider_content(self):
  result,events=self.run_case(fail=True)
  self.assertEqual(result,[])
  self.assertFalse(any(kind=='match' for kind,*_ in events))

 def test_verified_catalog_still_rejects_unmatched_titles(self):
  result,events=self.run_case(rebuild={'movie':{'titles':{'example':['2026']}}},match=False)
  self.assertEqual(result,[])
  self.assertIn(('match',True),events)

 def test_empty_index_rebuilds(self):
  result,events=self.run_case(cache={'movie':{'titles':{}}},rebuild={'movie':{'titles':{'example':['2026']}}})
  self.assertEqual(len(result),1)
  self.assertIn(('rebuild',{'show_progress':False}),events)

if __name__=='__main__':unittest.main()
