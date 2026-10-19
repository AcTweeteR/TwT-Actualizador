"""Release builder end-to-end safety checks, never publishing to Stable."""
import hashlib
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / 'tools/build_repository_package.py'


class RepositoryPackageSafetyTests(unittest.TestCase):
    def run_builder(self, destination):
        return subprocess.run([sys.executable, str(BUILDER), '--output', str(destination)],
                              capture_output=True, text=True)

    def test_valid_package_reproducible_and_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / 'one.zip'
            second = Path(tmp) / 'two.zip'
            self.assertEqual(self.run_builder(first).returncode, 0)
            self.assertEqual(self.run_builder(second).returncode, 0)
            self.assertEqual(hashlib.sha256(first.read_bytes()).digest(),
                             hashlib.sha256(second.read_bytes()).digest())
            with zipfile.ZipFile(first) as archive:
                self.assertIsNone(archive.testzip())
                self.assertIn('repository.actweeter/addon.xml', archive.namelist())

    def test_existing_package_is_never_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / 'existing.zip'
            destination.write_bytes(b'preserve')
            result = self.run_builder(destination)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(destination.read_bytes(), b'preserve')
            self.assertFalse(list(Path(tmp).glob('.repository-actweeter-*')))

    def test_symlink_destination_is_never_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / 'original.zip'
            original.write_bytes(b'preserve')
            destination = root / 'linked.zip'
            destination.symlink_to(original)
            self.assertNotEqual(self.run_builder(destination).returncode, 0)
            self.assertEqual(original.read_bytes(), b'preserve')


if __name__ == '__main__':
    unittest.main()
