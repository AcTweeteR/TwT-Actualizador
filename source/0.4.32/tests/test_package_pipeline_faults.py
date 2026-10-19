"""Fault injection across package builders and index validation."""
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
from package_safety import publish_zip
from build_distribution_index import addon_from_zip


class PackagePipelineFaults(unittest.TestCase):
    def test_payload_failure_leaves_no_package_or_staging(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'source'
            source.mkdir()
            (source / 'addon.xml').write_text('<addon id="test.addon" version="1.0"/>')
            (source / 'broken.txt').write_text('broken')
            def failing_payload(path):
                if path.name == 'broken.txt':
                    raise OSError('simulated read failure')
                return path.read_bytes()
            with self.assertRaisesRegex(OSError, 'simulated read failure'):
                publish_zip(source, root / 'out.zip', 'test.addon', '1.0',
                            (2026, 10, 3, 0, 0, 0), failing_payload)
            self.assertFalse((root / 'out.zip').exists())
            self.assertFalse(list(root.glob('.actweeter-package-*')))

    def test_wrong_embedded_identity_is_not_published(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'source'
            source.mkdir()
            (source / 'addon.xml').write_text('<addon id="other" version="1.0"/>')
            with self.assertRaisesRegex(ValueError, 'identity mismatch'):
                publish_zip(source, root / 'out.zip', 'test.addon', '1.0',
                            (2026, 10, 3, 0, 0, 0), lambda path: path.read_bytes())
            self.assertFalse((root / 'out.zip').exists())
            self.assertFalse(list(root.glob('.actweeter-package-*')))

    def test_source_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'source'
            source.mkdir()
            (source / 'addon.xml').write_text('<addon id="test.addon" version="1.0"/>')
            (source / 'external').symlink_to(root)
            with self.assertRaisesRegex(ValueError, 'symlink'):
                publish_zip(source, root / 'out.zip', 'test.addon', '1.0',
                            (2026, 10, 3, 0, 0, 0), lambda path: path.read_bytes())
            self.assertFalse((root / 'out.zip').exists())

    def test_index_rejects_windows_traversal_and_duplicates(self):
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / 'test.zip'
            for member in ('test.addon/..\\outside', 'test.addon/./inside'):
                with zipfile.ZipFile(package, 'w') as archive:
                    archive.writestr('test.addon/addon.xml',
                                     '<addon id="test.addon" version="1.0"/>')
                    archive.writestr(member, 'unexpected')
                with self.assertRaisesRegex(ValueError, 'unsafe'):
                    addon_from_zip(package, 'test.addon', '1.0')

    def test_index_rejects_symlink_member(self):
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / 'test.zip'
            with zipfile.ZipFile(package, 'w') as archive:
                archive.writestr('test.addon/addon.xml',
                                 '<addon id="test.addon" version="1.0"/>')
                info = zipfile.ZipInfo('test.addon/escape')
                info.create_system = 3
                info.external_attr = (0o120777 << 16)
                archive.writestr(info, '../outside')
            with self.assertRaisesRegex(ValueError, 'unsafe'):
                addon_from_zip(package, 'test.addon', '1.0')


if __name__ == '__main__':
    unittest.main()

class DistributionIndexPublicationFaults(unittest.TestCase):
    def test_existing_destination_preserved(self):
        from build_distribution_index import build
        from unittest.mock import patch
        from xml.etree import ElementTree as ET
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / 'index'
            destination.mkdir()
            marker = destination / 'keep.txt'
            marker.write_text('original')
            def fake_addon(path, addon_id, version):
                addon = ET.Element('addon', id=addon_id, version=version)
                ET.SubElement(addon, 'extension', point='xbmc.addon.metadata')
                return addon
            with patch('build_distribution_index.addon_from_zip', side_effect=fake_addon):
                with self.assertRaisesRegex(ValueError, 'overwrite'):
                    build(None, None, None, None, destination)
            self.assertEqual(marker.read_text(), 'original')
            self.assertFalse(list(Path(temp).glob('.actweeter-index-*')))

class PackageSourceEntryFaults(unittest.TestCase):
    def test_source_root_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            real = root / 'real'
            real.mkdir()
            (real / 'addon.xml').write_text('<addon id="test.addon" version="1.0"/>')
            alias = root / 'alias'
            alias.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'real directory'):
                publish_zip(alias, root / 'out.zip', 'test.addon', '1.0',
                            (2026, 10, 3, 0, 0, 0), lambda p: p.read_bytes())
            self.assertFalse((root / 'out.zip').exists())

    def test_source_fifo_is_rejected_without_opening_it(self):
        import os
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'source'
            source.mkdir()
            (source / 'addon.xml').write_text('<addon id="test.addon" version="1.0"/>')
            os.mkfifo(source / 'fifo')
            with self.assertRaisesRegex(ValueError, 'non-regular'):
                publish_zip(source, root / 'out.zip', 'test.addon', '1.0',
                            (2026, 10, 3, 0, 0, 0), lambda p: p.read_bytes())
            self.assertFalse((root / 'out.zip').exists())

    def test_mid_write_exception_cleans_staging(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'source'
            source.mkdir()
            manifest = source / 'addon.xml'
            manifest.write_text('<addon id="test.addon" version="1.0"/>')
            with patch('package_safety.zipfile.ZipInfo', side_effect=OSError('injected packaging fault')):
                with self.assertRaisesRegex(OSError, 'injected'):
                    publish_zip(source, root / 'out.zip', 'test.addon', '1.0',
                                (2026, 10, 3, 0, 0, 0), lambda path: path.read_bytes())
            self.assertFalse((root / 'out.zip').exists())
            self.assertFalse(list(root.glob('.actweeter-package-*')))

    def test_source_file_becomes_symlink_before_read(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'source'
            source.mkdir()
            manifest = source / 'addon.xml'
            manifest.write_text('<addon id="test.addon" version="1.0"/>')
            original = Path.is_symlink
            def changed(self):
                if self == manifest and not changed.done:
                    changed.done = True
                    return False
                if self == manifest and changed.done:
                    return True
                return original(self)
            changed.done = False
            # Inventory sees an ordinary file; pre-write guard sees a symlink.
            with patch.object(Path, 'is_symlink', changed):
                with self.assertRaisesRegex(ValueError, 'source changed'):
                    publish_zip(source, root / 'out.zip', 'test.addon', '1.0',
                                (2026, 10, 3, 0, 0, 0), lambda p: p.read_bytes())
            self.assertFalse((root / 'out.zip').exists())
            self.assertFalse(list(root.glob('.actweeter-package-*')))
