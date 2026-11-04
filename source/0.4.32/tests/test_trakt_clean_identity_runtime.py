"""A clean profile imports Trakt data and resolves identities through real XStream routes."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = r'''
import json, sqlite3, subprocess, sys, tempfile, time, types
from pathlib import Path
root=Path(tempfile.mkdtemp())
sys.path.insert(0, sys.argv[2])
sys.path.insert(0, sys.argv[1] + '/plugin.video.xstream-pro/resources/lib')
xbmc=types.ModuleType('xbmc'); xbmc.LOGWARNING=2; xbmc.log=lambda *a:None
xbmc.getCondVisibility=lambda *a:False; sys.modules['xbmc']=xbmc
addonmod=types.ModuleType('xbmcaddon'); addonmod.Addon=lambda *a:None; sys.modules['xbmcaddon']=addonmod
vfs=types.ModuleType('xbmcvfs'); vfs.translatePath=lambda p:str(root); sys.modules['xbmcvfs']=vfs
import history, series_state, content_state, premium_routes
from trakt_live_queue import build_batch, write_batch, provider_fingerprint
from trakt_live_consumer import apply_batch
addon=types.SimpleNamespace(getAddonInfo=lambda k:str(root), getSetting=lambda k:'Xtream Codes')
shows=[
 {'provider':'10','title':'Paradise','year':'2025','ids':{'tmdb':'245927'},'seasons':[8,8],'provider_seasons':[8,8],'watched':16},
 {'provider':'20','title':'Tierra de mafiosos','year':'2025','ids':{'tmdb':'247718'},'seasons':[10,10],'provider_seasons':[10,7],'watched':10}]
db=sqlite3.connect(root/'provider_search_1.sqlite')
db.execute('CREATE TABLE items (stype TEXT,provider_id TEXT,title TEXT,norm TEXT,year TEXT)')
for show in shows:
 db.execute('INSERT INTO items VALUES (?,?,?,?,?)',('series',show['provider'],show['title']+' (2025)',show['title'].lower()+' 2025',show['year']))
db.commit();db.close()
items=[]; inventories={}; metadata={}
for show in shows:
 rows=[{'season':s,'episode':e,'provider_id':str(1000+s*100+e)}
       for s,count in enumerate(show['provider_seasons'],1) for e in range(1,count+1)]
 inventories[show['provider']]={'complete':True,'checked_at':time.time(),'episodes':rows}
 metadata[show['title']]={'id':int(show['ids']['tmdb']),'first_air_date':show['year']+'-01-01',
     'seasons':[{'season_number':s,'episode_count':n} for s,n in enumerate(show['seasons'],1)]}
 for row in rows[:show['watched']]:
  items.append({'identity':{'kind':'episode','ids':dict(show['ids']),
               'season':row['season'],'episode':row['episode']},'watched':True,'watched_at':1700000000})
scope=provider_fingerprint('1','Xtream Codes','https://provider.invalid','account')
batch=build_batch({'profile':'1','account':'test-account','items':items},provider_scope=scope,
                  consent=True,target='tmdb',batch_id='1'*32)
queue=root/'service'/'trakt_live'/'queue'; path=write_batch(queue,batch)
ack=apply_batch(path,root/'service'/'trakt_live'/'acks',profile='1',account='test-account',
                provider_scope=scope,addon=addon,history=history,catalog_root=root)
assert all(row['status']=='applied' for row in ack['results'])
calls=[]
tmdb=types.ModuleType('tmdb')
tmdb.paged=lambda path,media,params,ttl:(calls.append(params['query']) or {'total_pages':1,'results':[{'tmdb_id':str(metadata[params['query']]['id']),'title':params['query'],'year':'2025'}]})
tmdb.details=lambda media,ident:next(value for value in metadata.values() if str(value['id'])==str(ident))
tmdb.image_url=lambda value,*a:'';tmdb.fanart_url=lambda value:'';sys.modules['tmdb']=tmdb
class Tag:
 def __getattr__(self,name): return lambda *a:None
class Card:
 def __init__(self): self.properties={}
 def setProperty(self,key,value): self.properties[key]=value
 def getVideoInfoTag(self): return Tag()
 def setArt(self,value): pass
cache={}
g={'addon':addon,'xbmcvfs':vfs,'_cache_load':lambda key,**kw:cache.get(key),
   '_cache_save':lambda key,value:cache.__setitem__(key,value),'_new_listitem':lambda *a:Card(),
   '_log':lambda *a:None,'pm':types.SimpleNamespace(active='1'),
   'series_changes':types.SimpleNamespace(series_state=series_state,
                                          inventory_map=lambda *a:inventories)}
ctx={'inventory':inventories,'watched':history.WatchedEpisodes(addon,1),
     'tmdb_watched':history.WatchedMovies(addon,1),'resume':[]}
for show in shows:
 item={'series_id':show['provider'],'name':show['title']+' (2025)','year':show['year']}
 data=premium_routes.enrich(g,item,'series',{'title':item['name'],'year':show['year']},[1,0])
 card=premium_routes.listitem(g,item,'series',data,profile_num=1,series_context=ctx)
 fresh={'addon':addon,'xbmcvfs':vfs}
 resolved=content_state.provider_tmdb_id(fresh,'series',show['provider'],1)
 assert resolved==show['ids']['tmdb']
 state=series_state.derive_series_state(resolved,show['provider'],inventories[show['provider']],
           ctx['watched'],tmdb_watched_store=ctx['tmdb_watched'])
 assert state['watched']==show['watched'] and state['total']==sum(show['provider_seasons']),state
 assert card.properties['XStream.SeriesComplete']==('true' if show['watched']==16 else 'false')
 assert content_state.tmdb_watched_state(g,{'tmdb_type':'tv','tmdb_id':resolved},
             ctx['tmdb_watched'],ctx['watched']) is (show['watched']==16)
 assert content_state.provider_tmdb_id({'addon':addon,'xbmcvfs':vfs},'series',show['provider'],1)==resolved
 premium_routes.enrich(g,item,'series',{'title':item['name'],'year':show['year']},[1,0])
assert calls==['Paradise','Tierra de mafiosos']
restart="""import json,sys,types
sys.path.insert(0,sys.argv[1]+'/plugin.video.xstream-pro/resources/lib')
import content_state
root=sys.argv[2];g={'addon':types.SimpleNamespace(getAddonInfo=lambda _:root),
 'xbmcvfs':types.SimpleNamespace(translatePath=lambda value:value)}
print(json.dumps([content_state.provider_tmdb_id(g,'series',sid,1) for sid in ('10','20')]))
"""
recovered=json.loads(subprocess.check_output([sys.executable,'-c',restart,sys.argv[1],str(root)],text=True))
assert recovered==[show['ids']['tmdb'] for show in shows]
print('PASS')
'''


class CleanIdentityRuntimeTests(unittest.TestCase):
    @unittest.skipIf(os.environ.get('ACTWEETER_RELEASE_CHANNEL') == 'stable',
                     'requires Beta6 XStream identity recovery')
    def test_clean_profile_import_and_recovery(self):
        package = os.environ.get('ACTWEETER_XSTREAM_LIVE_ZIP')
        self.assertTrue(package, 'exact candidate ZIP required')
        result = subprocess.run([sys.executable, '-c', SCRIPT, package,
            str(ROOT / 'addons/service.actweeter/resources/lib')],
            text=True, capture_output=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS', result.stdout)
