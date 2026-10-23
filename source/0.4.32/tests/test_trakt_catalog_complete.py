import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile
import os

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'addons/service.actweeter/resources'))
from lib.trakt_provider_index import catalog_members, verified_vod_records
from lib.trakt_series_index import verified_show_records
from lib.trakt_episode_index import verified_episode_records
from lib.trakt_restore_importer import preview_changes
from lib.trakt_auto_cycle import catalog_generation, run_cycle
from lib import trakt_auto_cycle
from test_trakt_sync import sync, LATE, EARLY


class CompleteCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, value):
        path = self.root / name; path.write_text(json.dumps(value)); return path

    def movies(self, rows):
        return self.write('data_cache_p1_xtream_streams_movie.json', {'_src': 'synthetic|user|secret', '_data': rows})

    def series(self, rows):
        return self.write('data_cache_p1_xtream_streams_series.json', {'_src': 'synthetic|user|secret', '_data': rows})

    def test_full_catalog_ids_and_category_duplicates_are_not_materialized_history(self):
        self.movies([{'stream_id': 9, 'tmdb_id': 42, 'category_id': 1},
                     {'stream_id': 9, 'tmdb_id': 42, 'category_id': 2},
                     {'stream_id': 10, 'imdb_id': 'tt0010'}])
        rows = verified_vod_records(self.root, profile='1')
        self.assertEqual({r['provider_id'] for r in rows}, {'9', '10'})
        self.assertEqual(catalog_members(self.root, '1', 'movie').keys(), {'9','10'})

    def test_removed_and_wrong_profile_details_do_not_authorize_identity(self):
        self.movies([{'stream_id': 9}])
        self.write('data_cache_p1_vod_info_10.json', {'movie_data':{'stream_id':10},'info':{'tmdb_id':42}})
        self.write('data_cache_p2_vod_info_9.json', {'movie_data':{'stream_id':9},'info':{'tmdb_id':42}})
        self.assertEqual(verified_vod_records(self.root, profile='1'), [])

    def test_title_enrichment_alone_does_not_prove_movie_identity(self):
        self.movies([{'stream_id':9,'name':'Ambiguous title','year':'2020'}])
        self.write('data_cache_p1_premium_meta_movie_9_es.json',
                   {'data':{'tmdb_id':42,'title':'Ambiguous title'}})
        self.assertEqual(verified_vod_records(self.root,profile='1'),[])

    def test_premium_lookup_does_not_add_external_identity_to_provider_movie(self):
        self.movies([{'stream_id':9,'name':'Film','year':'2020','imdb_id':'tt0012345'}])
        self.write('data_cache_p1_premium_meta_movie_9_es.json',
                   {'data':{'tmdb_id':42,'title':'Film'}})
        rows=verified_vod_records(self.root,profile='1')
        self.assertEqual(rows[0]['ids'],{'imdb':'tt0012345'})

    def test_conflicting_duplicate_ids_or_external_metadata_fail_closed(self):
        for rows in ([{'stream_id':9, 'name':'One'}, {'stream_id':9,'name':'Different'}],
                     [{'stream_id':9,'tmdb_id':42}]):
            with self.subTest(rows=rows):
                self.movies(rows)
                self.write('data_cache_p1_vod_info_9.json', {'movie_data':{'stream_id':9},'info':{'tmdb_id':99}})
                self.assertEqual(verified_vod_records(self.root, profile='1'), [])

    def test_unmaterialized_provider_series_details_authorize_explicit_episode_only(self):
        self.series([{'series_id':7}])
        path = self.write('data_cache_p1_series_info_7.json', {'info':{'tmdb':42},
            'episodes':{'2':[{'id':'99','season':2,'episode_num':3,'info':{'duration_secs':'1200'}}]}})
        snapshot = {'records':{'ep':{'identity':sync.identity('episode',show_ids={'tmdb':42},season=2,episode=3)}}}
        shows = verified_show_records(self.root,profile='1')
        result = verified_episode_records(self.root,profile='1',snapshot=snapshot,show_records=shows)
        self.assertEqual(result['records'][0]['provider_episode_id'],'99')
        self.assertEqual(result['records'][0]['duration_seconds'],1200)
        value=json.loads(path.read_text()); value['episodes']['2'][0]['season']=3
        path.write_text(json.dumps(value))
        self.assertEqual(verified_episode_records(self.root,profile='1',snapshot=snapshot,show_records=shows)['records'],[])

    def test_offset_index_is_reused_readonly_and_stale_index_falls_back(self):
        spec=importlib.util.spec_from_file_location('offset_test', ROOT/'third_party/xstream/provider_catalog_index.py')
        index=importlib.util.module_from_spec(spec);spec.loader.exec_module(index)
        rows=[{'stream_id':i+1,'name':'Title '+str(i),'tmdb_id':i+1,'added':i} for i in range(1000)]
        path=self.movies(rows)
        sidecar=index.CatalogIndex(str(path),'synthetic|user|secret',1,'movie',build=True)
        before=Path(sidecar.path).read_bytes()
        with patch('lib.trakt_provider_index.read_object', side_effect=AssertionError('full catalog read')):
            self.assertEqual(set(catalog_members(self.root,'1','movie',{'5'})),{'5'})
        self.assertEqual(Path(sidecar.path).read_bytes(),before)
        self.movies([{'stream_id':8}])
        self.assertEqual(set(catalog_members(self.root,'1','movie',{'8'})),{'8'})

    def test_title_candidates_cannot_authorize_watched_state(self):
        sys.path.insert(0,str(ROOT.parents[1]/'tools'))
        from prepare_trakt_catalog_mac import candidate_ids, provider_candidates, safe_catalog_evidence
        self.movies([{'stream_id':9,'title':'Exact candidate','year':'2020'}])
        candidates=candidate_ids(catalog_members(self.root,'1','movie'), {'movie:42':[['Exact candidate','2020']]})
        self.assertEqual(candidates,['9'])
        self.assertEqual(verified_vod_records(self.root,profile='1'),[])

    def test_private_catalog_evidence_redacts_provider_source_and_urls(self):
        sys.path.insert(0,str(ROOT.parents[1]/'tools'))
        from prepare_trakt_catalog_mac import safe_catalog_evidence
        source={'_src':'https://private.invalid|secret-user|secret-password', '_data':[
            {'stream_id':9,'name':'Film','year':'2020','tmdb_id':42,
             'url':'https://private.invalid/secret-stream','password':'secret-password'}]}
        evidence=safe_catalog_evidence(source,'movie')
        encoded=json.dumps(evidence)
        self.assertNotIn('secret',encoded)
        self.assertNotIn('private.invalid',encoded)
        self.assertEqual(evidence,{'_src':'redacted','_data':[
            {'stream_id':9,'name':'Film','year':'2020','tmdb_id':42}]})
        self.assertEqual(source['_src'],'https://private.invalid|secret-user|secret-password')
        with tempfile.TemporaryDirectory() as destination:
            path=Path(destination)/'data_cache_p1_xtream_streams_movie.json'
            path.write_text(json.dumps(evidence))
            self.assertEqual(catalog_members(destination,'1','movie')['9']['tmdb_id'],42)

    def test_provider_lookup_skips_already_verified_movie_ids(self):
        sys.path.insert(0,str(ROOT.parents[1]/'tools'))
        from prepare_trakt_catalog_mac import provider_candidates
        self.movies([{'stream_id':9,'name':'Film','year':'2020','tmdb_id':42},
                     {'stream_id':10,'name':'Other','year':'2021'}])
        self.write('data_cache_p1_vod_info_9.json',{
            'movie_data':{'stream_id':9,'name':'Film','year':'2020'},
            'info':{'tmdb_id':42}})
        self.assertEqual(provider_candidates('movie',['9','10'],self.root,'1'),['10'])
        self.assertEqual(provider_candidates('series',['9','10'],self.root,'1'),['9','10'])

    def test_preview_is_delta_and_preserves_more_recent_and_unknown_local_progress(self):
        self.write('watched_movies_p1.json',{'9':True, '12':False})
        refs={}
        items=[]
        for provider in ('9','10','11','12'):
            content=sync.identity('movie',{'tmdb':provider})
            item={'identity':content,'provider_id':provider,'watched':True,'watched_at':EARLY,
                  'position':400,'duration':1000,'paused_at':LATE}
            items.append(item)
            refs[provider+'||https://synthetic.invalid/movie/'+provider+'.mp4']={
                'name':provider,'url':'https://synthetic.invalid/movie/'+provider+'.mp4','stype':'movie',
                'position':200,'duration':1000,'timestamp': None if provider=='11' else
                (1 if provider=='10' else 9999999999)}
        self.write('resume_points_p1.json',refs)
        before={p.name:p.read_bytes() for p in self.root.iterdir()}
        result=preview_changes({'profile':'1','account':'x','items':items},self.root,profile='1')
        self.assertEqual(result['summary']['movies_watched_added'],2)
        self.assertEqual(result['summary']['local_unwatched_conflicts'],1)
        self.assertEqual(result['summary']['resumes_updated'],1)
        self.assertEqual(result['summary']['resumes_local_preserved'],3)
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.root.iterdir()})

    def test_generation_changes_for_metadata_but_not_progress(self):
        self.movies([{'stream_id':1}]); first=catalog_generation(self.root,'1')
        self.write('resume_points_p1.json',{'not':'an indexed source'})
        self.assertEqual(first,catalog_generation(self.root,'1'))
        self.write('data_cache_p1_vod_info_1.json',{'info':{'tmdb_id':42}})
        self.assertNotEqual(first,catalog_generation(self.root,'1'))

    def test_binding_change_during_export_never_queues_or_applies(self):
        self.movies([])
        bindings=iter([True,False])
        with patch.object(trakt_auto_cycle,'prepare_batches',side_effect=AssertionError('must not plan')):
            result=run_cycle(self.root/'service', self.root, account='user',profile='1',
                provider_scope='a'*64,activity_get=lambda:('user',{'all':LATE}),
                export_snapshot=lambda:self.root,apply_batch=lambda *a,**k:(_ for _ in ()).throw(AssertionError('apply')),
                addon=None,history=None,one_shot=True,binding_valid=lambda:next(bindings))
        self.assertEqual(result['status'],'suspended')
        self.assertFalse(list((self.root/'service').rglob('queue/*.json')))

    def test_native_snapshot_transport_never_refreshes_or_posts(self):
        package=os.environ.get('ACTWEETER_XSTREAM_LIVE_ZIP')
        self.assertTrue(package,'candidate ZIP required, this test must not be skipped')
        with zipfile.ZipFile(package) as z:
            tree=ast.parse(z.read('plugin.video.xstream-pro/resources/lib/trakt.py'))
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='snapshot_request')
        calls=[]
        def transport(method,*args,**kwargs):
            calls.append(method)
            return types.SimpleNamespace(status_code=401)
        namespace={'BASE_URL':'https://synthetic.invalid','_headers':lambda auth:{},
            '_http_request':transport,'_raise_trakt_error':lambda *a:(_ for _ in ()).throw(PermissionError()),
            'refresh_token':lambda:(_ for _ in ()).throw(AssertionError('POST'))}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'native-get','exec'),namespace)
        with self.assertRaises(PermissionError):namespace['snapshot_request']('/users/settings')
        self.assertEqual(calls,['GET'])
        with self.assertRaises(ValueError):namespace['snapshot_request']('/sync/history')

    def test_unchanged_remote_activity_reuses_verified_export_when_catalog_grows(self):
        from lib.trakt_live_queue import build_batch, write_ack
        self.movies([])
        service = self.root/'service'
        exported = self.root/'trakt_exports/snapshot-fixture'; exported.mkdir(parents=True)
        calls = []
        def export(): calls.append(1); return exported
        def prepare(folder, root, **kwargs):
            self.assertEqual(folder, exported)
            return [build_batch({'profile':'1','account':'user','items':[]},provider_scope='a'*64,
                consent=True,activity_fingerprint=kwargs['activity_fingerprint'],
                catalog_generation=kwargs['catalog_generation'],source_export=kwargs['source_export'])]
        def apply(path, ackroot, **kwargs):
            batch=json.loads(Path(path).read_text())
            return write_ack(Path(ackroot)/(batch['batch_id']+'.json'),batch,[])
        args=dict(account='user',profile='1',provider_scope='a'*64,
            activity_get=lambda:('user',{'all':LATE}),export_snapshot=export,apply_batch=apply,
            addon=None,history=None,one_shot=True)
        with patch.object(trakt_auto_cycle,'prepare_batches',side_effect=prepare):
            self.assertEqual(run_cycle(service,self.root,**args)['status'],'queued')
            self.assertEqual(run_cycle(service,self.root,**args)['status'],'applied')
            self.write('data_cache_p1_vod_info_9.json',{'info':{'tmdb_id':42}})
            self.assertEqual(run_cycle(service,self.root,**args)['status'],'queued')
            self.assertEqual(len(calls),1)
            self.assertEqual(run_cycle(service,self.root,**args)['status'],'applied')
            self.assertEqual(run_cycle(service,self.root,**args)['status'],'unchanged')

    def test_consumer_rejects_old_provider_catalog_even_with_new_account_consent(self):
        from lib import trakt_provider_index, trakt_live_queue
        self.movies([{'stream_id':9,'tmdb_id':42}])
        tree=ast.parse((ROOT/'third_party/xstream/trakt_live_consumer.py').read_text())
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_catalog_scope_verified')
        namespace={'Path':Path}
        with patch.dict(sys.modules,{'trakt_provider_index':trakt_provider_index,'trakt_live_queue':trakt_live_queue}):
            exec(compile(ast.Module(body=[node],type_ignores=[]),'scope-check','exec'),namespace)
            addon=types.SimpleNamespace(getSetting=lambda key:'Xtream Codes')
            scope=trakt_live_queue.provider_fingerprint('1','Xtream Codes','synthetic','user')
            self.assertTrue(namespace['_catalog_scope_verified']([{'kind':'movie'}],self.root,'1',scope,addon))
            other=trakt_live_queue.provider_fingerprint('1','Xtream Codes','other.invalid','user')
            self.assertFalse(namespace['_catalog_scope_verified']([{'kind':'movie'}],self.root,'1',other,addon))

    def test_corrupt_cached_export_is_recovered_without_advancing_checkpoint(self):
        from test_trakt_snapshot import exporter
        from test_trakt_sync import API
        self.movies([])
        service=self.root/'service'
        invalid=self.root/'trakt_exports/snapshot-invalid'; invalid.mkdir(parents=True)
        invalid.parent.chmod(0o700)
        cursor=service/'trakt_live/remote/profile_1.json'
        old={'schema':1,'account':'synthetic-user','profile':'1','provider_scope':'a'*64,
             'activity_fingerprint':trakt_auto_cycle._digest({'all':LATE}),
             'catalog_generation':'0'*64,'planner_contract':2,
             'source_export':'trakt_exports/snapshot-invalid'}
        (service/'trakt_live').mkdir(mode=0o700,parents=True)
        trakt_auto_cycle._write(cursor,old)
        previous=cursor.read_bytes();calls=[]
        def fresh():
            calls.append(1)
            exporter.export_snapshot(API().get,self.root/'trakt_exports','1')
            return next(path for path in (self.root/'trakt_exports').glob('snapshot-*') if path!=invalid)
        result=run_cycle(service,self.root,account='synthetic-user',profile='1',provider_scope='a'*64,
            activity_get=lambda:('synthetic-user',{'all':LATE}),export_snapshot=fresh,
            apply_batch=lambda *a,**k:(_ for _ in ()).throw(AssertionError('must not apply now')),
            addon=None,history=None,one_shot=True)
        self.assertEqual(result['status'],'queued')
        self.assertEqual(calls,[1])
        self.assertEqual(cursor.read_bytes(),previous)
