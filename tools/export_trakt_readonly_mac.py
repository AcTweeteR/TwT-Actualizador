#!/usr/bin/env python3
"""Strict GET-only Mac snapshot, using the existing XStream account in memory.

No OAuth refresh, redirects, installed-code changes, remote/local playback writes.
Private export files must be outside the repository in a mode-0700 directory.
"""
import argparse
import ast
import json
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'source/0.4.32'
sys.path.insert(0, str(LIB / 'addons/service.actweeter/resources/lib'))
sys.path.insert(0, str(LIB / 'third_party/xstream'))
from trakt_snapshot import export_snapshot

PATHS = {'/users/settings', '/sync/last_activities'} | {
    '/sync/' + group + '/' + kind for group in ('watched', 'history', 'playback')
    for kind in ('movies', 'shows', 'episodes')}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class ReadOnlyTrakt:
    def __init__(self, kodi):
        addon = kodi / 'addons/plugin.video.xstream-pro/resources/lib/trakt.py'
        tree = ast.parse(addon.read_bytes())
        client = next(ast.literal_eval(node.value) for node in tree.body
                      if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name)
                      and t.id == 'BUNDLED_CLIENT_ID' for t in node.targets))
        profile = kodi / 'userdata/addon_data/plugin.video.xstream-pro'
        settings = ET.parse(profile / 'settings.xml')
        custom = next((node.text for node in settings.findall('.//setting')
                       if node.get('id') == 'trakt_client_id'), None)
        token = json.loads((profile / 'trakt/trakt_tokens.json').read_text()).get('access_token')
        if not isinstance(token, str) or not token:
            raise PermissionError('existing XStream OAuth authorization required')
        self.headers = {'User-Agent': 'python-requests/2.32.3', 'Authorization': 'Bearer ' + token, 'trakt-api-key': custom or client,
                        'trakt-api-version': '2', 'Content-Type': 'application/json'}
        self.opener = build_opener(NoRedirect())
        self.calls = []

    def get(self, path, params):
        if path not in PATHS:
            raise ValueError('snapshot GET endpoint required')
        start = time.monotonic()
        req = Request('https://api.trakt.tv' + path + ('?' + urlencode(params) if params else ''),
                      headers=self.headers, method='GET')
        with self.opener.open(req, timeout=35) as response:
            payload = json.loads(response.read())
            headers = response.headers
            pagination = {key: int(headers.get('X-Pagination-' + name)) for key, name in
                [('page', 'Page'), ('limit', 'Limit'), ('page_count', 'Page-Count'),
                 ('item_count', 'Item-Count')] if headers.get('X-Pagination-' + name) is not None}
        self.calls.append({'path': path, 'page': params.get('page'),
                           'seconds': round(time.monotonic() - start, 6),
                           'rows': len(payload) if isinstance(payload, list) else None,
                           'pagination': pagination})
        if isinstance(payload, list) and set(pagination) != {'page','limit','page_count','item_count'}:
            raise ValueError('complete pagination headers required')
        return payload, pagination if pagination else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kodi', type=Path, default=Path.home() / 'Library/Application Support/Kodi')
    parser.add_argument('--profile', default='1')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.is_symlink():
        parser.error('symlink output is not allowed')
    output = args.output.resolve()
    if output == ROOT or ROOT in output.parents:
        parser.error('private export must be outside the repository')
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    if output.is_symlink() or output.stat().st_mode & 0o077:
        parser.error('mode-0700 output directory required')
    client = None
    try:
        client = ReadOnlyTrakt(args.kodi)
        summary = export_snapshot(client.get, output, args.profile)
        print(json.dumps(summary, sort_keys=True))
        return 0
    except Exception as error:
        print(json.dumps({'status': 'FAILED', 'error_type': type(error).__name__,
                          'http_status': error.code if isinstance(error, HTTPError) else None}))
        return 1
    finally:
        if client is not None:
            target = output / ('get-metrics-' + str(time.time_ns()) + '.json')
            with target.open('x') as stream:
                os.chmod(target, 0o600)
                json.dump({'method': 'GET', 'calls': client.calls}, stream)


if __name__ == '__main__':
    raise SystemExit(main())
