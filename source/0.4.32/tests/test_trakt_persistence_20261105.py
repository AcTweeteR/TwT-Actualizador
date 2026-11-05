"""Synthetic refresh and recommendations; no user credentials or Trakt writes."""
import ast
import sys
import types
import unittest
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
ADDON='plugin.video.xstream-pro'
BETA=ROOT/'docs/testing/repo'/ADDON/(ADDON+'-1.1.2.42~beta1.zip')

class TraktPersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with zipfile.ZipFile(BETA) as z:
            cls.trakt=z.read(ADDON+'/resources/lib/trakt.py').decode()
            cls.routes=z.read(ADDON+'/resources/lib/tmdb_routes.py').decode()
    def test_transient_refresh_rejection_preserves_tokens(self):
        tree=ast.parse(self.trakt)
        fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='refresh_token')
        code=compile(ast.Module(body=[fn],type_ignores=[]),'test_trakt_refresh','exec')
        for status in [400,401,403,429,500]:
            with self.subTest(status=status):
                calls=[]
                class Response:
                    status_code=status
                    def json(self): return {'access_token':'new','refresh_token':'new'}
                env={'_read_tokens':lambda: {'access_token':'old','refresh_token':'old'},
                     '_http_request':lambda *a,**kw:Response(), '_headers':lambda _: {},
                     'client_id':lambda:'public-app','_log':lambda *a:calls.append('log'),
                     'xbmc':types.SimpleNamespace(LOGWARNING=1),
                     '_write_tokens':lambda _:calls.append('write'),
                     'clear_tokens':lambda : calls.append('DELETE'),
                     '_raise_trakt_error':lambda *a:(_ for _ in ()).throw(RuntimeError('http error'))}
                exec(code,env)
                if status in (429,500):
                    with self.assertRaises(RuntimeError): env['refresh_token']()
                else: self.assertFalse(env['refresh_token']())
                self.assertNotIn('DELETE',calls)
                self.assertNotIn('write',calls)
    def test_success_stores_rotated_pair(self):
        fn=next(x for x in ast.parse(self.trakt).body if isinstance(x,ast.FunctionDef) and x.name=='refresh_token')
        code=compile(ast.Module(body=[fn],type_ignores=[]),'test_refresh','exec')
        writes=[]
        env={'_read_tokens':lambda:{'refresh_token':'old'},'_http_request':lambda *a,**kw:types.SimpleNamespace(status_code=200,json=lambda:{'access_token':'new','refresh_token':'new'}),
             '_headers':lambda _: {},'client_id':lambda:'public', '_write_tokens':writes.append,'_log':lambda *a:None,'xbmc':types.SimpleNamespace(LOGWARNING=1)}
        exec(code,env)
        self.assertTrue(env['refresh_token']())
        self.assertEqual(len(writes),1)
        self.assertEqual(writes[0]['access_token'],'new')
    def test_recommendations_empty_state_is_visible_without_unmatched_media(self):
        self.assertIn('Sin recomendaciones disponibles en tu catálogo',self.routes)
        self.assertIn('Recomendaciones temporalmente no disponibles',self.routes)
        self.assertIn('"mode": "xstream_tmdb_trakt_menu"',self.routes)
        self.assertIn('_filter_provider_trakt_recommendations(data.get("results", []))',self.routes)
        self.assertIn('"tmdb_type"',self.routes)

if __name__=='__main__':unittest.main()
