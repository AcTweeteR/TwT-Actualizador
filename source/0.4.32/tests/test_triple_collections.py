import importlib.util
from pathlib import Path
import unittest
p=Path(__file__).resolve().parents[1]/'addons/service.actweeter/resources/lib/triple_collections.py'
spec=importlib.util.spec_from_file_location('test_triple_collections_impl',p)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class TripleCollectionsTests(unittest.TestCase):
 def snap(self,source,collection,items,account='account-a'):
  return module.snapshot(source,collection,items,account=account)
 def test_bootstrap_union_and_no_deletion(self):
  a={'kind':'movie','tmdb_id':'100'};b={'kind':'show','tmdb_id':'100'}
  snapshots=[self.snap('kodi','pending',[a]),self.snap('trakt','pending',[b]),self.snap('tmdb','pending',[])]
  plan=module.bootstrap(snapshots,account='account-a',collection='pending')
  self.assertEqual(plan['count'],2)
  self.assertEqual(len(plan['additions']['kodi']),1)
  self.assertEqual(len(plan['additions']['tmdb']),2)
  self.assertTrue(all(not x for x in plan['removals'].values()))
 def test_missing_source_and_foreign_account_rejected(self):
  snapshots=[self.snap('kodi','favorites',[]),self.snap('trakt','favorites',[])]
  with self.assertRaises(ValueError):module.bootstrap(snapshots,account='account-a',collection='favorites')
  with self.assertRaises(ValueError):module.bootstrap(snapshots+[self.snap('tmdb','favorites',[],'other')],account='account-a',collection='favorites')
 def test_incomplete_never_becomes_mass_deletion(self):
  before=self.snap('tmdb','favorites',[{'kind':'movie','tmdb_id':1}])
  with self.assertRaises(ValueError):module.snapshot('tmdb','favorites',[],account='account-a',complete=False)
  current=self.snap('tmdb','favorites',[])
  self.assertEqual(len(module.delta(before,current,source='tmdb')['removed']),1)
  with self.assertRaises(ValueError):module.delta(dict(before,complete=False),current,source='tmdb')
 def test_no_unverified_titles_or_channels(self):
  for row in ({'kind':'movie','title':'Similar'}, {'kind':'live','tmdb_id':'9'}, {'kind':'movie','tmdb_id':'-1'}):
   with self.assertRaises(ValueError):self.snap('kodi','pending',[row])
 def test_favorites_does_not_mutate_pending(self):
  items=[{'kind':'movie','tmdb_id':12}]
  states=[self.snap(s,'favorites',items if s=='trakt' else []) for s in module.SOURCES]
  plan=module.bootstrap(states,account='account-a',collection='favorites')
  self.assertEqual(plan['collection'],'favorites')
  with self.assertRaises(ValueError):module.bootstrap(states,account='account-a',collection='pending')
