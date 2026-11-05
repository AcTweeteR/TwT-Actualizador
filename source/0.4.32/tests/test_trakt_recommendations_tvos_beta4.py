"""Regression: absent tvOS provider cache is rebuilt, never bypassed."""
import ast,types,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
AID='plugin.video.xstream-pro'
PACKAGE=ROOT/'docs/testing/repo'/AID/(AID+'-1.1.2.43~beta4.zip')
class TVOSRecommendationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  with zipfile.ZipFile(PACKAGE) as z:
   s=z.read(AID+'/resources/lib/addon.py').decode()
  node=next(n for n in ast.parse(s).body if isinstance(n,ast.FunctionDef) and n.name=='_filter_provider_trakt_recommendations')
  cls.code=compile(ast.Module(body=[node],type_ignores=[]),'provider_recommendations','exec')
 def run_case(self,cache,rebuilt,match=True):
  events=[]
  env={'_load_provider_availability_cache':lambda:cache,
       '_refresh_provider_availability_cache_after_profile_load':lambda **kw:(events.append(('rebuild',kw)),rebuilt)[1],
       '_provider_match_cached':lambda item,cache,strict_title_year:events.append(('match',strict_title_year)) or match,
       '_log':lambda msg:events.append(('log',msg))}
  exec(self.code,env)
  result=env['_filter_provider_trakt_recommendations']([{'tmdb_type':'movie','tmdb_id':123}])
  return result,events
 def test_missing_cache_recovers_verified_match(self):
  result,events=self.run_case(None,{'movie':{'titles':{'example':['2024']}}})
  self.assertEqual(len(result),1);self.assertIn(('rebuild',{'show_progress':False}),events)
  self.assertIn(('match',True),events)
 def test_unavailable_catalog_never_exposes_unmatched_media(self):
  result,events=self.run_case(None,None)
  self.assertEqual(result,[]);self.assertFalse(any(x[0]=='match' for x in events))
 def test_existing_cache_does_not_rebuild(self):
  result,events=self.run_case({'movie':{'titles':{'example':['2024']}}},None)
  self.assertEqual(len(result),1);self.assertFalse(any(x[0]=='rebuild' for x in events))
 def test_empty_index_recovers(self):
  result,events=self.run_case({'movie':{'titles':{}}},{'tv':{'titles':{'show':['2025']}}})
  self.assertEqual(len(result),1);self.assertTrue(any(x[0]=='rebuild' for x in events))
if __name__=='__main__':unittest.main()
