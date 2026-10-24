import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'addons/service.actweeter/resources'))
from lib.trakt_tmdb_discovery import discover

class TMDbDiscoveryTests(unittest.TestCase):
    def test_candidates_never_become_verified_and_duplicates_are_distinguished(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for typ, data in [('movie', [{'stream_id': 7, 'title':'A.I. Inteligencia Artificial', 'year':'2001'},
                                         {'stream_id': 7, 'title':'A.I. Inteligencia Artificial', 'year':'2001'}]),
                              ('series', [{'series_id': 9, 'title':'Breaking Bad', 'year':'2008'}])]:
                (root / ('data_cache_p1_xtream_streams_%s.json' % typ)).write_text(json.dumps({'_src':'host|user|secret', '_data':data}))
            snapshot={'records': {'m': {'identity': {'kind':'movie','ids':{'tmdb':'644'}}},
                                  'e': {'identity': {'kind':'episode','ids':{'tmdb':'1396'}}}}}
            meta={'movie': {'title':'A.I. Inteligencia Artificial','release_date':'2001-06-29'},
                  'show': {'name':'Breaking Bad','first_air_date':'2008-01-20'}}
            results=discover(snapshot,root,'1',lambda kind, ident:meta[kind]); self.assertEqual(len(results),2)
            self.assertEqual({x['status'] for x in results},{'candidate'})
            self.assertEqual({x['provider_id'] for x in results},{'7','9'})
            self.assertFalse(any(x.get('confidence')=='verified' for x in results))
            rows=json.loads((root/'data_cache_p1_xtream_streams_movie.json').read_text())
            rows['_data'].append({'stream_id': 8,'title':'A.I. Inteligencia Artificial','year':'2001'})
            (root/'data_cache_p1_xtream_streams_movie.json').write_text(json.dumps(rows))
            results=discover(snapshot,root,'1',lambda kind, ident:meta[kind]); self.assertEqual(results[1]['status'],'ambiguous')
