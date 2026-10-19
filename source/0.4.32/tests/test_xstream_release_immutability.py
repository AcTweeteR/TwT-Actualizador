"""Do not republish changed XStream payload under an existing version."""
import json
import hashlib
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

    def test_existing_different_version_is_never_overwritten(self):
        data=json.loads(build_xstream_package.MANIFEST.read_text())
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); upstream=root/'upstream.zip';upstream.write_bytes(b'fixture')
            output=root/'candidate.zip'
            with zipfile.ZipFile(output,'w') as z:
                z.writestr('plugin.video.xstream-pro/addon.xml','<addon version="0.0.1"/>')
            before=hashlib.sha256(output.read_bytes()).hexdigest()
            with patch.object(build_xstream_package,'sha256',return_value=data['upstream_release_zip_sha256']):
                with self.assertRaisesRegex(ValueError,'refusing to overwrite'):
                    build_xstream_package.build(upstream,output)
            self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(),before)

    def test_existing_symlink_is_never_followed(self):
        data=json.loads(build_xstream_package.MANIFEST.read_text())
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);upstream=root/'upstream.zip';upstream.write_bytes(b'fixture')
            original=root/'original.zip';original.write_bytes(b'preserve')
            output=root/'candidate.zip';output.symlink_to(original)
            with patch.object(build_xstream_package,'sha256',return_value=data['upstream_release_zip_sha256']):
                with self.assertRaisesRegex(ValueError,'refusing to overwrite'):
                    build_xstream_package.build(upstream,output)
            self.assertEqual(original.read_bytes(),b'preserve')

    def test_invalid_candidate_does_not_publish_or_leave_temp_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);candidate=root/'staged.zip';output=root/'published.zip'
            source=root/'payload';source.mkdir();(source/'addon.xml').write_text('<addon/>')
            with patch.object(build_xstream_package,'validate_python_archive',return_value=0):
                with self.assertRaisesRegex(ValueError,'patched runtime file missing'):
                    build_xstream_package._write_validate_publish(
                        source,candidate,output,{'local_runtime_sha256':{'missing.py':'abc'}},'upstream')
            self.assertFalse(output.exists())

    def test_atomic_publish_rejects_race_without_clobber(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);candidate=root/'candidate.zip';output=root/'published.zip'
            candidate.write_bytes(b'new');output.write_bytes(b'existing')
            with self.assertRaises(FileExistsError):
                build_xstream_package.os.link(candidate,output,follow_symlinks=False)
            self.assertEqual(output.read_bytes(),b'existing')

    def test_duplicate_upstream_entries_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);upstream=root/'upstream.zip';output=root/'out.zip'
            with zipfile.ZipFile(upstream,'w') as z:
                z.writestr('plugin.video.xstream-pro/addon.xml','<addon/>')
                z.writestr('plugin.video.xstream-pro/addon.xml','<addon/>')
            digest=hashlib.sha256(upstream.read_bytes()).hexdigest()
            data=json.loads(build_xstream_package.MANIFEST.read_text())
            data['upstream_release_zip_sha256']=digest
            with patch.object(build_xstream_package,'MANIFEST',root/'manifest.json'):
                (root/'manifest.json').write_text(json.dumps(data))
                with self.assertRaisesRegex(ValueError,'unexpected XStream ZIP paths'):
                    build_xstream_package.build(upstream,output)
            self.assertFalse(output.exists())

    def test_foreign_upstream_entries_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);upstream=root/'upstream.zip';output=root/'out.zip'
            with zipfile.ZipFile(upstream,'w') as z:
                z.writestr('plugin.video.xstream-pro/addon.xml','<addon/>')
                z.writestr('unrelated/payload','foreign')
            data=json.loads(build_xstream_package.MANIFEST.read_text())
            data['upstream_release_zip_sha256']=hashlib.sha256(upstream.read_bytes()).hexdigest()
            with patch.object(build_xstream_package,'MANIFEST',root/'manifest.json'):
                (root/'manifest.json').write_text(json.dumps(data))
                with self.assertRaisesRegex(ValueError,'unexpected XStream ZIP paths'):
                    build_xstream_package.build(upstream,output)
            self.assertFalse(output.exists())

    def test_historical_zip_remains_unchanged(self):
        import hashlib
        old=ROOT.parents[1]/'docs/testing/repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.8.zip'
        self.assertEqual(hashlib.sha256(old.read_bytes()).hexdigest(),
                         'f1a305719b8b8bc5e5e0b99c66331af5ad153fdd15829b25947ba1fe97ad9382')
