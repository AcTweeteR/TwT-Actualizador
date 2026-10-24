"""Trakt PKCE authorization primitives. No Kodi writes or stored secrets.

The redirect may be a normal HTTPS page: the user copies its complete URL
(including code and state) into the application to finish authentication.
"""
import base64
import hashlib
import secrets
from urllib.parse import urlencode, urlsplit, parse_qs

AUTHORIZE_URL = 'https://trakt.tv/oauth/authorize'
TOKEN_URL = 'https://auth.trakt.tv/oauth/token'


def begin(client_id, redirect_uri):
    if not client_id or not redirect_uri.startswith('https://'):
        raise ValueError('Client ID and HTTPS redirect required')
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest()).rstrip(b'=').decode('ascii')
    state = secrets.token_urlsafe(32)
    url = AUTHORIZE_URL + '?' + urlencode({'response_type': 'code', 'client_id': client_id,
        'redirect_uri': redirect_uri, 'code_challenge': challenge,
        'code_challenge_method': 'S256', 'state': state})
    return {'url': url, 'verifier': verifier, 'state': state, 'redirect_uri': redirect_uri}


def exchange_payload(client_id, session, callback_url):
    """Validate callback before any network exchange; never log code/verifier."""
    parsed = urlsplit(callback_url)
    expected = urlsplit(session['redirect_uri'])
    if (parsed.scheme, parsed.netloc, parsed.path) != (expected.scheme, expected.netloc, expected.path):
        raise ValueError('Unexpected redirect destination')
    params = parse_qs(parsed.query)
    if 'error' in params:
        raise ValueError('Authorization denied')
    if len(params.get('state', [])) != 1 or not secrets.compare_digest(params['state'][0], session['state']):
        raise ValueError('OAuth state mismatch')
    if len(params.get('code', [])) != 1 or not params['code'][0]:
        raise ValueError('Missing authorization code')
    return {'grant_type': 'authorization_code', 'client_id': client_id,
            'redirect_uri': session['redirect_uri'], 'code': params['code'][0],
            'code_verifier': session['verifier']}


def exchange(client_id, session, callback_url, post, save_tokens):
    """Exchange an already validated callback; persist only successful tokens.

    `post` is injected for tests and must accept (url, json=..., timeout=...).
    `save_tokens` is the existing XStream atomic token writer.
    """
    payload = exchange_payload(client_id, session, callback_url)
    response = post(TOKEN_URL, json=payload, timeout=15)
    if response.status_code >= 400:
        raise RuntimeError('Trakt PKCE exchange failed (HTTP %d)' % response.status_code)
    tokens = response.json()
    if not isinstance(tokens, dict) or not tokens.get('access_token') or not tokens.get('refresh_token'):
        raise ValueError('Incomplete Trakt token response')
    save_tokens(tokens)
    return True
