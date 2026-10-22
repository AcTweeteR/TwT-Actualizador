import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'addons/service.actweeter/resources'))
from lib.trakt_restore_commit import commit_staged_restore, recover_interrupted_restore

class CommitTests(unittest.TestCase):
 def test_requires_stopped_kodi_and_backs_up_both(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);files=[root/x for x in ('new_m','new_e','old_m','old_e')]
   for i,p in enumerate(files):p.write_text(json.dumps({'value':i}))
   kwargs=dict(staged_movie=files[0],staged_episode=files[1],active_movie=files[2],active_episode=files[3],backup_directory=root/'backup')
   with self.assertRaises(PermissionError):commit_staged_restore(**kwargs,kodi_stopped=False)
   self.assertFalse((root/'backup').exists())
   result=commit_staged_restore(**kwargs,kodi_stopped=True)
   self.assertTrue(result['committed'])
   self.assertEqual(json.loads(files[2].read_text()),{'value':0})
   self.assertEqual(json.loads(files[3].read_text()),{'value':1})
   self.assertEqual(json.loads((root/'backup/original_0.json').read_text()),{'value':2})

 def test_interrupted_transaction_restores_both_originals(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);backup=root/'backup';backup.mkdir()
   a=root/'movies';b=root/'episodes'
   a.write_text('{"changed":1}');b.write_text('{"changed":2}')
   (backup/'original_0.json').write_text('{"original":1}')
   (backup/'original_1.json').write_text('{"original":2}')
   (backup/'transaction.pending').write_text('rollback-required')
   with self.assertRaises(PermissionError):
    recover_interrupted_restore(backup_directory=backup,active_movie=a,active_episode=b,kodi_stopped=False)
   self.assertTrue(recover_interrupted_restore(backup_directory=backup,active_movie=a,active_episode=b,kodi_stopped=True))
   self.assertEqual(json.loads(a.read_text()),{'original':1})
   self.assertEqual(json.loads(b.read_text()),{'original':2})
   self.assertFalse((backup/'transaction.pending').exists())
