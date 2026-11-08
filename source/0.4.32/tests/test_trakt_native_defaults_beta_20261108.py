"""Account-scoped, opt-in native Favorites/Watchlist release contracts."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sqlite3
import sys
import tempfile
import types
import unittest
import zipfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'source/0.4.32/addons/service.actweeter/resources/lib'
TOOLS=ROOT/'tools'
sys.path.insert(0,str(BASE.parent))
sys.path.insert(0,str(TOOLS))
from lib.collection_catalog import Catalog
from lib.trakt_outbox import Outbox
from enable_native_collections_patch import patch as patch_native

BETA=ROOT/'docs/testing/repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.44~beta9.zip'
SERVICE_BETA=ROOT/'docs/testing/repo/service.actweeter/service.actweeter-0.4.104~beta2.zip'
SCOPE={'account':'synthetic','profile':'1','provider_scope':'a'*64,
       'kodi_profile':'b'*64,'generation':'c'*64}


def routes():
    with zipfile.ZipFile(BETA) as z:
        raw=z.read('plugin.video.xstream-pro/resources/lib/trakt_auto_routes.py')
    namespace={'__name__':'native_beta_routes'}
    exec(compile(raw,'trakt_auto_routes.py','exec'),namespace)
    return types.SimpleNamespace(**namespace)


class NativeCollectionsBeta(unittest.TestCase):
    def test_four_canonical_mappings_and_repeated_noop(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Catalog(Path(folder)/'catalog.db')
            self.assertEqual(store.ensure_native_defaults(
                scope=SCOPE,favorites_folder='Favoritos',approved=True),
                {'created':4,'existing':0,'refreshed':0})
            self.assertEqual(store.ensure_native_defaults(
                scope=SCOPE,favorites_folder='Favoritos',approved=True),
                {'created':0,'existing':4,'refreshed':0})
            with store._db() as db:
                entries=[json.loads(row[0]) for row in db.execute('SELECT mappings FROM lists')]
            self.assertCountEqual([x['trakt_sync']['destination'] for x in entries],
                                  ['favorites','favorites','watchlist','watchlist'])
            self.assertEqual({x['xstream_source']['media_type'] for x in entries},
                             {'movie','series'})
            self.assertEqual({x['xstream_source']['folder'] for x in entries},
                             {'Favoritos','AcTweeteR Pending - Movies','AcTweeteR Pending - Series'})

    def test_requires_consent_and_never_rebinds_another_account(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Catalog(Path(folder)/'catalog.db')
            with self.assertRaises(PermissionError):
                store.ensure_native_defaults(scope=SCOPE,favorites_folder='Favoritos',approved=False)
            with self.assertRaises(ValueError):
                store.ensure_native_defaults(scope={**SCOPE,'generation':'bad'},
                                             favorites_folder='Favoritos',approved=True)
            store.ensure_native_defaults(scope=SCOPE,favorites_folder='Favoritos',approved=True)
            with self.assertRaises(PermissionError):
                store.ensure_native_defaults(scope={**SCOPE,'account':'different'},
                                             favorites_folder='Favoritos',approved=True)
            with store._db() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM lists').fetchone()[0],4)

    def test_token_refresh_is_allowed_only_for_same_account_provider_and_kodi(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Catalog(Path(folder)/'catalog.db')
            store.ensure_native_defaults(scope=SCOPE,favorites_folder='Favoritos',approved=True)
            refreshed={**SCOPE,'generation':'e'*64}
            self.assertEqual(store.ensure_native_defaults(
                scope=refreshed,favorites_folder='Favoritos',approved=True),
                {'created':0,'existing':4,'refreshed':4})
            with store._db() as db:
                rows=[json.loads(r[0]) for r in db.execute('SELECT mappings FROM lists')]
            self.assertTrue(all(r['trakt_sync']['scope']==refreshed for r in rows))
            self.assertEqual(store.ensure_native_defaults(
                scope=refreshed,favorites_folder='Favoritos',approved=True)['refreshed'],0)
            with self.assertRaises(PermissionError):
                store.ensure_native_defaults(
                    scope={**refreshed,'provider_scope':'f'*64},
                    favorites_folder='Favoritos',approved=True)

    def test_preexisting_manual_destination_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Catalog(Path(folder)/'catalog.db')
            store.ensure_native_defaults(scope=SCOPE,favorites_folder='Favorites',approved=True)
            with store._db() as db:
                identifier,raw=db.execute("SELECT local_id,mappings FROM lists WHERE kind='movie' ORDER BY name LIMIT 1").fetchone()
                data=json.loads(raw);data['trakt_sync']['destination']='list.123'
                db.execute('UPDATE lists SET mappings=? WHERE local_id=?',(json.dumps(data),identifier))
            store.ensure_native_defaults(scope=SCOPE,favorites_folder='Favorites',approved=True)
            self.assertEqual(store.get(identifier)['mappings']['trakt_sync']['destination'],'list.123')

    def test_initial_local_items_queue_additions_only_and_no_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            catalog=Catalog(root/'catalog.db')
            catalog.ensure_native_defaults(scope=SCOPE,favorites_folder='Favoritos',approved=True)
            with catalog._db() as db:
                identifier,mapping=next((i,json.loads(m)) for i,m in db.execute('SELECT local_id,mappings FROM lists')
                                        if json.loads(m)['xstream_source']['folder']=='AcTweeteR Pending - Movies')
            binding=mapping['trakt_sync'];source=mapping['xstream_source']
            rows=[{'id':'71','stype':'movie'},{'id':'72','stype':'movie'},
                  {'id':'73','stype':'series'},{'id':'74','stype':'movie','actweeter_trakt_origin':binding['revision']}]
            addon=types.SimpleNamespace(getAddonInfo=lambda *_:str(root))
            fake_favs=types.SimpleNamespace(Favorites=lambda *a:types.SimpleNamespace(get_all=lambda *_:rows))
            fake_provider=types.SimpleNamespace(verified_vod_records=lambda *a,**k:[
                {'provider_id':'71','ids':{'tmdb':100}},{'provider_id':'72','ids':{'tmdb':200}}])
            modules={'favorites':fake_favs,'trakt_provider_index':fake_provider,
                     'trakt_series_index':types.SimpleNamespace(verified_show_records=lambda *a,**k:[]),
                     'trakt_live_consumer':types.SimpleNamespace(_catalog_scope_verified=lambda *a,**k:True)}
            vfs=types.SimpleNamespace(translatePath=lambda x:x)
            with patch.dict(sys.modules,modules):
                mod=routes()
                args=(lambda _:addon,catalog,identifier,source,binding,SCOPE,
                      [{'kind':'movie','tmdb_id':200,'title':'already'}],root,vfs)
                self.assertEqual(mod._stage_first_native_additions(*args),1)
                self.assertEqual(mod._stage_first_native_additions(*args),1)
            with Outbox(root/'trakt_explicit_outbox.sqlite').connect() as db:
                events=[(json.loads(raw),state) for raw,state in db.execute('SELECT event,state FROM events')]
            self.assertEqual(len(events),1)
            self.assertEqual(events[0][1],'held')
            self.assertEqual(events[0][0]['endpoint'],'/sync/watchlist')
            self.assertEqual(events[0][0]['payload'],{'movies':[{'ids':{'tmdb':100}}]})

    def test_candidate_delta_is_bounded_and_stable_untouched(self):
        from build_native_trakt_collections_beta import build
        with zipfile.ZipFile(BETA) as z, zipfile.ZipFile(
                ROOT/'docs/testing/repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.44~beta8.zip') as old:
            self.assertIsNone(z.testzip())
            text=z.read('plugin.video.xstream-pro/resources/lib/trakt_auto_routes.py').decode()
            self.assertEqual(text,patch_native(old.read('plugin.video.xstream-pro/resources/lib/trakt_auto_routes.py').decode()))
            for marker in ('with journal.runtime_scope(native_store)',
                           'ensure_native_defaults(', '_stage_first_native_additions(',
                           'if incomplete:', 'if import_allowed and not one_shot:', 'adopted.update(', 'only_id=target_id'):
                self.assertIn(marker,text)
        with tempfile.TemporaryDirectory() as folder:
            for aid,pkg in [('service.actweeter',SERVICE_BETA),('plugin.video.xstream-pro',BETA)]:
                output=Path(folder)/pkg.name
                self.assertEqual(build(aid,output)['version'],
                                 {'service.actweeter':'0.4.104~beta2',
                                  'plugin.video.xstream-pro':'1.1.2.44~beta9'}[aid])
                self.assertEqual(hashlib.sha256(output.read_bytes()).digest(),
                                 hashlib.sha256(pkg.read_bytes()).digest())
