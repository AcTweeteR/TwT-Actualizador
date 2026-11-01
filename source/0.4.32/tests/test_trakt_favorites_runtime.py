"""Real packaged Favorites/PendingAdapter, synthetic profile and no network."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

SCRIPT = r"""
import json, sqlite3, sys, tempfile, types
from pathlib import Path
root=Path(tempfile.mkdtemp())
sys.modules['xbmc']=types.SimpleNamespace(getCondVisibility=lambda *_: False, log=lambda *_: None, LOGWARNING=2)
sys.modules['xbmcvfs']=types.SimpleNamespace(translatePath=lambda path: path)
sys.modules['lang']=types.SimpleNamespace(_t=lambda _: 'Favorites')
sys.path.insert(0, sys.argv[1]+'/plugin.video.xstream-pro/resources/lib')
from favorites import Favorites
from pending_adapter import PendingAdapter
addon=types.SimpleNamespace(getAddonInfo=lambda _: str(root))
one, two=Favorites(addon, '1'), Favorites(addon, '1')
one.add({'id':'42','stype':'movie','url':'https://secret.invalid/a'})
two.add({'id':'42','stype':'series','url':'https://secret.invalid/b'})
assert len(Favorites(addon,'1').get_favorites())==2
pending=PendingAdapter(Favorites(addon,'1'))
assert pending.add('movie', {'id':'42','stype':'movie'})
assert pending.remove('movie','42')
assert Favorites(addon,'1').remove('42',stype='movie')
assert len(Favorites(addon,'1').get_favorites())==1
with sqlite3.connect(root/'trakt_local_changes.sqlite') as db:
 rows=db.execute('SELECT event,state FROM changes').fetchall()
assert len(rows)==5
assert all(state=='quarantined' for _,state in rows)
assert 'secret.invalid' not in str(rows)
changes=[change for raw,_ in rows for change in json.loads(raw)['changes']]
assert [c['change'] for c in changes if c['collection']=='pending']==['add','remove']
assert any(c['change']=='remove' and c['media_type']=='movie' for c in changes)

for folder in ('Favorites','AcTweeteR Pending - Movies','AcTweeteR Pending - Series'):
 for media in ('movie','series'):
  store=Favorites(addon,'1')
  store.apply_trakt(folder,media,[dict(id='99',stype=media,name='Synthetic')],'revision',lambda:set())
  assert store.is_favorite('99',folder,media)
  store=Favorites(addon,'1')
  store.apply_trakt(folder,media,[],'revision',lambda:{'99'})
  assert store.is_favorite('99',folder,media)
  store.apply_trakt(folder,media,[],'revision',lambda:set())
  assert not store.is_favorite('99',folder,media)
with sqlite3.connect(root/'trakt_local_changes.sqlite') as db:
 imported=db.execute("SELECT event FROM changes WHERE state='observed'").fetchall()
assert len(imported)==12
assert all(json.loads(raw)['origin']=='trakt_import' for raw, in imported)
for index,(folder,media) in enumerate([('Favorites','movie'),('Favorites','series'),
 ('AcTweeteR Pending - Movies','movie'),('AcTweeteR Pending - Series','series')]):
 ident=str(500+index)
 store=Favorites(addon,'1')
 assert store.add(dict(id=ident,stype=media,name='Local'),folder)
 with sqlite3.connect(root/'trakt_local_changes.sqlite') as db:
  original_count=db.execute("SELECT count(*) FROM changes WHERE state='quarantined'").fetchone()[0]
 def interrupted():
  raise RuntimeError('interrupted after native save')
 try:
  store.apply_trakt(folder,media,[dict(id=ident,stype=media,name='Local')],
                    'confirmed',lambda:(set(),{ident},interrupted))
 except RuntimeError: pass
 else: raise AssertionError('interruption was not simulated')
 store=Favorites(addon,'1')
 assert store.is_favorite(ident,folder,media)
 store.apply_trakt(folder,media,[dict(id=ident,stype=media,name='Local')],
                   'confirmed',lambda:(set(),{ident},lambda:None))
 store=Favorites(addon,'1')
 store.apply_trakt(folder,media,[],'confirmed',lambda:({ident},set(),lambda:None))
 assert store.is_favorite(ident,folder,media)
 store.apply_trakt(folder,media,[],'confirmed',lambda:(set(),set(),lambda:None))
 assert not Favorites(addon,'1').is_favorite(ident,folder,media)
 with sqlite3.connect(root/'trakt_local_changes.sqlite') as db:
  assert db.execute("SELECT count(*) FROM changes WHERE state='quarantined'").fetchone()[0]==original_count



