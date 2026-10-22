import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
p=Path(__file__).resolve().parents[1]/'addons/service.actweeter/resources/lib/collection_catalog.py'
s=importlib.util.spec_from_file_location('collection_catalog_test_impl',p)
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class CatalogTests(unittest.TestCase):
 def test_auto_creation_needs_consent_and_verified_connection(self):
  with tempfile.TemporaryDirectory() as folder:
   db=m.Catalog(os.path.join(folder,'lists.db'));i=db.create_local('Sci Fi')
   self.assertEqual(db.plan_creation(i,connected={'trakt':True,'tmdb':True},automatic_creation=False),[])
   self.assertEqual([x['service'] for x in db.plan_creation(i,connected={'trakt':True,'tmdb':False},automatic_creation=True)],['trakt'])
   self.assertEqual(len(db.plan_creation(i,connected={'trakt':True,'tmdb':True},automatic_creation=True)),2)
 def test_verified_mapping_prevents_duplicate_creation_and_rename_survives(self):
  with tempfile.TemporaryDirectory() as folder:
   db=m.Catalog(os.path.join(folder,'lists.db'));i=db.create_local('Sci Fi')
   with self.assertRaises(ValueError):db.confirm_remote(i,'trakt','list-1',account='a',verified=False)
   db.confirm_remote(i,'trakt','list-1',account='a',verified=True)
   db.rename_local(i,'Science Fiction')
   self.assertEqual(db.get(i)['name'],'Science Fiction')
   self.assertEqual([x['service'] for x in db.plan_creation(i,connected={'trakt':True,'tmdb':True},automatic_creation=True)],['tmdb'])
   with self.assertRaises(ValueError):db.confirm_remote(i,'trakt','different',account='a',verified=True)
 def test_same_title_distinct_ids(self):
  with tempfile.TemporaryDirectory() as folder:
   db=m.Catalog(os.path.join(folder,'lists.db'))
   self.assertNotEqual(db.create_local('Favorites'),db.create_local('Favorites'))
