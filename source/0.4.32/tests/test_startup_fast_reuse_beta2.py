"""Repeat Home activations do not relaunch verified interface setup."""
import ast,os,types,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
AID='service.actweeter';BETA=ROOT/'docs/testing/repo'/AID/(AID+'-0.4.101~beta2.zip')
class StartupFastReuseTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  with zipfile.ZipFile(Path(os.environ.get('ACTWEETER_SERVICE_LIVE_ZIP',BETA))) as z:
   source=z.read(AID+'/setup.py').decode()
  cls.tree=ast.parse(source)
  cls.source=source
 def test_fast_reuse_requires_verified_version(self):
  main=next(n for n in self.tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
  text=ast.unparse(main)
  self.assertIn('AcTweeteR.InterfaceReady',text)
  self.assertIn('AcTweeteR.ReadySkinVersion',text)
  self.assertIn("xbmcaddon.Addon('skin.actweeter').getAddonInfo('version')",text)
  self.assertIn('if not resume',text)
 def test_success_and_current_migration_set_same_skin_version(self):
  helper=next(n for n in self.tree.body if isinstance(n,ast.FunctionDef) and n.name=='_run_pending_interface_migration')
  text=ast.unparse(helper)
  self.assertEqual(text.count("window.setProperty('AcTweeteR.ReadySkinVersion', active_skin_version)"),2)
  self.assertIn('if not interface_preparation_needed(migration_due, generated_ready)',text)
  self.assertIn("if result != 'GENERATED'",text)
 def test_repair_and_pending_setup_paths_preserved(self):
  source=self.source
  self.assertIn("if action == 'repair_interface'",source)
  self.assertIn("_run_pending_interface_migration(dialog, explicit=True)",source)
  self.assertIn('claim_process_session(_first_run_session_path(), os.getpid())',source)
  self.assertIn('_run_pending_interface_migration(dialog)',source)
  self.assertIn('should_offer_first_run_in_process',source)
  self.assertIn('FIRST_RUN_FLOW status=fast_reused',source)
if __name__=='__main__':unittest.main()
