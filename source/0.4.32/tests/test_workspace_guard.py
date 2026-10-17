"""Checks for the read-only repository identity guard."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'tools'))
import workspace_guard

class WorkspaceGuardTests(unittest.TestCase):
    def test_clean_official(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            with patch.object(workspace_guard, 'git', side_effect=[str(root), workspace_guard.OFFICIAL, 'codex/beta', '', 'abc123']):
                self.assertEqual(workspace_guard.inspect(root, True, 'codex/beta')['dirty'], 'false')

    def test_reject_wrong_origin(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            with patch.object(workspace_guard, 'git', side_effect=[str(root), '/private/tmp/old']):
                with self.assertRaisesRegex(ValueError, 'Unexpected origin'):
                    workspace_guard.inspect(root)

    def test_reject_dirty(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            with patch.object(workspace_guard, 'git', side_effect=[str(root), workspace_guard.OFFICIAL, 'main', ' M foo']):
                with self.assertRaisesRegex(ValueError, 'uncommitted'):
                    workspace_guard.inspect(root, True)

    def test_reject_wrong_branch(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            with patch.object(workspace_guard, 'git', side_effect=[str(root), workspace_guard.OFFICIAL, 'main']):
                with self.assertRaisesRegex(ValueError, 'Expected'):
                    workspace_guard.inspect(root, require_branch='codex/beta')
