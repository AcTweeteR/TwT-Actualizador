import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'addons/service.actweeter/resources'))
from lib.trakt_restore_commit import (commit_staged_restore, recover_interrupted_restore,
    rollback_committed_restore)

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

 def test_second_replace_failure_rolls_back_first(self):
  from unittest.mock import patch
  import os
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);files=[root/x for x in ('new_m','new_e','old_m','old_e')]
   for i,p in enumerate(files):p.write_text(json.dumps({'value':i}))
   real_replace=os.replace
   def fail_second(src,dst):
    if str(dst)==str(files[3]) and str(src).endswith('.tmp'):
     raise OSError('simulated failure after first replacement')
    return real_replace(src,dst)
   with patch('lib.trakt_restore_commit.os.replace',side_effect=fail_second):
    with self.assertRaises(OSError):
     commit_staged_restore(staged_movie=files[0],staged_episode=files[1],active_movie=files[2],active_episode=files[3],backup_directory=root/'backup',kodi_stopped=True)
   self.assertEqual(json.loads(files[2].read_text()),{'value':2})
   self.assertEqual(json.loads(files[3].read_text()),{'value':3})
   self.assertFalse((root/'backup/transaction.pending').exists())

 def test_symlink_backup_refused(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);files=[root/x for x in ('new_m','new_e','old_m','old_e')]
   for p in files:p.write_text('{}')
   (root/'backup').symlink_to(root, target_is_directory=True)
   with self.assertRaises(FileExistsError):
    commit_staged_restore(staged_movie=files[0],staged_episode=files[1],active_movie=files[2],active_episode=files[3],backup_directory=root/'backup',kodi_stopped=True)

 def test_three_store_restore_and_rollback_preserves_absent_resume_store(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory)
   staged=[root/name for name in ('new_m','new_e','new_r')]
   active=[root/name for name in ('old_m','old_e','resume')]
   for i,path in enumerate(staged):path.write_text(json.dumps({'new':i}))
   active[0].write_text('{"old":"movie"}');active[1].write_text('{"old":"episode"}')
   backup=root/'backup'
   commit_staged_restore(staged_movie=staged[0],staged_episode=staged[1],staged_resume=staged[2],
      active_movie=active[0],active_episode=active[1],active_resume=active[2],
      backup_directory=backup,kodi_stopped=True)
   self.assertEqual(json.loads(active[2].read_text()),{'new':2})
   rollback_committed_restore(backup_directory=backup,active_movie=active[0],
      active_episode=active[1],active_resume=active[2],kodi_stopped=True)
   self.assertEqual(active[0].read_text(),'{"old":"movie"}')
   self.assertEqual(active[1].read_text(),'{"old":"episode"}')
   self.assertFalse(active[2].exists())

 def test_rollback_refuses_a_store_changed_after_commit(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);files=[root/x for x in ('new_m','new_e','old_m','old_e')]
   for i,path in enumerate(files):path.write_text(json.dumps({'value':i}))
   backup=root/'backup'
   commit_staged_restore(staged_movie=files[0],staged_episode=files[1],
      active_movie=files[2],active_episode=files[3],backup_directory=backup,kodi_stopped=True)
   files[2].write_text('{"later":"local change"}')
   with self.assertRaises(RuntimeError):
    rollback_committed_restore(backup_directory=backup,active_movie=files[2],
       active_episode=files[3],kodi_stopped=True)
   self.assertEqual(json.loads(files[2].read_text()),{'later':'local change'})
