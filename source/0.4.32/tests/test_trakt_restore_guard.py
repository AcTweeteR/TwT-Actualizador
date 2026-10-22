import pathlib
import sys
import tempfile
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'addons/service.actweeter/resources'))
from lib.trakt_restore_guard import pending_restores, assert_restore_ready

class RestoreGuardTests(unittest.TestCase):
 def test_empty_and_pending(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp)
   self.assertTrue(assert_restore_ready(root))
   folder=root/'trakt_restore_backups'/'attempt-1';folder.mkdir(parents=True)
   (folder/'transaction.pending').write_text('rollback-required')
   self.assertEqual(pending_restores(root),[folder])
   with self.assertRaises(RuntimeError):assert_restore_ready(root)
 def test_rejects_symlink(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);(root/'trakt_restore_backups').symlink_to(root)
   with self.assertRaises(ValueError):pending_restores(root)
