"""Execute the packaged provider index builder against an isolated SQLite database."""
import ast
import sqlite3
from contextlib import closing
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
PATCH=ROOT/'third_party/xstream/patches/1.1.2/actweeter-runtime.patch'


def provider_builder():
    patch=PATCH.read_text();start=patch.index('+++ b/resources/lib/premium_routes.py')
    end=patch.find('diff --git ',start+10)
    lines=patch[patch.index('@@ ',start):end if end!=-1 else len(patch)].splitlines()[1:]
    tree=ast.parse('\n'.join(line[1:] for line in lines if line.startswith('+') and not line.startswith('+++')))
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_ensure_search_index')
    return compile(ast.Module(body=[node],type_ignores=[]),str(PATCH),'exec')


class SearchSnapshotAtomicTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.path=Path(tmp.name)/'provider_search_1.sqlite'
        self.calls=[];self.stamps={'movie':'1','series':'1'}
        self.fail=None
        def catalog(g,stype,pnum,force_refresh=False):
            if stype==self.fail:raise RuntimeError('provider unavailable')
            if stype=='movie' and self.fail=='change_stamp':self.stamps['movie']='2'
            return ([{'stream_id':'11','series_id':'22','name':stype.title()}],('user','pass'))
        namespace={'time':time,'catalog':catalog,
                   '_search_index_path':lambda g,pnum:str(self.path),
                   '_search_filter_stamp':lambda g,pnum:'filters',
                   '_search_source_stamp':lambda g,pnum,stype:self.stamps[stype],
                   'provider_id':lambda item,stype:str(item['stream_id' if stype=='movie' else 'series_id']),
                   '_search_text':lambda title:title.casefold(),
                   '_safe_search_art':lambda value:'',}
        exec(provider_builder(),namespace)
        self.build=namespace['_ensure_search_index']
        self.g={'xbmcvfs':SimpleNamespace(translatePath=lambda p:str(self.path.parent)),
                'addon':SimpleNamespace(getAddonInfo=lambda k:str(self.path.parent)),
                '_log':self.calls.append}

    def run_builder(self,force=False):
        conn,results=self.build(self.g,1,force_provider_refresh=force)
        conn.close()
        return results

    def rows(self):
        with closing(sqlite3.connect(self.path)) as conn:
            return conn.execute('SELECT stype,provider_id FROM items ORDER BY stype').fetchall()

    def test_two_media_types_commit_together(self):
        results=self.run_builder()
        self.assertEqual([r['status'] for r in results],['success','success'])
        self.assertEqual(self.rows(),[('movie','11'),('series','22')])

    def test_series_provider_error_preserves_prior_rows(self):
        self.run_builder();original=self.rows();self.stamps={'movie':'2','series':'2'};self.fail='series'
        self.assertIn('error',[r['status'] for r in self.run_builder()]);self.assertEqual(self.rows(),original)

    def test_nonforced_cache_change_during_catalog_rejected(self):
        self.run_builder();original=self.rows();self.stamps={'movie':'3','series':'3'};self.fail='change_stamp'
        self.assertIn('error',[r['status'] for r in self.run_builder()]);self.assertEqual(self.rows(),original)

    def test_forced_provider_refresh_may_change_cache_stamp(self):
        self.fail='change_stamp';results=self.run_builder(force=True)
        self.assertEqual([r['status'] for r in results],['success','success'])
