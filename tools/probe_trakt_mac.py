#!/usr/bin/env python3
"""Query installed XStream through Kodi's native directory API on localhost.

No token access, playback, navigation, settings changes or Trakt history writes.
Output is counts/status only; provider URLs, account names and titles stay local.
"""
import argparse
import codecs
import json
import socket
import time
from urllib.parse import parse_qs, urlencode, urlsplit

ROUTES = {
    'menu': {'mode': 'xstream_tmdb_trakt_menu'},
    'watched-movies': {'mode': 'xstream_trakt_list', 'section': 'watched', 'tmdb_type': 'movie'},
    'watched-shows': {'mode': 'xstream_trakt_list', 'section': 'watched', 'tmdb_type': 'tv'},
    'playback-movies': {'mode': 'xstream_trakt_playback', 'media_kind': 'movies'},
    'playback-episodes': {'mode': 'xstream_trakt_playback', 'media_kind': 'episodes'},
    'recommendations-movies': {'mode': 'xstream_trakt_list', 'section': 'recommendations', 'tmdb_type': 'movie'},
    'recommendations-shows': {'mode': 'xstream_trakt_list', 'section': 'recommendations', 'tmdb_type': 'tv'},
}


def rpc(port, method, params=None, timeout=30):
    if method not in ('JSONRPC.Ping', 'JSONRPC.Introspect', 'Application.GetProperties',
                       'Player.GetActivePlayers', 'Files.GetDirectory'):
        raise ValueError('read-only probe method required')
    request = {'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}}
    decoder, data = json.JSONDecoder(), ''
    utf8 = codecs.getincrementaldecoder('utf-8')()
    with socket.create_connection(('127.0.0.1', port), timeout=3) as stream:
        stream.settimeout(timeout)
        stream.sendall((json.dumps(request) + '\r\n').encode())
        while len(data) < 8_000_000:
            chunk = stream.recv(65536)
            if not chunk:
                raise RuntimeError('incomplete Kodi reply')
            data += utf8.decode(chunk)
            while data.strip():
                try:
                    reply, end = decoder.raw_decode(data.lstrip())
                except json.JSONDecodeError:
                    break
                data = data.lstrip()[end:]
                if reply.get('id') != 1:
                    continue
                if 'error' in reply:
                    raise RuntimeError('Kodi error code %s' % reply['error'].get('code'))
                return reply.get('result')
    raise RuntimeError('Kodi reply exceeds probe bound')


def summarize(rows):
    modes, sections = set(), set()
    for row in rows:
        query = parse_qs(urlsplit(row.get('file', '')).query)
        modes.update(query.get('mode', []))
        sections.update(query.get('section', []))
    return {'items': len(rows), 'media_items': sum(row.get('type') in ('movie', 'episode', 'tvshow') for row in rows),
            'authorization_offered': 'xstream_trakt_authorize' in modes,
            'account_configuration_offered': 'settings' in modes,
            'account_routes_present': 'watched' in sections or 'history' in sections,
            'next_page_present': any('page' in parse_qs(urlsplit(row.get('file', '')).query) for row in rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=9090)
    parser.add_argument('--query', choices=tuple(ROUTES) + ('all',), default='menu')
    args = parser.parse_args()
    try:
        print(json.dumps({'ping': rpc(args.port, 'JSONRPC.Ping')}), flush=True)
        version = rpc(args.port, 'Application.GetProperties', {'properties': ['version']})
        print(json.dumps({'kodi': version['version']}), flush=True)
        schema = rpc(args.port, 'JSONRPC.Introspect', {'filter': {'id': 'Files.GetDirectory', 'type': 'method'}})
        if 'Files.GetDirectory' not in schema.get('methods', {}):
            raise RuntimeError('directory API not exported')
        active = rpc(args.port, 'Player.GetActivePlayers')
        print(json.dumps({'active_players': len(active)}), flush=True)
        menu = None
        names = ['menu'] + ([name for name in ROUTES if name != 'menu'] if args.query == 'all'
                           else [args.query] if args.query != 'menu' else [])
        for name in names:
            if name != 'menu' and not menu['account_routes_present']:
                print(json.dumps({'query': name, 'status': 'NOT_TESTED', 'reason': 'native_account_routes_absent'}), flush=True)
                continue
            start = time.monotonic()
            directory = 'plugin://plugin.video.xstream-pro/?' + urlencode(ROUTES[name])
            result = rpc(args.port, 'Files.GetDirectory', {'directory': directory, 'media': 'video',
                         'properties': ['title']})
            summary = summarize(result.get('files', []))
            if name == 'menu':
                menu = summary
            print(json.dumps({'query': name, 'seconds': round(time.monotonic() - start, 3), **summary}), flush=True)
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        # Exception messages from upstream could contain private request URLs.
        print(json.dumps({'status': 'FAILED', 'error_type': type(exc).__name__}), flush=True)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
