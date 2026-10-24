#!/usr/bin/env python3
"""Private read-only catalog discovery. Title candidates NEVER authorize watched state.

Copies catalog/cache evidence outside Kodi. Only provider-confirmed external IDs
are passed to the normal importer. No playback, installation, OAuth or Trakt writes.
"""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor, as_completed
import collections
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
import tempfile
import unicodedata
from urllib.parse import urlencode
from urllib.request import Request, build_opener
import xml.etree.ElementTree as ET

from export_trakt_readonly_mac import NoRedirect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'source/0.4.32/addons/service.actweeter/resources'))
from lib.trakt_provider_index import catalog_members, verified_vod_records
from lib.trakt_sync import validate_export


def private_json(path, value):
    fd, temporary = tempfile.mkstemp(prefix='.metadata-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def safe_catalog_evidence(value, kind):
    """Keep only catalog identity fields; never copy provider credentials/URLs."""
    field = 'stream_id' if kind == 'movie' else 'series_id'
    if not isinstance(value, dict) or not isinstance(value.get('_data'), list):
        raise ValueError('invalid provider catalog')
    fields = (field, 'name', 'title', 'year', 'tmdb_id', 'imdb_id', 'tvdb_id')
    return {'_src': 'redacted', '_data': [
        {key: row[key] for key in fields if key in row}
        for row in value['_data'] if isinstance(row, dict)
    ]}


def provider_candidates(kind, selected, directory, profile):
    if kind != 'movie':
        return selected
    already_verified = {row['provider_id'] for row in
                        verified_vod_records(directory, profile=profile)}
    return [ident for ident in selected if ident not in already_verified]


def title_key(title):
    return ''.join(c for c in unicodedata.normalize('NFKD', re.sub(r'\s*\(\d{4}\)\s*$', '', str(title or ''))).casefold() if c.isalnum())


def remote_aliases(payload):
    result = {}
    for response in payload['responses']:
        if not isinstance(response['data'], list):
            continue
        for row in response['data']:
            for kind, field in (('movie', 'movie'), ('series', 'show')):
                value = row.get(field) or {}
                ident = (value.get('ids') or {}).get('tmdb')
                if str(ident).isdigit() and value.get('title'):
                    key = kind + ':' + str(ident)
                    result.setdefault(key, []).append([value['title'], str(value.get('year') or '')])
    return result


def candidate_ids(members, aliases):
    """Bound network lookups by exact title/year; this is NOT identity matching."""
    names = {(title_key(name), str(year)) for values in aliases.values() for name, year in values}
    names_only = {name for name, year in names}
    return sorted({ident for ident, row in members.items()
                   if any((title_key(row.get(field)), str(row.get('year') or '')) in names
                          or (not row.get('year') and title_key(row.get(field)) in names_only)
                          for field in ('title', 'name'))}, key=int)


def json_get(url, timeout=25, user_agent='python-requests/2.32.3'):
    request = Request(url, headers={'User-Agent': user_agent}, method='GET')
    with build_opener(NoRedirect()).open(request, timeout=timeout) as response:
        value = json.loads(response.read())
    if not isinstance(value, dict):
        raise ValueError('object response required')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kodi', type=Path, default=Path.home() / 'Library/Application Support/Kodi')
    parser.add_argument('--export', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--profile', default='1')
    parser.add_argument('--with-translations', action='store_true')
    args = parser.parse_args()
    start, cpu = time.monotonic(), time.process_time()
    source = args.kodi / 'userdata/addon_data/plugin.video.xstream-pro'
    if args.output.is_symlink():
        parser.error('symlink output is not allowed')
    output = args.output.resolve()
    if (output == ROOT or ROOT in output.parents or output == source or source in output.parents
            or output == args.kodi.resolve() or args.kodi.resolve() in output.parents
            or not args.profile.isdigit() or int(args.profile) < 1):
        parser.error('isolated private evidence directory required')
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    if output.is_symlink() or output.stat().st_mode & 0o077:
        parser.error('mode-0700 output required')
    payload = json.loads((args.export / 'snapshot.json').read_text())
    manifest = json.loads((args.export / 'manifest.json').read_text())
    if hashlib.sha256((args.export / 'snapshot.json').read_bytes()).hexdigest() != manifest['sha256']:
        raise ValueError('snapshot hash mismatch')
    validate_export(payload, manifest, profile=args.profile, account=payload['snapshot']['account'])
    settings = {node.get('id'): node.text or node.get('value', '') for node in
                ET.parse(source / 'settings.xml').findall('.//setting')}
    prefix = 'profile_' + args.profile + '_'
    host, user, password = (settings.get(prefix + key, '') for key in
                            ('xtream_url', 'xtream_username', 'xtream_password'))
    if not all((host, user, password)):
        raise PermissionError('selected provider credentials unavailable')
    for kind in ('movie', 'series'):
        path = source / ('data_cache_p%s_xtream_streams_%s.json' % (args.profile, kind))
        content = json.loads(path.read_text())
        if content.get('_src') != '|'.join((host, user, password)):
            raise PermissionError('provider source mismatch')
    patterns = ['data_cache_p%s_xtream_streams_*.json' % args.profile,
                'data_cache_p%s_vod_info_*.json' % args.profile,
                'data_cache_p%s_series_info_*.json' % args.profile,
                'data_cache_p%s_premium_meta_*.json' % args.profile,
                'series_changes_p%s.json' % args.profile]
    for pattern in patterns:
        for path in source.glob(pattern):
            if path.is_symlink():
                raise ValueError('unsafe evidence input')
            target = output / path.name
            if target.is_symlink():
                raise ValueError('unsafe existing evidence')
            if '_xtream_streams_' in path.name:
                kind = 'movie' if path.name.endswith('_movie.json') else 'series'
                evidence = safe_catalog_evidence(json.loads(path.read_text()), kind)
                if target.exists() and json.loads(target.read_text()) != evidence:
                    raise ValueError('catalog generation changed; use a new evidence directory')
                if not target.exists(): private_json(target, evidence)
            elif not target.exists():
                shutil.copyfile(path, target); target.chmod(0o600)
    aliases = remote_aliases(payload)
    metrics = {'tmdb_get': 0, 'provider_get': 0, 'errors': {}, 'kodi_writes': 0, 'remote_writes': 0}
    if args.with_translations:
        tree = ast.parse((args.kodi / 'addons/plugin.video.xstream-pro/resources/lib/tmdb.py').read_bytes())
        key = settings.get('tmdb_api_key') or next(ast.literal_eval(n.value) for n in tree.body
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'BUNDLED_API_KEY' for t in n.targets))
        metadata_dir = output / 'tmdb'; metadata_dir.mkdir(mode=0o700, exist_ok=True)
        def translate(item):
            ref, values = item; kind, ident = ref.split(':'); path = metadata_dir / (ref.replace(':', '-') + '.json')
            if path.exists():
                value = json.loads(path.read_text()); fetched = False
            else:
                value = json_get('https://api.themoviedb.org/3/' + ('movie' if kind == 'movie' else 'tv') + '/' + ident + '?' +
                    urlencode({'api_key': key, 'append_to_response': 'translations,alternative_titles'}))
                if str(value.get('id')) != ident:
                    raise ValueError('TMDb ID mismatch')
                private_json(path, value); fetched = True
            year = str(value.get('release_date') or value.get('first_air_date') or '')[:4]
            names = [value.get('title') or value.get('name'), value.get('original_title') or value.get('original_name')]
            names.extend((t.get('data') or {}).get('title') or (t.get('data') or {}).get('name')
                         for t in (value.get('translations') or {}).get('translations', []))
            alternative = value.get('alternative_titles') or {}
            names.extend(t.get('title') for t in alternative.get('titles', alternative.get('results', [])))
            return ref, values + [[name, year] for name in names if name and year], fetched
        with ThreadPoolExecutor(max_workers=3) as pool:
            jobs = [pool.submit(translate, item) for item in aliases.items()]
            for future in as_completed(jobs):
                try:
                    ref, values, fetched = future.result(); aliases[ref] = values
                    metrics['tmdb_get'] += int(fetched)
                except Exception as error:
                    name = type(error).__name__; metrics['errors'][name] = metrics['errors'].get(name, 0) + 1
        private_json(output / 'lookup-aliases.json', aliases)
    requests = []
    for kind in ('movie', 'series'):
        members = catalog_members(output, args.profile, kind)
        selected = candidate_ids(members, {key:value for key,value in aliases.items() if key.startswith(kind + ':')})
        selected = provider_candidates(kind, selected, output, args.profile)
        metrics[kind + '_catalog_members'] = len(members)
        metrics[kind + '_lookup_candidates'] = len(selected)
        requests.extend((kind, ident) for ident in selected)
    if len(requests) > 285:
        raise ValueError('discovery exceeds the user-authorized one-shot GET limit')
    fresh = output / 'provider-verified'; fresh.mkdir(mode=0o700, exist_ok=True)
    def provider_get(item):
        kind, ident = item; cache_name = 'data_cache_p%s_%s_info_%s.json' % (args.profile, 'vod' if kind == 'movie' else 'series', ident)
        marker = fresh / cache_name
        if marker.exists():
            return False
        query = {'username': user, 'password': password,
                 'action': 'get_vod_info' if kind == 'movie' else 'get_series_info',
                 'vod_id' if kind == 'movie' else 'series_id': ident}
        value = json_get(host.rstrip('/').removesuffix('/player_api.php') + '/player_api.php?' + urlencode(query), timeout=20,
            user_agent=settings.get('custom_user_agent') or 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
        if not isinstance(value.get('info'), dict):
            raise ValueError('missing provider info')
        if kind == 'movie' and str((value.get('movie_data') or {}).get('stream_id')) != ident:
            raise ValueError('provider movie ID mismatch')
        if kind == 'series' and not isinstance(value.get('episodes'), dict):
            raise ValueError('incomplete provider episode response')
        private_json(output / cache_name, value); private_json(marker, {'verified': True})
        return True
    # Do not enqueue hundreds of timeouts when the configured provider is offline.
    if requests:
        try:
            metrics['provider_get'] += int(provider_get(requests[0]))
        except Exception as error:
            metrics.update(status='PROVIDER_UNREACHABLE', provider_pending=len(requests),
                           connectivity_error=type(error).__name__,
                           wall_seconds=round(time.monotonic() - start, 3),
                           cpu_seconds=round(time.process_time() - cpu, 3))
            private_json(output / ('discovery-metrics-' + str(time.time_ns()) + '.json'), metrics)
            print(json.dumps(metrics, sort_keys=True)); return
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = [pool.submit(provider_get, item) for item in requests[1:]]
        for future in as_completed(jobs):
            try: metrics['provider_get'] += int(future.result())
            except Exception as error:
                name = type(error).__name__; metrics['errors'][name] = metrics['errors'].get(name, 0) + 1
    metrics.update(wall_seconds=round(time.monotonic() - start, 3), cpu_seconds=round(time.process_time() - cpu, 3))
    private_json(output / ('discovery-metrics-' + str(time.time_ns()) + '.json'), metrics)
    print(json.dumps(metrics, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'status': 'FAILED', 'error_type': type(error).__name__}))
        raise SystemExit(1)
