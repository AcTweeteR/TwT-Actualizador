"""Regression contracts for Beta4 EPG and Beta2 watched/widget XStream.

All writes and state mutations operate on temporary fakes, never user profiles.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import io
import sys
import tempfile
import time
import types
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
SOURCE = ROOT/'source/0.4.32/addons/skin.actweeter/1080i'
REPO = ROOT/'docs/testing/repo'
SKIN = REPO/'skin.actweeter/skin.actweeter-1.2.41~beta4.zip'
XSTREAM = REPO/'plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.40~beta2.zip'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def get_member(addon,relative):
    file=SKIN if addon=='skin.actweeter' else XSTREAM
    with zipfile.ZipFile(file) as z:
        return z.read(f'{addon}/{relative}')


class _FakeStore:
    def __init__(self):
        self._data={}
        self.saves=0
    def _save(self):
        self.saves+=1


class _FakeKodi:
    LOGINFO=1;LOGWARNING=2
    def __init__(self,playing=False):
        self.playing=playing
        self.commands=[]
        self.logs=[]
    def getCondVisibility(self,condition):
        assert condition=='Player.HasMedia'
        return self.playing
    def executebuiltin(self,command):
        self.commands.append(command)
    def log(self,*args):
        self.logs.append(args)


class _FakeGui:
    def __init__(self):
        self.properties={}
        self.notifications=[]
    def Window(self,id_):
        assert id_==10000
        return types.SimpleNamespace(
            setProperty=lambda name,value:self.properties.__setitem__(name,value))
    def Dialog(self):
        return types.SimpleNamespace(
            notification=lambda *args:self.notifications.append(args))


class EpgWatchedPerformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder=module('build_epg_watched_perf_beta','tools/build_epg_watched_perf_beta.py')
        cls.patch=module('epg_watch_performance_patch','tools/epg_watch_performance_patch.py')
        cls.watch_code=get_member('plugin.video.xstream-pro','resources/lib/watch_ui_refresh.py')
        cls.actions_code=get_member('plugin.video.xstream-pro','resources/lib/watched_actions.py')
        cls.premium_code=get_member('plugin.video.xstream-pro','resources/lib/premium_routes.py')
        cls.addon_code=get_member('plugin.video.xstream-pro','resources/lib/addon.py')

    def test_zero_width_programme_titles_are_fixed_in_both_layouts(self):
        root=ET.parse(SOURCE/'IncludesViews.xml').getroot()
        for name in ('PVRGuideItemLayout','PVRGuideItemLayoutFocus'):
            layout=root.find(f'include[@name="{name}"]')
            self.assertIsNotNone(layout)
            controls=[c for c in layout.findall("control")
                      if c.get('type')=='label' and c.findtext('label')=='$INFO[ListItem.Label]']
            self.assertEqual(len(controls),2)
            for label in controls:
                self.assertEqual(label.findtext('width'),'90%')
                self.assertEqual(label.findtext('left'),'5%')
                self.assertEqual(label.findtext('right'),'5%')
            images=[c for c in layout.findall('control') if c.get('type')=='image'
                    and 'diffuse/panel.png' in (c.findtext('texture') or '')]
            self.assertTrue(images)
            self.assertTrue(all(c.findtext('width')=='98%' for c in images))
        with zipfile.ZipFile(SKIN) as z:
            self.assertEqual(z.read('skin.actweeter/1080i/IncludesViews.xml'),
                             (SOURCE/'IncludesViews.xml').read_bytes())

    def test_pvr_guide_and_client_stay_native(self):
        with zipfile.ZipFile(SKIN) as z:
            guide=ET.fromstring(z.read('skin.actweeter/1080i/MyPVRGuide.xml'))
            self.assertIsNotNone(guide.find('.//control[@type="epggrid"]'))
        with zipfile.ZipFile(REPO/'skin.actweeter/skin.actweeter-1.2.41~beta3.zip') as z:
            before=z.read('skin.actweeter/1080i/MyPVRGuide.xml')
        self.assertEqual(get_member('skin.actweeter','1080i/MyPVRGuide.xml'),before)

    def test_mutation_only_invalidation_and_deferred_refresh(self):
        kodi=_FakeKodi()
        gui=_FakeGui()
        env={}
        exec(self.watch_code,env)
        result=env['invalidate_after_watched_mutation'](
            {'xbmc':kodi,'xbmcgui':gui},event='test')
        self.assertEqual(result,{'status':'invalidated','scheduled':True})
        self.assertEqual(len(gui.properties),3)
        self.assertEqual(len(set(gui.properties.values())),1)
        self.assertIn('Premium.CollectionsRefresh',gui.properties)
        self.assertIn('Premium.ContinueRefresh',gui.properties)
        self.assertTrue(kodi.commands[0].startswith('CancelAlarm('))
        self.assertIn('AlarmClock(AcTweeteRWatchedRefresh,Container.Refresh,00:00:02,silent)',
                      kodi.commands)
        self.assertFalse(any('Container.Update(' in x or 'ReloadSkin' in x for x in kodi.commands))

    def test_mutation_during_playback_never_refreshes_screen(self):
        kodi=_FakeKodi(playing=True)
        gui=_FakeGui()
        env={}
        exec(self.watch_code,env)
        result=env['invalidate_after_watched_mutation'](
            {'xbmc':kodi,'xbmcgui':gui},event='playback')
        self.assertEqual(result,{'status':'invalidated','scheduled':False})
        self.assertEqual(kodi.commands,[])
        self.assertTrue(gui.properties)

    def test_movie_and_episode_toggle_refresh_only_after_store_save(self):
        service=types.ModuleType('watch_ui_refresh')
        exec(self.watch_code,service.__dict__)
        env={}
        exec(self.actions_code,env)
        kodi=_FakeKodi();gui=_FakeGui();store=_FakeStore()
        g={'xbmc':kodi,'xbmcgui':gui,'pm':types.SimpleNamespace(active='1'),
           'WatchedMovies':lambda addon,profile_num:store,
           'addon':object(),'_t':lambda key:str(key)}
        with patch.dict(sys.modules,{'watch_ui_refresh':service}):
            movie={'tmdb_id':['198184'],'tmdb_type':['movie'],
                   'season':[''],'episode':['']}
            self.assertIs(env['toggle_tmdb_watched'](g,movie),True)
            self.assertIs(store._data['tmdb:movie:198184'],True)
            self.assertEqual(store.saves,1)
            self.assertEqual(len(gui.notifications),1)
            self.assertTrue(gui.properties)
            self.assertIs(env['toggle_tmdb_watched'](g,movie),False)
            self.assertIs(store._data['tmdb:movie:198184'],False)
            self.assertEqual(store.saves,2)
            self.assertEqual(len(gui.notifications),2)
            episode={'tmdb_id':['3000'],'tmdb_type':['tv'],
                     'season':['2'],'episode':['4']}
            self.assertIs(env['toggle_tmdb_watched'](g,episode),True)
            self.assertIs(store._data['tmdb:episode:3000:s2:e4'],True)
            self.assertEqual(store.saves,3)
            initial=len(kodi.commands)
            invalid={'tmdb_id':['not-id'],'tmdb_type':['movie'],
                     'season':[''],'episode':['']}
            self.assertIsNone(env['toggle_tmdb_watched'](g,invalid))
            self.assertEqual(store.saves,3)
            self.assertEqual(len(kodi.commands),initial)

    def test_episode_progress_success_hook_and_safe_failures(self):
        s=self.addon_code.decode()
        marker='result = mark_progress(globals(), args)'
        self.assertEqual(s.count(marker),1)
        a=s.index(marker)
        b=s.index('xbmcgui.Dialog().notification(',a)
        snippet=s[a:b]
        self.assertIn('invalidate_after_watched_mutation(globals(), event=',snippet)
        self.assertIn("'mark_progress_to'",snippet)
        # The callback remains inside the try after success; incomplete
        # inventories still refuse all mutation.
        self.assertIn('except IncompleteSeriesInventory:',s[b:b+700])

    def test_first_paint_uses_provider_and_warm_cache_without_external_enrichment(self):
        s=self.premium_code.decode()
        self.assertIn("fast_widget = get('actweeter_expand') == '1'",s)
        self.assertIn("budget = [0, 0] if fast_widget else [4, 1]",s)
        self.assertIn('ranked_provider_items(g, items, stype, view, fast=fast_widget)',s)
        self.assertIn("get('browse') != '1'",s)
        # Compile and call the real enrichment function, not a duplicate
        # reimplementation in the test.
        tree=ast.parse(s)
        func=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='enrich')
        code=compile(ast.fix_missing_locations(ast.Module(body=[func],type_ignores=[])),
                     '<premium.enrich>','exec')
        network=[]
        cache={}
        env={
          'time':time,'re':__import__('re'),
          'normalized':lambda x:''.join(c for c in str(x).casefold() if c.isalnum()),
          'provider_id':lambda item,stype:item['stream_id'],
          'number':lambda x:int(x) if x else 0,
          'content_state':types.SimpleNamespace(),
          '_performance_call':lambda g,name,fn,*a,**kw:(network.append(name) or fn(*a,**kw)),
        }
        exec(code,env)
        g={'_cache_load':lambda key:cache.get(key,{}),
           '_cache_save':lambda key,value:cache.__setitem__(key,value),
           '_log':lambda message:None}
        data={'title':'Sample','poster_url':'poster.jpg','fanart_url':'backdrop.jpg',
              'year':2026,'tmdb_id':''}
        item={'stream_id':'123','name':'Sample','year':2026}
        result=env['enrich'](g,item,'movie',dict(data),[0,0])
        self.assertEqual(network,[])
        self.assertEqual(result['poster_url'],'poster.jpg')
        self.assertEqual(result['fanart_url'],'backdrop.jpg')
        self.assertEqual(result['title'],'Sample')
        cache['premium_meta_movie_123_es']={'expires':time.time()+300,
                'data':{'plot':'cached plot','rating':8.5}}
        result=env['enrich'](g,item,'movie',dict(data),[0,0])
        self.assertEqual(result['plot'],'cached plot')
        self.assertEqual(network,[])

    def test_full_browse_original_budget_and_ranking_refresh_remain(self):
        s=self.premium_code.decode()
        self.assertIn("budget = [0, 0] if fast_widget else [4, 1]",s)
        self.assertIn("if view in ('play',",s) if "if view in ('play'," in s else self.assertIn("if view == 'play':",s)
        self.assertIn('external.trakt.public_list',s)
        self.assertIn('external.tmdb.details',s)
        self.assertIn('time.time() - 86400',s)

    def test_new_episode_detection_invalidates_widgets_only_for_real_changes(self):
        from contextlib import nullcontext
        series_source=get_member('plugin.video.xstream-pro',
                                 'resources/lib/series_changes.py')
        gui=_FakeGui()
        events=[]
        state={'events':[],'catalog_ids':['series-42'],
               'episode_inventory':{
                   'series-42':{'complete':True,'episodes':[{'provider_id':'101'}]}},
               'episode_ids':{'series-42':['101']}}
        fake_series=types.ModuleType('series_state')
        fake_series.normalize_inventory=lambda episodes: (
            [{'provider_id':str(r['id']),'season':1,'episode':i+1}
             for i,r in enumerate(episodes.get('1',[]))],True)
        fake_series.inventory_diagnostics=lambda ep:{}
        dummy_vfs=types.ModuleType('xbmcvfs')
        dummy_gui=types.ModuleType('xbmcgui')
        dummy_gui.Window=gui.Window
        with patch.dict(sys.modules,{'series_state':fake_series,
                                     'xbmcvfs':dummy_vfs,'xbmcgui':dummy_gui}):
            env={}
            exec(series_source,env)
            env['_profile_lock']=lambda addon,num:nullcontext()
            env['_read']=lambda addon,num:state
            env['_write']=lambda addon,num, data:events.append('saved')
            env['_scope_provider']=lambda *args:False
            env['series_state']=fake_series
            env['_provider_date']=lambda value,now:now if value else 0
            args={'addon':object(),'profile_num':1,'series_id':'series-42',
                  'title':'Redacted','provider':None}
            valid={'info':{},'episodes':{'1':[{'id':'101','added':None},
                                             {'id':'102','added':int(time.time())}]}}
            result=env['record_series_info'](args['addon'],args['profile_num'],
                args['series_id'],args['title'],valid,provider=args['provider'])
            self.assertTrue(result)
            self.assertEqual(events,['saved'])
            self.assertIn('Premium.CollectionsRefresh',gui.properties)
            previous_stamp=gui.properties['Premium.CollectionsRefresh']
            # Same complete inventory is not a new episode; must not cause
            # repeated Home widget refresh loops when visiting the detail.
            self.assertTrue(env['record_series_info'](
                args['addon'],args['profile_num'],args['series_id'],args['title'],
                valid,provider=args['provider']))
            self.assertEqual(gui.properties['Premium.CollectionsRefresh'],
                             previous_stamp)
            invalid={'info':{},'episodes':None}
            self.assertFalse(env['record_series_info'](
                args['addon'],args['profile_num'],args['series_id'],args['title'],
                invalid,provider=args['provider']))
            self.assertEqual(gui.properties['Premium.CollectionsRefresh'],
                             previous_stamp)

    def test_old_package_history_unmodified_and_only_allowlisted_changes(self):
        for addon,old_version,new_version in (
            ('skin.actweeter','1.2.41~beta3','1.2.41~beta4'),
            ('plugin.video.xstream-pro','1.1.2.40~beta1','1.1.2.40~beta2')):
            old=REPO/addon/f'{addon}-{old_version}.zip'
            new=REPO/addon/f'{addon}-{new_version}.zip'
            with zipfile.ZipFile(old) as za,zipfile.ZipFile(new) as zb:
                before={n:za.read(n) for n in za.namelist() if not n.endswith('/')}
                after={n:zb.read(n) for n in zb.namelist() if not n.endswith('/')}
                changed={name for name,b in after.items() if before.get(name)!=b}
                allowed={f'{addon}/{name}' for name in self.builder.SPEC[addon]['members']}
                allowed|={f'{addon}/addon.xml',f'{addon}/changelog-{new_version}.txt'}
                self.assertEqual(changed,allowed)
                self.assertEqual(set(before)-set(after),set())
                self.assertIsNone(zb.testzip())
                self.assertEqual(hashlib.sha256(old.read_bytes()).hexdigest(),
                                 self.builder.SPEC[addon]['sha256'])

    def test_reproducible_builder_and_live_index_only_new_versions(self):
        with tempfile.TemporaryDirectory() as td:
            res=self.builder.build(Path(td))
            for addon,meta in res.items():
                self.assertEqual(
                    (Path(td)/f'{addon}-{meta["version"]}.zip').read_bytes(),
                    (REPO/addon/f'{addon}-{meta["version"]}.zip').read_bytes())
            with self.assertRaises(FileExistsError):
                self.builder.build(Path(td))
        vals={x.get('id'):x.get('version') for x in
              ET.parse(REPO/'addons.xml').getroot()}
        self.assertEqual(vals['skin.actweeter'],'1.2.41~beta5')
        self.assertEqual(vals['plugin.video.xstream-pro'],'1.1.2.44~beta7')
        self.assertEqual(vals['service.actweeter'],'0.4.101~beta1')
        stable={x.get('id'):x.get('version') for x in
                ET.parse(ROOT/'repo/addons.xml').getroot()}
        self.assertEqual(stable['skin.actweeter'],'1.2.41')
        self.assertEqual(stable['plugin.video.xstream-pro'],'1.1.2.45')


if __name__=='__main__':
    unittest.main()
