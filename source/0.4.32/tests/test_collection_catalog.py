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
   db=m.Catalog(os.path.join(folder,'lists.db'));i=db.create_local('Sci Fi',origin='mis_colecciones')
   self.assertEqual(db.plan_creation(i,connected={'trakt':True,'tmdb':True},automatic_creation=False),[])
   self.assertEqual([x['service'] for x in db.plan_creation(i,connected={'trakt':True,'tmdb':False},automatic_creation=True)],['trakt'])
   self.assertEqual(len(db.plan_creation(i,connected={'trakt':True,'tmdb':True},automatic_creation=True)),2)
 def test_verified_mapping_prevents_duplicate_creation_and_rename_survives(self):
  with tempfile.TemporaryDirectory() as folder:
   db=m.Catalog(os.path.join(folder,'lists.db'));i=db.create_local('Sci Fi',origin='mis_colecciones')
   with self.assertRaises(ValueError):db.confirm_remote(i,'trakt','list-1',account='a',verified=False)
   db.confirm_remote(i,'trakt','list-1',account='a',verified=True)
   db.rename_local(i,'Science Fiction')
   self.assertEqual(db.get(i)['name'],'Science Fiction')
   self.assertEqual([x['service'] for x in db.plan_creation(i,connected={'trakt':True,'tmdb':True},automatic_creation=True)],['tmdb'])
   with self.assertRaises(ValueError):db.confirm_remote(i,'trakt','different',account='a',verified=True)
 def test_other_folders_cannot_sync(self):
  with tempfile.TemporaryDirectory() as folder:
   db=m.Catalog(os.path.join(folder,'lists.db'))
   with self.assertRaises(PermissionError):db.create_local('External',origin='xstream_favorites')
   with self.assertRaises(PermissionError):db.create_local('Unscoped')
 def test_members_are_local_persistent_and_deduplicated(self):
  with tempfile.TemporaryDirectory() as folder:
   path=os.path.join(folder,'lists.db');db=m.Catalog(path)
   i=db.create_local('Movies',kind='movie',origin='mis_colecciones')
   db.add_member(i,kind='movie',tmdb_id=603,title='The Matrix')
   db.add_member(i,kind='movie',tmdb_id=603,title='The Matrix')
   self.assertEqual(len(m.Catalog(path).members(i)),1)
   with self.assertRaises(ValueError):db.add_member(i,kind='show',tmdb_id=42,title='Wrong')
   with self.assertRaises(ValueError):db.add_member(i,kind='movie',tmdb_id=0,title='Wrong')
   db.remove_member(i,kind='movie',tmdb_id=603)
   self.assertEqual(db.members(i),[])
 def test_same_title_distinct_ids(self):
  with tempfile.TemporaryDirectory() as folder:
   db=m.Catalog(os.path.join(folder,'lists.db'))
   self.assertNotEqual(db.create_local('Favorites',origin='mis_colecciones'),db.create_local('Favorites',origin='mis_colecciones'))
