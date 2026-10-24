"""TMDb v3 user-session transport, with explicit opt-in and no token logging.

No writes are performed without a separate approved operation. The caller
must provide its own HTTPS requester, API key, session and account scope.
"""
from urllib.parse import urlencode

BASE = 'https://api.themoviedb.org/3'
AUTH_PAGE = 'https://www.themoviedb.org/authenticate/'


class TMDbAccount:
    def __init__(self, api_key, requester):
        if not isinstance(api_key, str) or len(api_key) != 32 or any(c not in '0123456789abcdefABCDEF' for c in api_key):
            raise ValueError('valid TMDb v3 API key required')
        if not callable(requester):
            raise ValueError('HTTPS requester required')
        self._key = api_key
        self._request = requester

    def _call(self, method, endpoint, *, session=None, payload=None, query=None):
        if not endpoint.startswith('/') or '://' in endpoint or '?' in endpoint:
            raise ValueError('invalid TMDb endpoint')
        params = {'api_key': self._key}
        if query is not None:
            if not isinstance(query, dict) or any(k not in ('page',) or type(v) is not int or v < 1 for k, v in query.items()):
                raise ValueError('invalid query parameters')
            params.update(query)
        if session is not None:
            if not isinstance(session, str) or not session.strip():
                raise ValueError('invalid session')
            params['session_id'] = session
        response = self._request(method, BASE + endpoint + '?' + urlencode(params), payload)
        if not isinstance(response, dict):
            raise ValueError('invalid TMDb response')
        return response

    def request_token(self):
        data = self._call('GET', '/authentication/token/new')
        if data.get('success') is not True or not data.get('request_token'):
            raise ValueError('TMDb token request failed')
        return {'request_token': data['request_token'], 'authorize_url': AUTH_PAGE + data['request_token']}

    def create_session(self, request_token):
        if not isinstance(request_token, str) or not request_token.strip():
            raise ValueError('request token required')
        data = self._call('POST', '/authentication/session/new', payload={'request_token': request_token})
        if data.get('success') is not True or not data.get('session_id'):
            raise ValueError('TMDb authorization not confirmed')
        return data['session_id']

    def account(self, session):
        data = self._call('GET', '/account', session=session)
        if type(data.get('id')) is not int or data['id'] < 1:
            raise ValueError('TMDb account identity unverified')
        return {'id': data['id']}

    def watchlist_page(self, session, account_id, kind, page=1):
        if type(account_id) is not int or account_id < 1 or kind not in ('movies', 'tv') or type(page) is not int or page < 1:
            raise ValueError('invalid TMDb watchlist request')
        endpoint = '/account/%d/watchlist/%s' % (account_id, kind)
        # Page is appended only through trusted validated input.
        data = self._call('GET', endpoint, session=session, query={'page': page})
        if (type(data.get('page')) is not int or data['page'] != page or
                type(data.get('total_pages')) is not int or data['total_pages'] < page or
                not isinstance(data.get('results'), list)):
            raise ValueError('incomplete TMDb watchlist page')
        return data

    def change_watchlist(self, session, account_id, kind, tmdb_id, *, add, approved):
        if approved is not True:
            raise PermissionError('specific remote write authorization required')
        if type(account_id) is not int or account_id < 1 or kind not in ('movie', 'tv') or type(tmdb_id) is not int or tmdb_id < 1 or type(add) is not bool:
            raise ValueError('invalid TMDb watchlist change')
        data = self._call('POST', '/account/%d/watchlist' % account_id, session=session,
                          payload={'media_type': kind, 'media_id': tmdb_id, 'watchlist': add})
        if data.get('success') is not True:
            raise ValueError('TMDb watchlist change not confirmed')
        return True
