import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'addons/service.actweeter/resources'))
from lib.trakt_restore_importer import prepare_restore

class RestoreImporterTests(unittest.TestCase):
 def test_rejects_account_mismatch_before_import(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);export=root/'export';export.mkdir()
   raw=json.dumps({'schema_version':1,'profile':'1','snapshot':{
    'account':'correct','complete':True,'records':{},'history':[]}}).encode()
   (export/'snapshot.json').write_bytes(raw)
   import hashlib
   (export/'manifest.json').write_text(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'status':'READ_ONLY_EXPORT_VERIFIED'}))
   with self.assertRaises(PermissionError):
    prepare_restore(export,root,profile='1',account='wrong')

 def test_rejects_snapshot_without_complete_fence(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);export=root/'export';export.mkdir()
   raw=json.dumps({'schema_version':1,'profile':'1','snapshot':{
    'account':'correct','complete':False,'records':{},'history':[]}}).encode()
   (export/'snapshot.json').write_bytes(raw)
   import hashlib
   (export/'manifest.json').write_text(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),
    'status':'READ_ONLY_EXPORT_VERIFIED'}))
   with self.assertRaisesRegex(ValueError,'complete supported snapshot'):
    prepare_restore(export,root,profile='1',account='correct')
