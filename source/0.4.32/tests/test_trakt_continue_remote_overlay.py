"""Remote-only Trakt playback is visible while native ResumePoints remain authoritative."""
import ast
import os
import sys
import types
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
AID='plugin.video.xstream-pro'
DEFAULT=ROOT/'docs/testing/repo'/AID/(AID+'-1.1.2.44~beta4.zip')

class FakeListItem:
    def __init__(self):self.props={}
    def setProperty(self,key,value):self.props[key]=value

class RemoteContinueOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        file=Path(os.environ.get('ACTWEETER_XSTREAM_LIVE_ZIP',DEFAULT))
        with zipfile.ZipFile(file) as archive:
            source=archive.read(AID+'/resources/lib/premium_routes.py').decode()
            trakt=archive.read(AID+'/resources/lib/trakt.py').decode()
        cls.helper=next(node for node in ast.parse(source).body
            if isinstance(node,ast.FunctionDef) and node.name=='_trakt_continue_extra')
        cls.code=compile(ast.Module(body=[cls.helper],type_ignores=[]),'remote_continue','exec')
        cls.premium_source=source
        cls.trakt_source=trakt

    def run_overlay(self,stype='movie',seen=None,limit=19,remote=None,authorized=True,fail=False):
        calls=[]
        if remote is None:
            remote={'movies':{'results':[
                {'tmdb_type':'movie','tmdb_id':str(i),'title':'Movie %d'%i,
                 'raw':{'progress':float(i),'movie':{'ids':{'tmdb':i}}}}
                for i in range(1,7)]},'episodes':{'results':[]}}
        fake_trakt=types.ModuleType('trakt')
        fake_trakt.authorized=lambda:authorized
        def playback(kind,cached=False):
            calls.append(('GET',kind,cached))
            if fail:raise OSError('synthetic outage')
            return remote[kind]
        fake_trakt.playback=playback
        fake_routes=types.SimpleNamespace(
            _hydrate_from_tmdb_meta_cache=lambda items:items,
            _media_item=lambda item:('plugin://provider/mode=source/'+str(item['tmdb_id']),FakeListItem(),True))
        g={'_setup_tmdb_routes':lambda:True,'_tmdb_routes':fake_routes,'_log':lambda x:calls.append(('log',x)), '_cache_load':lambda key:{}, 'xbmcvfs':types.SimpleNamespace(translatePath=lambda x:'/tmp/nonexistent-actweeter-profile'), 'addon':types.SimpleNamespace(getAddonInfo=lambda key:'/tmp/nonexistent-actweeter-profile'), 'pm':types.SimpleNamespace(active='1')}
        with patch.dict(sys.modules,{'trakt':fake_trakt}):
            scope={};exec(self.code,scope)
            result=scope['_trakt_continue_extra'](g,stype,set(seen or ()),limit)
        return result,calls

    def test_fresh_tablet_with_two_local_rows_shows_all_six_remote_progress_cards(self):
        rows,calls=self.run_overlay('movie',limit=17)
        self.assertEqual(len(rows),6)
        self.assertEqual([row[0].rsplit('/',1)[-1] for row in rows],list(map(str,range(1,7))))
        self.assertTrue(all(row[1].props.get('XStream.RemoteOnly')=='true' for row in rows))
        self.assertTrue(all(row[2] for row in rows))
        self.assertEqual(calls,[('GET','movies',True)])

    def test_known_local_tmdb_id_is_not_duplicated(self):
        rows,_=self.run_overlay('movie',seen={('movie','1','',''),('movie','3','','')})
        self.assertEqual(len(rows),4)

    def test_no_remote_episodes_does_not_make_up_series(self):
        rows,calls=self.run_overlay('series')
        self.assertEqual(rows,[])
        self.assertEqual(calls,[('GET','episodes',True)])

    def test_offline_or_unauthed_never_alters_resume_store(self):
        rows,calls=self.run_overlay('both',fail=True)
        self.assertEqual(rows,[])
        self.assertEqual(calls[0],('GET','movies',True))
        self.assertEqual(calls[1][0],'log')
        rows,calls=self.run_overlay('both',authorized=False)
        self.assertEqual((rows,calls),([],[]))

    def test_overlay_is_read_only_and_preserves_provider_seek_authority(self):
        func=ast.get_source_segment(self.premium_source,self.helper)
        self.assertIn("_media_item(item)",func)
        self.assertIn("data_cache_p%s_premium_meta_movie_*_es.json",func)
        self.assertIn("XStream.ProviderMatched",func)
        self.assertIn("meta_summary_cached",func)
        self.assertIn("_hydrate_from_tmdb_meta_cache",func)
        self.assertNotIn('save_position(',func)
        self.assertNotIn('setResumePoint(',func)
        self.assertIn("if view == 'continue' and page == 1:",self.premium_source)
        self.assertIn('def playback(media_kind="movies", page=1, cached=False):',self.trakt_source)
        self.assertIn('ttl=180, timeout=2',self.trakt_source)

if __name__=='__main__':unittest.main()
