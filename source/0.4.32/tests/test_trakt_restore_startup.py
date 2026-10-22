import pathlib
import sys
import tempfile
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'addons/service.actweeter/resources'))
from lib.trakt_restore_startup import startup_restore_status

class StartupTests(unittest.TestCase):
 def test_clean_and_interrupted(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp)
   self.assertEqual(startup_restore_status(root)['reason'],'ready')
   folder=root/'trakt_restore_backups'/'attempt';folder.mkdir(parents=True)
   (folder/'transaction.pending').write_text('rollback-required')
   self.assertEqual(startup_restore_status(root),{'safe':False,'pending':1,'reason':'recovery_required'})
 def test_invalid_root_fails_closed(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);(root/'trakt_restore_backups').symlink_to(root)
   self.assertFalse(startup_restore_status(root)['safe'])
