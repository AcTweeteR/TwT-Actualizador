import importlib.util
from pathlib import Path
import unittest
p=Path(__file__).resolve().parents[1]/'addons/service.actweeter/resources/lib/tmdb_account_transport.py'
s=importlib.util.spec_from_file_location('tmdb_account_transport_test_impl',p)
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class TMDbTransportTests(unittest.TestCase):
 def test_device_auth_flow(self):
  calls=[]
  def req(method,url,payload):
   calls.append((method,url,payload))
   if '/token/new' in url:return {'success':True,'request_token':'abc'}
   if '/session/new' in url:return {'success':True,'session_id':'session'}
   return {'id':7}
  client=m.TMDbAccount('a'*32,req)
  self.assertEqual(client.request_token()['authorize_url'],m.AUTH_PAGE+'abc')
  self.assertEqual(client.create_session('abc'),'session')
  self.assertEqual(client.account('session')['id'],7)
  self.assertNotIn('session_id=',calls[0][1])
 def test_write_requires_approval_and_confirmed_response(self):
  calls=[]
  def req(method,url,payload):calls.append(payload);return {'success':False}
  client=m.TMDbAccount('b'*32,req)
  with self.assertRaises(PermissionError):client.change_watchlist('s',2,'movie',3,add=True,approved=False)
  self.assertEqual(calls,[])
  with self.assertRaises(ValueError):client.change_watchlist('s',2,'movie',3,add=True,approved=True)
  self.assertEqual(calls,[{'media_type':'movie','media_id':3,'watchlist':True}])
 def test_invalid_page_rejected(self):
  client=m.TMDbAccount('c'*32,lambda *args:{'page':1,'total_pages':2,'results':[]})
  with self.assertRaises(ValueError):client.watchlist_page('s',1,'movies',2)
 def test_pagination_is_in_url(self):
  calls=[]
  def req(method,url,payload):
   calls.append((url,payload));return {'page':2,'total_pages':2,'results':[]}
  client=m.TMDbAccount('d'*32,req)
  client.watchlist_page('s',1,'movies',2)
  self.assertIn('page=2',calls[0][0]);self.assertIsNone(calls[0][1])
