"""Provider patch integrity and defensive snapshot guard contracts."""
import ast
import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PATCH=ROOT/'third_party/xstream/patches/1.1.2/actweeter-runtime.patch'
MANIFEST=ROOT/'third_party/xstream/upstream.json'


class XStreamIndexGuardTests(unittest.TestCase):
    def test_patch_hunk_and_manifest_integrity(self):
        patch=PATCH.read_bytes()
        manifest=json.loads(MANIFEST.read_text())
        self.assertEqual(hashlib.sha256(patch).hexdigest(),manifest['patch_sha256'])
        start=patch.index(b'+++ b/resources/lib/premium_routes.py')
        header=patch[patch.index(b'@@ ',start):].splitlines()[0]
        count=int(re.search(rb'\+1,(\d+)',header).group(1))
        end=patch.find(b'diff --git ',start+10)
        hunk=patch[patch.index(b'@@ ',start):end if end!=-1 else len(patch)]
        self.assertEqual(count,sum(line.startswith(b'+') and not line.startswith(b'+++') for line in hunk.splitlines()))

    def test_search_guards_cover_all_provider_snapshot_failure_paths(self):
        patch=PATCH.read_bytes()
        start=patch.index(b'+++ b/resources/lib/premium_routes.py')
        end=patch.find(b'diff --git ',start+10)
        text=patch[start:end if end!=-1 else len(patch)].decode()
        self.assertIn('if old_ids and not rows:',text)
        self.assertNotIn('if old_ids and not rows and saved_filters == filter_stamp:',text)
        self.assertIn('if not isinstance(item, dict):',text)
        self.assertIn("raise ValueError('invalid provider search item')",text)
        self.assertIn('if os.path.islink(path) or (os.path.exists(path) and not os.path.isfile(path)):',text)

    def test_filter_failures_and_query_symlinks_fail_closed(self):
        patch=PATCH.read_text()
        self.assertNotIn('+        except Exception:\n+            return ()',patch)
        self.assertIn("+                if os.path.islink(path):",patch)
        self.assertIn("+                    raise ValueError('unsafe provider search index path')",patch)

    def test_patched_provider_function_is_syntactically_valid(self):
        patch=PATCH.read_bytes()
        start=patch.index(b'+++ b/resources/lib/premium_routes.py')
        end=patch.find(b'diff --git ',start+10)
        hunk=patch[patch.index(b'@@ ',start):end if end!=-1 else len(patch)]
        source='\n'.join(line[1:].decode() for line in hunk.splitlines()[1:]
                         if line.startswith(b'+') and not line.startswith(b'+++'))
        ast.parse(source)
