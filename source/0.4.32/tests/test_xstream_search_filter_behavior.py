"""Exercise the exact packaged provider filter-stamp function without Kodi."""
import ast
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
PATCH=ROOT/'third_party/xstream/patches/1.1.2/actweeter-runtime.patch'


def filter_stamp_function():
    text=PATCH.read_text()
    start=text.index('+++ b/resources/lib/premium_routes.py')
    end=text.find('diff --git ',start+10)
    hunk=text[text.index('@@ ',start):end if end!=-1 else len(text)]
    source='\n'.join(line[1:] for line in hunk.splitlines()[1:]
                     if line.startswith('+') and not line.startswith('+++'))
    tree=ast.parse(source)
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_search_filter_stamp')
    namespace={}
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(PATCH),'exec'),namespace)
    return namespace['_search_filter_stamp']


class SearchFilterBehaviorTests(unittest.TestCase):
    def test_settings_failure_must_not_represent_empty_filters(self):
        fn=filter_stamp_function()
        def failure(*args):raise RuntimeError('filter storage unavailable')
        g={'addon':SimpleNamespace(getSetting=lambda key:'false'),
           '_get_hidden_subcats':failure,'_get_hidden_items':lambda *args:[]}
        with self.assertRaisesRegex(RuntimeError,'filter storage unavailable'):
            fn(g,1)

    def test_distinct_filter_selections_produce_distinct_stamps(self):
        fn=filter_stamp_function()
        def make(hidden):
            return {'addon':SimpleNamespace(getSetting=lambda key:'false'),
                    '_get_hidden_subcats':lambda stype,pnum:hidden,
                    '_get_hidden_items':lambda stype,pnum:[]}
        self.assertNotEqual(fn(make([]),1),fn(make(['adult']),1))
        self.assertEqual(fn(make(['a','b']),1),fn(make(['b','a']),1))
