import importlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
root=Path(__file__).resolve().parents[1]/'addons/service.actweeter/resources/lib'
sys.path.insert(0,str(root.parent))
Journal=importlib.import_module('lib.collection_journal').Journal
class JournalTests(unittest.TestCase):
 def test_explicit_checkpoint_and_reopen(self):
  with tempfile.TemporaryDirectory() as directory:
   path=os.path.join(directory,'journal.db');j=Journal(path)
   one=[{'kind':'movie','tmdb_id':42}]
   result=j.observe('a','tmdb','pending',one,complete=True,verified=True)
   self.assertFalse(result['committed']);self.assertIsNone(j.get('a','tmdb','pending'))
   j.observe('a','tmdb','pending',one,complete=True,verified=True,approved=True)
   result=Journal(path).observe('a','tmdb','pending',[],complete=True,verified=True)
   self.assertEqual(len(result['changes']['removed']),1)
   self.assertEqual(len(Journal(path).get('a','tmdb','pending')['items']),1)
   self.assertIsNone(j.get('other','tmdb','pending'))
 def test_fail_closed_on_incomplete_or_unverified(self):
  with tempfile.TemporaryDirectory() as directory:
   j=Journal(os.path.join(directory,'journal.db'))
   for complete,verified in [(False,True),(True,False)]:
    with self.assertRaises(ValueError):j.observe('a','trakt','favorites',[],complete=complete,verified=verified,approved=True)
   self.assertIsNone(j.get('a','trakt','favorites'))
 def test_no_symlink_database(self):
  with tempfile.TemporaryDirectory() as directory:
   p=os.path.join(directory,'db');link=os.path.join(directory,'link');open(p,'w').close();os.symlink(p,link)
   with self.assertRaises(ValueError):Journal(link)
