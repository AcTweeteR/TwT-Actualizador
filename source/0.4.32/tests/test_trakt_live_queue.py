import json
from pathlib import Path
import sys
import tempfile
import unittest

SERVICE_RESOURCES = (Path(__file__).resolve().parents[1] /
                     'addons/service.actweeter/resources')
sys.path.insert(0, str(SERVICE_RESOURCES))
sys.path.insert(0, str(SERVICE_RESOURCES / 'lib'))
from trakt_live_queue import (build_batch, checkpoint_from_ack,
                              persist_checkpoint, provider_fingerprint,
                              verify_batch, write_ack, write_batch)
from lib.trakt_live_sync import confirm_batch, dispatch_batch


class TraktLiveQueueTests(unittest.TestCase):
    def setUp(self):
        self.scope = provider_fingerprint('2', 'xtream', 'https://host.invalid:443',
                                          'user', '')
        self.item = {'identity': {'kind': 'movie', 'ids': {'tmdb': '7'}},
                     'provider_id': '71', 'watched': True, 'watched_at': 1000}
        self.plan = {'profile': '2', 'account': 'acct', 'items': [self.item]}

    def test_explicit_consent_and_scope_are_required(self):
        with self.assertRaises(PermissionError):
            build_batch(self.plan, provider_scope=self.scope)
        with self.assertRaises(ValueError):
            build_batch(self.plan, provider_scope='', consent=True)

    def test_provider_binding_never_depends_on_password(self):
        a = provider_fingerprint('2', 'xtream', 'https://host.invalid', 'user', '')
        b = provider_fingerprint('2', 'xtream', 'https://host.invalid', 'user', '')
        self.assertEqual(a, b)
        self.assertNotEqual(a, provider_fingerprint('3', 'xtream', 'https://host.invalid', 'user', ''))
        self.assertNotEqual(a, provider_fingerprint('2', 'xtream', 'https://other.invalid', 'user', ''))

    def test_batch_is_credential_free_atomic_and_scope_bound(self):
        batch = build_batch(self.plan, provider_scope=self.scope, consent=True,
                            batch_id='a' * 32)
        with tempfile.TemporaryDirectory() as directory:
            path = write_batch(Path(directory) / 'queue', batch)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            text = path.read_text()
            self.assertNotIn('password', text.casefold())
            verify_batch(json.loads(text), profile='2', account='acct',
                         provider_scope=self.scope)
            with self.assertRaises(PermissionError):
                verify_batch(json.loads(text), profile='2', account='other',
                             provider_scope=self.scope)

    def test_checkpoint_requires_all_confirmations_and_keeps_scope(self):
        batch = build_batch(self.plan, provider_scope=self.scope, consent=True,
                            batch_id='b' * 32)
        op_id = batch['operations'][0]['id']
        with tempfile.TemporaryDirectory() as directory:
            deferred = write_ack(Path(directory) / 'acks', batch,
                                 [{'id': op_id, 'status': 'deferred'}])
            with self.assertRaises(RuntimeError):
                checkpoint_from_ack(deferred, batch)
            ack = write_ack(Path(directory) / 'acks', batch,
                            [{'id': op_id, 'status': 'applied'}])
            checkpoint = checkpoint_from_ack(ack, batch)
            path = Path(directory) / 'state' / 'profile_2.json'
            persisted = persist_checkpoint(path, checkpoint)
            self.assertEqual(persisted['batches'][0]['batch_id'], batch['batch_id'])
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(PermissionError):
                persist_checkpoint(path, dict(checkpoint, account='other'))

    def test_malformed_acknowledgements_fail_closed(self):
        batch = build_batch(self.plan, provider_scope=self.scope, consent=True,
                            batch_id='d' * 32)
        op_id = batch['operations'][0]['id']
        with tempfile.TemporaryDirectory() as directory:
            for rows in ([None], [{'id': op_id, 'status': 'applied'},
                                  {'id': op_id, 'status': 'applied'}]):
                with self.assertRaises(ValueError):
                    write_ack(Path(directory) / 'acks', batch, rows)
            malformed = {'schema': 1, 'batch_id': batch['batch_id'],
                         'account': batch['account'], 'profile': batch['profile'],
                         'provider_scope': batch['provider_scope'], 'results': [None]}
            unsigned = json.dumps(malformed, sort_keys=True, separators=(',', ':'))
            import hashlib
            malformed['sha256'] = hashlib.sha256(unsigned.encode()).hexdigest()
            with self.assertRaises(RuntimeError):
                checkpoint_from_ack(malformed, batch)

    def test_native_dispatch_is_suppressed_during_playback_and_confirmation_persists(self):
        class Addon:
            def __init__(self, root): self.root = root
            def getAddonInfo(self, key): return self.root
        class VFS:
            translatePath = staticmethod(lambda value: value)
        class Kodi:
            calls = []
            def executebuiltin(self, command, wait): self.calls.append((command, wait))
        batch = build_batch(self.plan, provider_scope=self.scope, consent=True,
                            batch_id='c' * 32)
        with tempfile.TemporaryDirectory() as directory:
            service = Addon(directory)
            kodi = Kodi()
            self.assertEqual(dispatch_batch(kodi, service, VFS(), batch,
                                            player_active=True)['status'], 'deferred')
            self.assertEqual(kodi.calls, [])
            result = dispatch_batch(kodi, service, VFS(), batch)
            self.assertEqual(result['status'], 'dispatched')
            self.assertIn('RunPlugin(plugin://plugin.video.xstream-pro/', kodi.calls[0][0])
            ack_path = Path(directory) / 'trakt_live' / 'acks' / ('c' * 32 + '.json')
            row = {'id': batch['operations'][0]['id'], 'status': 'applied'}
            ack = write_ack(ack_path, batch, [row])
            self.assertIsNotNone(confirm_batch(service, VFS(), batch))


if __name__ == '__main__':
    unittest.main()
