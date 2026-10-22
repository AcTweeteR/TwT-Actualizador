import pathlib
import sys
import tempfile
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'addons/service.actweeter/resources'))
from lib.trakt_restore_bootcheck import inspect_all_profiles

class BootCheckTests(unittest.TestCase):
 def test_logs_pending_and_never_writes(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);folder=root/'trakt_restore_backups'/'tx';folder.mkdir(parents=True)
   marker=folder/'transaction.pending';marker.write_text('rollback-required')
   logs=[];status=inspect_all_profiles(root,logs.append)
   self.assertFalse(status['safe']);self.assertEqual(marker.read_text(),'rollback-required')
   self.assertEqual(len(logs),1)
