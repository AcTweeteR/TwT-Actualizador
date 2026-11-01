import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/service.actweeter/resources'))
from lib import trakt_restore_plan as restore


class RestorePlanTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.staged = [self.root / ('new%d' % i) for i in range(3)]
        self.active = [self.root / ('old%d' % i) for i in range(3)]
        for index, path in enumerate(self.staged + self.active):
            path.write_text(json.dumps({'value': index}))
        self.hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in self.active]
        self.plan = self.root / 'plan'
        self.backup = self.root / 'backup'

    def prepare(self, **kwargs):
        options = dict(staged=self.staged, active=self.active, expected_active_sha256=self.hashes,
                       account='synthetic', profile='1', confirmed=True)
        options.update(kwargs)
        return restore.prepare(self.plan, **options)

    def apply(self, **kwargs):
        options = dict(active=self.active, backup_directory=self.backup, account='synthetic',
                       profile='1', kodi_stopped=True)
        options.update(kwargs)
        return restore.apply(self.plan, **options)

    def test_confirmed_plan_survives_restart_but_cannot_commit(self):
        self.prepare()
        self.assertTrue(self.plan.is_dir())
        with self.assertRaises(PermissionError):
            self.apply(kodi_stopped=False)
        self.assertFalse(self.backup.exists())
        with patch.object(restore, 'commit_staged_restore') as commit:
            with self.assertRaisesRegex(PermissionError, 'application disabled'):
                self.apply()
            commit.assert_not_called()
        self.assertEqual(json.loads(self.active[0].read_text()), {'value': 3})
        self.assertFalse(self.backup.exists())

    def test_preview_requires_confirmation_and_unchanged_active_stores(self):
        with self.assertRaises(PermissionError):
            self.prepare(confirmed=False)
        self.active[0].write_text('{"newer": true}')
        with self.assertRaisesRegex(RuntimeError, 'during preview'):
            self.prepare()
        self.assertFalse(self.plan.exists())

    def test_change_while_staging_is_rejected(self):
        copy = restore.shutil.copyfileobj
        def change_after_copy(reader, writer):
            copy(reader, writer)
            self.active[0].write_text('{"newer": true}')
        with patch.object(restore.shutil, 'copyfileobj', side_effect=change_after_copy):
            with self.assertRaisesRegex(RuntimeError, 'while staging'):
                self.prepare()
        self.assertFalse(self.plan.exists())
        self.assertFalse(self.backup.exists())

    def test_refuses_changed_active_staged_account_and_targets(self):
        self.prepare()
        with self.assertRaises(PermissionError):
            self.apply(account='different')
        with self.assertRaises(ValueError):
            self.apply(active=list(reversed(self.active)))
        self.active[0].write_text('{"newer": true}')
        with self.assertRaisesRegex(RuntimeError, 'after preview'):
            self.apply()
        self.active[0].write_text(json.dumps({'value': 3}))
        (self.plan / 'staged_0.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'staged restore changed'):
            self.apply()
        self.assertFalse(self.backup.exists())