# Exercise the packaged write, durable handoff, simulated POST and native import.
from contextlib import contextmanager
sys.path.insert(0, sys.argv[2]+'/addons/service.actweeter/resources')
sys.path.insert(0, sys.argv[2]+'/third_party/xstream')
import trakt_local_journal as journal
import trakt_auto_routes as routes
from lib.collection_catalog import Catalog
from lib.trakt_outbox import Outbox
import lib.collection_catalog as catalog_module
scope=dict(account='synthetic',profile='1',provider_scope='a'*64,kodi_profile='b'*64,generation='c'*64)
catalog_module._runtime_scope=lambda:scope
catalog=Catalog(root/'collections_catalog.db')
queue=Outbox(root/'trakt_explicit_outbox.sqlite')
@contextmanager
def bound(_):
 with journal.verified_scope(**scope): yield
journal.runtime_scope=bound
journal.runtime_handoff=lambda _:None
sys.modules['trakt_live_consumer']=types.SimpleNamespace(_catalog_scope_verified=lambda *args:True)
sys.modules['trakt_provider_index']=types.SimpleNamespace(
 verified_vod_records=lambda *a,**k:[dict(provider_id='900',ids=dict(tmdb=900))],
 catalog_members=lambda *a,**k:{'900':dict(name='Synthetic')})
sys.modules['trakt_series_index']=types.SimpleNamespace(
 verified_show_records=lambda *a,**k:[dict(provider_id='900',ids=dict(tmdb=900))])
for folder,media in [('Favorites','movie'),('Favorites','series'),
 ('AcTweeteR Pending - Movies','movie'),('AcTweeteR Pending - Series','series')]:
 local=catalog.create_local('synthetic',kind='movie' if media=='movie' else 'show',origin='mis_colecciones')
 mapping=catalog.configure_destination(local,scope=scope,destination='watchlist',verified=True,confirmed=True)
 source=dict(folder=folder,folder_sha256=journal._hash(folder),media_type=media)
 with catalog._db() as db:
  value=json.loads(db.execute('SELECT mappings FROM lists WHERE local_id=?',(local,)).fetchone()[0])
  value['xstream_source']=source
  db.execute('UPDATE lists SET mappings=? WHERE local_id=?',(json.dumps(value),local))
 def capture(_,binding,changes):
  for change in changes:
   change['destination_capture']=mapping
   change['external_identity']=dict(kind='movie' if media=='movie' else 'show',ids=dict(tmdb=900))
 journal._capture_native_destinations=capture
 store=Favorites(addon,'1')
 assert store.add(dict(id='900',stype=media,name='Synthetic'),folder)
 assert journal.deliver(store.file,queue,scope=scope)>=1
 with sqlite3.connect(root/'trakt_local_changes.sqlite') as db:
  records=[(ident,json.loads(raw)) for ident,raw in db.execute("SELECT id,event FROM changes WHERE state='queued'")]
 event_id,event=next((ident,event) for ident,event in records if event.get('scope')==scope and event['changes'][0].get('destination_capture')==mapping)
 operation=event['outbox_ids'][0]
 assert queue.send_manual(operation,account='synthetic',profile='1',provider_scope='a'*64,
  approved=operation,now=1,post=lambda *args:{'added':{'movies' if media=='movie' else 'shows':1},'not_found':{}})=='confirmed'
 remote=[dict(kind='movie' if media=='movie' else 'show',tmdb_id=900,title='Synthetic')]
 catalog.apply_remote(local,scope=scope,revision=mapping['revision'],items=remote,observed_at=100,complete=True)
 routes.sync_native_collection(lambda _:addon,catalog,local,source,mapping,scope,remote,root,None,types.SimpleNamespace(translatePath=lambda x:x),100,{event_id})
 with sqlite3.connect(root/'trakt_local_changes.sqlite') as db:
  assert db.execute('SELECT state FROM changes WHERE id=?',(event_id,)).fetchone()[0]=='confirmed'
 catalog.apply_remote(local,scope=scope,revision=mapping['revision'],items=[],observed_at=101,complete=True)
 routes.sync_native_collection(lambda _:addon,catalog,local,source,mapping,scope,[],root,None,types.SimpleNamespace(translatePath=lambda x:x),101,set())
 assert not Favorites(addon,'1').is_favorite('900',folder,media)
 with queue.connect() as db: assert db.execute('SELECT count(*) FROM events').fetchone()[0]==[('Favorites','movie'),('Favorites','series'),('AcTweeteR Pending - Movies','movie'),('AcTweeteR Pending - Series','series')].index((folder,media))+1

"""

class FavoritesRuntimeTests(unittest.TestCase):
    def test_packaged_favorites_pending_capture_and_concurrent_instances(self):
        channel=os.environ.get('ACTWEETER_RELEASE_CHANNEL')
        if channel == 'stable':
            self.skipTest('Beta-only Trakt 2.0 runtime contract; Stable validated separately')
        package=os.environ.get('ACTWEETER_XSTREAM_LIVE_ZIP')
        if not package:
            if channel == 'testing':
                self.fail('testing requires the exact candidate ZIP')
            self.skipTest('exact candidate ZIP required outside release validation')
        result=subprocess.run([sys.executable,'-c',SCRIPT,str(Path(package).resolve()),str(Path(__file__).resolve().parents[1])],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
