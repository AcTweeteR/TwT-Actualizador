import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
p=Path(__file__).resolve().parents[1]/'addons/service.actweeter/resources/lib'
sys.path.insert(0,str(p))
spec=importlib.util.spec_from_file_location('collections_ui_test_impl',p/'collections_ui.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class UiTests(unittest.TestCase):
 def test_create_and_reopen_without_remote_write(self):
  with tempfile.TemporaryDirectory() as directory:
   calls=[]
   addon=types.SimpleNamespace(getAddonInfo=lambda _:directory)
   vfs=types.SimpleNamespace(translatePath=lambda path:path)
   class Item:
    def __init__(self,label):self.label=label
    def setArt(self,art):pass
    def addContextMenuItems(self,items):pass
   gui=types.SimpleNamespace(ListItem=Item)
   plugin=types.SimpleNamespace(setPluginCategory=lambda x,y:None,setContent=lambda x,y:None,
    addDirectoryItem=lambda handle,url,item,folder:calls.append((url,item.label)),
    endOfDirectory=lambda *args,**kwargs:None)
   dialog=types.SimpleNamespace(input=lambda _: 'Science Fiction',ok=lambda *args:None)
   m.render(1,addon=addon,vfs=vfs,gui=gui,plugin=plugin,params={'action':['collection_create']},dialog=dialog)
   self.assertEqual(len(calls),2)
   self.assertEqual(calls[1][1],'Science Fiction')
   calls.clear()
   m.render(1,addon=addon,vfs=vfs,gui=gui,plugin=plugin,params={'action':['collections']},dialog=dialog)
   self.assertEqual(calls[1][1],'Science Fiction')
   self.assertTrue(os.path.exists(os.path.join(directory,'collections_catalog.db')))
 def test_rename_preserves_collection_id(self):
  with tempfile.TemporaryDirectory() as directory:
   from collection_catalog import Catalog
   db=Catalog(os.path.join(directory,'collections_catalog.db'))
   identifier=db.create_local('Old',origin='mis_colecciones')
   addon=types.SimpleNamespace(getAddonInfo=lambda _:directory)
   vfs=types.SimpleNamespace(translatePath=lambda value:value)
   class Item:
    def __init__(self,label):self.label=label
    def setArt(self,art):pass
    def addContextMenuItems(self,items):pass
   gui=types.SimpleNamespace(ListItem=Item)
   plugin=types.SimpleNamespace(setPluginCategory=lambda *args:None,setContent=lambda *args:None,
    addDirectoryItem=lambda *args:None,endOfDirectory=lambda *args,**kwargs:None)
   dialog=types.SimpleNamespace(input=lambda *args,**kwargs:'New',ok=lambda *args:None)
   m.render(1,addon=addon,vfs=vfs,gui=gui,plugin=plugin,
    params={'action':['collection_rename'],'id':[identifier]},dialog=dialog)
   self.assertEqual(db.get(identifier)['name'],'New')
 def test_unknown_action_rejected(self):
  with self.assertRaises(ValueError):m.render(1,addon=None,vfs=None,gui=None,plugin=None,params={'action':['delete_all']},dialog=None)
