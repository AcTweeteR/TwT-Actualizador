"""Exercise candidate navigation with an expired cache and forbidden network calls."""
import ast
import hashlib
import os
import sys
import time
import types
import urllib.error
import requests
import zipfile
from unittest.mock import patch

import pytest


def functions(filename, names):
    path = os.environ['ACTWEETER_XSTREAM_LIVE_ZIP']
    with zipfile.ZipFile(path) as archive:
        tree = ast.parse(archive.read('plugin.video.xstream-pro/resources/lib/' + filename))
    tree.body = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    scope = {'os': os, 'time': time, 'number': int}
    with zipfile.ZipFile(path) as archive:
        cache_tree = ast.parse(archive.read(
            'plugin.video.xstream-pro/resources/lib/catalog_cache.py'))
    cache_functions = [node for node in cache_tree.body
                       if isinstance(node, ast.FunctionDef)
                       and node.name in ('provider_fingerprint', 'source_matches')]
    cache_scope = {'hashlib': hashlib}
    exec(compile(ast.Module(body=cache_functions, type_ignores=[]),
                 'catalog_cache.py', 'exec'), cache_scope)
    scope['catalog_cache'] = types.SimpleNamespace(
        source_matches=cache_scope['source_matches'])
    exec(compile(tree, filename, 'exec'), scope)
    return scope


def forbidden(*args, **kwargs):
    raise AssertionError('navigation attempted a provider refresh')


@pytest.mark.parametrize('stype', ['movie', 'series'])
def test_expired_catalog_reads_without_provider_refresh(stype):
    scope = functions('addon.py', {'_get_cached_xtream_streams', '_get_cached_xtream_categories'})
    rows = [{'stream_id': 1, 'category_id': '2'}]
    scope.update(pm=types.SimpleNamespace(active='1'),
                 _cache_load=lambda *a: {'_src': 'host|user|password', '_data': rows},
                 _cache_valid=lambda *a, **k: False,
                 _refresh_catalog_generation=forbidden)
    assert scope['_get_cached_xtream_streams']('host', 'user', 'password', stype, '2') == rows
    assert scope['_get_cached_xtream_categories']('host', 'user', 'password', stype) == rows


def test_expired_movie_index_keeps_local_page_and_profile(tmp_path):
    scope = functions('premium_routes.py', {'indexed_movie_page', '_performance_call'})
    catalog = tmp_path / 'catalog.json'
    catalog.write_text('{}')
    selected = [{'stream_id': 1}]
    profiles = []

    class Index:
        reused = True
        def __init__(self, *a, **k): pass
        def page(self, **kwargs): return selected, False

    module = types.SimpleNamespace(CatalogIndex=Index, IndexUnavailable=LookupError,
                                   schedule_rebuild=forbidden)
    g = {'_get_credentials_for_profile': lambda p: dict(xtream_url='host', xtream_username='user', xtream_password='password'),
         '_cache_valid': forbidden,
         '_cache_path': lambda key, profile_num: profiles.append(profile_num) or str(catalog),
         '_get_cached_xtream_categories': lambda *a, profile_num: profiles.append(profile_num) or [],
         '_get_hidden_subcats': lambda *a: [], '_get_hidden_items': lambda *a: [],
         '_is_adult_category': lambda *a: False, '_log': lambda *a: None}
    with patch.dict(sys.modules, {'provider_catalog_index': module}):
        result = scope['indexed_movie_page'](g, 2, 'recent', lambda key, default='': default)
    assert result and result[0] == selected
    assert profiles == [2, 2]


def test_missing_movie_details_use_local_card_without_provider_call():
    scope = functions('premium_routes.py', {'metadata', 'provider_id', '_performance_call'})
    scope['backdrop'] = lambda value: value or ''
    def enrich(item, *credentials):
        assert not credentials, 'card lookup could issue an on-demand provider HTTP request'
        return {'plot': 'local plot', 'poster_url': 'local poster'}
    g = {'_enrich_movie_info': enrich, '_cache_load': lambda key: None}
    data = scope['metadata'](g, {'stream_id': 1, 'name': 'Cached title', 'year': '2024'},
                             'movie', ('host', 'user', 'password'))
    assert data['title'] == 'Cached title'
    assert data['plot'] == 'local plot'


def test_provider_error_classification_and_retry_after_are_preserved():
    scope = functions('premium_routes.py', {'_search_refresh_error'})
    classify = scope['_search_refresh_error']
    forbidden_error = urllib.error.HTTPError(
        'https://provider.invalid', 403, 'forbidden', {}, None)
    limited_error = urllib.error.HTTPError(
        'https://provider.invalid', 429, 'limited', {'Retry-After': '7200'}, None)
    assert classify(forbidden_error) == ('authentication', 0)
    provider_auth = type('ProviderAuthError', (Exception,), {})('expired')
    assert classify(provider_auth) == ('authentication', 0)
    assert classify(limited_error) == ('rate_limited', 7200)
    assert classify(TimeoutError()) == ('timeout', 0)
    assert classify(requests.exceptions.ReadTimeout('timed out')) == ('timeout', 0)
    assert classify(urllib.error.URLError('offline')) == ('connection', 0)
    assert classify(requests.exceptions.ConnectionError('network down')) == ('connection', 0)
    assert classify(ValueError('incomplete')) == ('incomplete', 0)
