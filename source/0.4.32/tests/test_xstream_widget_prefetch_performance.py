"""Deterministic warm/cold widget prefetch contract without live IPTV credentials."""
import ast
import json
import types
import unittest
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BUNDLED=ROOT.parents[1] / "docs/testing/repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.10.zip"


def load_prefetch():
    """Compile just the function from the reviewed tracked patch applied to pinned 1.1.2.10 code."""
    import importlib.util
    from tempfile import TemporaryDirectory
    spec=importlib.util.spec_from_file_location(
        "pinned_xstream_builder", ROOT/"tools/build_xstream_package.py")
    builder=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    with zipfile.ZipFile(BUNDLED) as archive:
        original=archive.read("plugin.video.xstream-pro/resources/lib/addon.py")
    with TemporaryDirectory() as temp:
        source=Path(temp)/"resources/lib/addon.py"
        source.parent.mkdir(parents=True)
        source.write_bytes(original)
        builder.apply_contextual_unified_patch(
            Path(temp),
            ROOT/"third_party/xstream/patches/1.1.2/actweeter-widget-prefetch.patch")
        tree=ast.parse(source.read_bytes())
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef)
                  and n.name=="_prefetch_vod_info_batch")
    return compile(ast.Module(body=[function],type_ignores=[]),"<prefetch>",'exec')


class _SyncThread:
    started=[]
    def __init__(self,target,args=()):
        self.target=target
        self.args=args
    def start(self):
        self.__class__.started.append(self.args[0].get('stream_id'))
        self.target(*self.args)
    def join(self,timeout=None):
        pass


class PrefetchTests(unittest.TestCase):
    def run_case(self,cached_ids,enabled=True,count=20):
        calls=[];sleeps=[];saved=[]
        _SyncThread.started=[]
        records=[{'stream_id':str(i),'name':'title'} for i in range(count)]
        store={'vod_info_'+str(i):{'info':{'plot':'cached'}} for i in cached_ids}
        settings=types.SimpleNamespace(getSetting=lambda name:'true' if enabled else 'false')
        def load(name):
            calls.append(name)
            return store.get(name)
        def save(name, value):
            saved.append(name)
            store[name]=value
        env={
            'addon':settings, 'pm':types.SimpleNamespace(active='1'),
            '_cache_load':load,'_cache_save':save,
            'threading':types.SimpleNamespace(Thread=_SyncThread),
            'xbmc':types.SimpleNamespace(sleep=lambda ms:sleeps.append(ms)),
            'IPTV':types.SimpleNamespace(
                get_vod_info=lambda host,user,pwd,sid:{'info':{'plot':'provider'}}),
            '_log':lambda *args:None,
            'time':__import__('time'),
        }
        exec(load_prefetch(),env)
        env['_prefetch_vod_info_batch'](records,'unused-host','user','password')
        return calls,sleeps,saved,list(_SyncThread.started)

    def test_complete_warm_cache_creates_no_threads_and_no_sleep(self):
        calls,sleeps,saved,threads=self.run_case(range(20))
        self.assertEqual(len(calls),20)
        self.assertEqual(sleeps,[])
        self.assertEqual(saved,[])
        self.assertEqual(threads,[])

    def test_metadata_disabled_does_not_load_or_prefetch(self):
        calls,sleeps,saved,threads=self.run_case([],enabled=False)
        self.assertEqual((calls,sleeps,saved,threads),([],[],[],[]))

    def test_single_missing_entry_preserves_provider_fetch_without_batch_delay(self):
        calls,sleeps,saved,threads=self.run_case(range(19))
        self.assertEqual(threads,['19'])
        self.assertEqual(saved,['vod_info_19'])
        self.assertEqual(sleeps,[])

    def test_more_than_one_batch_throttles_only_missing_entries(self):
        calls,sleeps,saved,threads=self.run_case(range(15))
        self.assertEqual(threads,['15','16','17','18','19'])
        self.assertEqual(len(saved),5)
        self.assertEqual(sleeps,[200])


if __name__=="__main__":
    unittest.main()
