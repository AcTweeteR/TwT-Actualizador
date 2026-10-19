"""Do not republish changed XStream payload under an existing version."""
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_xstream_package


class XStreamReleaseImmutabilityTests(unittest.TestCase):
    def test_same_version_output_is_rejected_before_build(self):
        data=json.loads(build_xstream_package.MANIFEST.read_text())
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            upstream=root/'upstream.zip'
            upstream.write_bytes(b'upstream fixture')
            output=root/'candidate.zip'
            with zipfile.ZipFile(output,'w') as z:
                z.writestr('plugin.video.xstream-pro/addon.xml',
                           '<addon version="'+data['distribution_version']+'"/>')
            with patch.object(build_xstream_package,'sha256',return_value=data['upstream_release_zip_sha256']):
                with self.assertRaisesRegex(ValueError,'refusing to overwrite'):
                    build_xstream_package.build(upstream,output)

    def test_historical_zip_remains_unchanged(self):
        import hashlib
        old=ROOT.parents[1]/'docs/testing/repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.8.zip'
        self.assertEqual(hashlib.sha256(old.read_bytes()).hexdigest(),
                         'f1a305719b8b8bc5e5e0b99c66331af5ad153fdd15829b25947ba1fe97ad9382')
