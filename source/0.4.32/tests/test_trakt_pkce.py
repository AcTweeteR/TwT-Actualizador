import importlib.util
import pathlib
import unittest
from urllib.parse import urlsplit, parse_qs, urlencode

MODULE = pathlib.Path(__file__).resolve().parents[1] / 'third_party/xstream/trakt_pkce.py'
spec = importlib.util.spec_from_file_location('trakt_pkce', MODULE)
pkce = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pkce)

class PKCETests(unittest.TestCase):
    def test_s256_and_callback(self):
        session = pkce.begin('public-id', 'https://github.com/AcTweeteR/TwT-Actualizador')
        params = parse_qs(urlsplit(session['url']).query)
        self.assertEqual(params['code_challenge_method'], ['S256'])
        self.assertEqual(params['response_type'], ['code'])
        callback = session['redirect_uri'] + '?' + urlencode({'code': 'example', 'state': session['state']})
        result = pkce.exchange_payload('public-id', session, callback)
        self.assertEqual(result['code'], 'example')
        self.assertEqual(result['code_verifier'], session['verifier'])
        self.assertNotIn('client_secret', result)
    def test_rejects_forged_callbacks(self):
        session = pkce.begin('public-id', 'https://github.com/AcTweeteR/TwT-Actualizador')
        for url in ('https://attacker.example/?code=x&state=' + session['state'],
                    session['redirect_uri'] + '?code=x&state=wrong',
                    session['redirect_uri'] + '?code=x'):
            with self.assertRaises(ValueError):
                pkce.exchange_payload('public-id', session, url)
