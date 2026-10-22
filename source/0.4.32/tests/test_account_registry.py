import importlib.util
from pathlib import Path
import unittest
p=Path(__file__).resolve().parents[1]/'addons/service.actweeter/resources/lib/account_registry.py'
spec=importlib.util.spec_from_file_location('account_registry_impl',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class AccountRegistryTests(unittest.TestCase):
 def test_trakt_and_tmdb_are_independent(self):
  rows=m.accounts_view({'trakt':{'status':'connected'},'tmdb':{'status':'needs_authorization'}})
  self.assertEqual([r['status'] for r in rows],['connected','needs_authorization'])
  self.assertEqual(rows[0]['scrobbler'],'script.trakt')
  self.assertIsNone(rows[1]['scrobbler'])
  self.assertNotIn('token',str(rows))
 def test_extension_cannot_embed_credentials(self):
  self.assertEqual(m.validate_extension('future_service',{'name':'Future','features':['pending']})['status'],'not_connected')
  with self.assertRaises(ValueError):m.validate_extension('future_service',{'name':'Future','features':[],'token':'secret'})
