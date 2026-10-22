"""Exercise the tracked OAuth patch with synthetic responses, never real tokens."""
import ast
import importlib.util
from pathlib import Path
import tempfile
import types
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]


class TraktDeviceAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('trakt_patch_builder', ROOT / 'tools/build_xstream_package.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            with zipfile.ZipFile(REPO / 'docs/testing/repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.19.zip') as archive:
                for name in ('trakt.py', 'tmdb_routes.py'):
                    path = base / 'resources/lib' / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(archive.read('plugin.video.xstream-pro/resources/lib/' + name).replace(b'\r\n', b'\n'))
            builder.apply_contextual_unified_patch(base,
                ROOT / 'third_party/xstream/patches/1.1.2/actweeter-trakt-device-auth.patch')
            tree = ast.parse((base / 'resources/lib/trakt.py').read_bytes())
            names = ('auth_configured', 'device_code', 'poll_device_token', 'refresh_token')
            cls.code = compile(ast.Module(body=[node for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name in names], type_ignores=[]), 'patched_trakt.py', 'exec')
            cls.routes = (base / 'resources/lib/tmdb_routes.py').read_text()

    def setUp(self):
        self.calls, self.saved = [], []
        self.payload = {'access_token': 'synthetic-access', 'refresh_token': 'synthetic-refresh'}
        self.status = 200
        def request(method, url, **kwargs):
            self.calls.append((method, url, kwargs))
            return types.SimpleNamespace(status_code=self.status, json=lambda: self.payload)
        def raise_error(*_): raise RuntimeError('synthetic error')
        self.env = {'client_id': lambda: 'synthetic-public-app',
                    'client_secret': lambda: self.fail('desktop must not read a client secret'),
                    '_http_request': request, '_headers': lambda _: {},
                    '_read_tokens': lambda: {'refresh_token': 'synthetic-refresh'},
                    '_write_tokens': self.saved.append, '_raise_trakt_error': raise_error,
                    'clear_tokens': lambda: self.fail('unexpected credential change'),
                    '_log': lambda *args: None, 'xbmc': types.SimpleNamespace(LOGWARNING=1)}
        exec(self.code, self.env)

    def test_public_app_id_is_sufficient_no_secret_access(self):
        self.assertTrue(self.env['auth_configured']())
        self.env['client_id'] = lambda: ''
        self.assertFalse(self.env['auth_configured']())

    def test_device_code_uses_official_auth_host(self):
        self.env['device_code']()
        method, url, kwargs = self.calls[0]
        self.assertEqual(method, 'POST')
        self.assertEqual(url, 'https://auth.trakt.tv/oauth/device/code')
        self.assertEqual(kwargs['json'], {'client_id': 'synthetic-public-app'})

    def test_device_poll_saves_in_native_xstream_store_only(self):
        self.env['poll_device_token']('synthetic-device-code')
        self.assertEqual(self.calls[0][1], 'https://auth.trakt.tv/oauth/device/token')
        self.assertNotIn('client_secret', self.calls[0][2]['json'])
        self.assertEqual(self.saved, [self.payload])

    def test_pending_does_not_persist_credentials(self):
        self.status = 400
        self.assertIsNone(self.env['poll_device_token']('synthetic-device-code'))
        self.assertFalse(self.saved)

    def test_authorization_errors_do_not_persist_success(self):
        for status in (401, 404, 409, 410, 418, 429):
            self.status = status
            with self.assertRaises(RuntimeError): self.env['poll_device_token']('synthetic-device-code')
        self.assertFalse(self.saved)

    def test_refresh_uses_rotated_native_tokens_without_secret(self):
        self.assertTrue(self.env['refresh_token']())
        self.assertEqual(self.calls[0][1], 'https://auth.trakt.tv/oauth/token')
        self.assertNotIn('client_secret', self.calls[0][2]['json'])
        self.assertEqual(self.saved, [self.payload])

    def test_rate_limit_preserves_previous_native_tokens(self):
        self.status = 429
        with self.assertRaises(RuntimeError): self.env['refresh_token']()
        self.assertFalse(self.saved)

    def test_expired_tokens_with_no_refresh_do_not_make_requests(self):
        self.env['_read_tokens'] = lambda: {}
        self.assertFalse(self.env['refresh_token']())
        self.assertFalse(self.calls)

    def test_routes_no_longer_demand_desktop_secrets(self):
        self.assertNotIn('Add Trakt client secret for account features', self.routes)
        self.assertNotIn('requires a client ID and client secret in settings', self.routes)


class ProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('trakt_mac_probe', REPO / 'tools/probe_trakt_mac.py')
        cls.probe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.probe)

    def test_summary_never_exposes_titles_urls_or_account_details(self):
        rows = [{'label': 'Private title', 'file': 'plugin://synthetic/?mode=settings', 'type': 'movie'},
                {'file': 'plugin://synthetic/?mode=xstream_trakt_list&section=history'}]
        summary = self.probe.summarize(rows)
        self.assertEqual(summary['items'], 2)
        self.assertTrue(summary['account_configuration_offered'])
        self.assertTrue(summary['account_routes_present'])
        self.assertNotIn('Private', str(summary))
        self.assertNotIn('plugin://', str(summary))

    def test_write_methods_are_rejected_before_connecting(self):
        for method in ('Player.Open', 'Addons.ExecuteAddon', 'Settings.SetSettingValue', 'Input.ExecuteAction'):
            with self.assertRaises(ValueError): self.probe.rpc(9090, method)


if __name__ == '__main__':
    unittest.main()
