"""Exact identities from current provider catalogs and already cached metadata.

No network, title-based identity, personal state or additional database.
"""
import json
import codecs
import math
import hashlib
import re
import sqlite3
from contextlib import closing
from pathlib import Path
try:
    from .trakt_sync import normalize_ids
except ImportError:
    from trakt_sync import normalize_ids


def read_object(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, UnicodeError):
        return None


def catalog_generation_path(directory, profile, key, legacy_path=None):
    """Resolve one immutable file from the newest complete committed generation."""
    root = Path(directory)
    generations = root / "catalog_generations"
    if root.is_symlink() or generations.is_symlink() or not generations.is_dir():
        return Path(legacy_path) if legacy_path is not None else root / (
            "data_cache_p%s_%s.json" % (profile, key))
    pointers = list(generations.glob("p%s-*.json" % profile))
    pointers = [path for path in pointers if not path.name.endswith(".previous.json")
                and not path.is_symlink()]
    candidates = []
    for path in pointers:
        current = read_object(path)
        previous = read_object(path.with_name(path.stem + ".previous.json"))
        for pointer in (current, previous):
            if isinstance(pointer, dict) and isinstance(pointer.get("updated_at"), (int, float)):
                candidates.append((pointer["updated_at"], path, pointer))
    for _, pointer_path, pointer in sorted(candidates, reverse=True,
                                            key=lambda item: item[0]):
        generation = pointer.get("generation")
        if (not isinstance(generation, str) or not re.fullmatch(r"[a-f0-9]{32}", generation)
                or pointer_path.is_symlink()):
            continue
        container = generations / pointer_path.stem
        generation_dir = container / generation
        manifest = read_object(generation_dir / "manifest.json")
        filename = key + ".json"
        files = manifest.get("files") if isinstance(manifest, dict) else None
        expected_files = {
            "xtream_streams_movie", "xtream_cats_movie",
            "xtream_streams_series", "xtream_cats_series",
            "xtream_counts_movie", "xtream_counts_series",
        }
        if (generation_dir.is_symlink() or not isinstance(manifest, dict)
                or manifest.get("schema") != 1 or manifest.get("generation") != generation
                or set(files or {}) != expected_files or key not in (files or {})
                or manifest.get("provider") != pointer_path.stem.split("-", 1)[-1]):
            continue
        try:
            valid = True
            for file_key in expected_files:
                item_path = generation_dir / (file_key + ".json")
                if (item_path.is_symlink() or not item_path.is_file()
                        or hashlib.sha256(item_path.read_bytes()).hexdigest() != files[file_key]):
                    valid = False
                    break
                value = json.loads(item_path.read_text(encoding="utf-8"))
                if file_key in {"xtream_streams_movie", "xtream_cats_movie",
                                "xtream_streams_series", "xtream_cats_series"}:
                    valid = (isinstance(value, dict) and isinstance(value.get("_data"), list))
                else:
                    valid = isinstance(value, dict)
                if not valid:
                    break
            if not valid:
                continue
            target = generation_dir / filename
        except (OSError, ValueError, KeyError, TypeError):
            continue
        return target
    return Path(legacy_path) if legacy_path is not None else root / (
        "data_cache_p%s_%s.json" % (profile, key))


def catalog_source(path):
    with Path(path).open('rb') as stream:
        prefix = codecs.getincrementaldecoder('utf-8')().decode(stream.read(65536), final=False)
    match = re.match(r'\s*\{\s*"_src"\s*:\s*', prefix)
    if match is None:
        value = read_object(path)
        source = value.get('_src') if value else None
    else:
        source, _ = json.JSONDecoder().raw_decode(prefix[match.end():])
    if not isinstance(source, str):
        raise ValueError('invalid source header')
    return source


def _indexed_members(path, profile, provider_ids):
    """Reuse valid v13/v14 offsets read-only for a bounded batch, never build one."""
    stat = path.stat()
    source = catalog_source(path)
    with path.open('rb') as stream:
        stamp = (str(stat.st_size), str(stat.st_mtime_ns), str(stat.st_ino), '2',
                 hashlib.sha256((str(profile) + '\0' + source + '\0movie').encode()).hexdigest())
        sidecar = Path(str(path) + '.idx-' + stamp[4][:16] + '.sqlite')
        if sidecar.is_symlink() or not sidecar.is_file():
            raise ValueError('missing offset index')
        with closing(sqlite3.connect(sidecar.as_uri() + '?mode=ro', uri=True, timeout=.05)) as db:
            saved = tuple(v for k, v in db.execute('SELECT key,value FROM meta ORDER BY CAST(key AS INTEGER)'))
            if saved != stamp:
                raise ValueError('stale offset index')
            rows = []
            selected = sorted(set(map(str, provider_ids)))
            query = 'SELECT id,start,length FROM items WHERE id IN (' + ','.join('?' for _ in selected) + ')'
            for ident, start, length in db.execute(query, selected) if selected else []:
                stream.seek(start)
                item = json.loads(stream.read(length))
                if str(item.get('stream_id')) != ident:
                    raise ValueError('offset identity mismatch')
                rows.append(item)
        if (path.stat().st_size, path.stat().st_mtime_ns, path.stat().st_ino) != (stat.st_size, stat.st_mtime_ns, stat.st_ino):
            raise ValueError('catalog changed during indexed read')
        return rows


def catalog_members(directory, profile, stype, provider_ids=None):
    if not str(profile).isdigit() or int(profile) < 1:
        raise ValueError('invalid profile')
    if Path(directory).is_symlink():
        raise ValueError('unsafe provider directory')
    key = 'xtream_streams_%s' % stype
    legacy = Path(directory) / ('data_cache_p%s_%s.json' % (profile, key))
    path = catalog_generation_path(directory, profile, key, legacy)
    rows = None
    if provider_ids is not None and stype == 'movie' and not path.is_symlink():
        try:
            rows = _indexed_members(path.resolve(), profile, provider_ids)
        except (OSError, ValueError, sqlite3.Error, UnicodeError):
            pass
    if rows is None:
        value = read_object(path)
        if value is None or not isinstance(value.get('_data'), list):
            return {}
        rows = value['_data']
    field = 'stream_id' if stype == 'movie' else 'series_id'
    selected = set(map(str, provider_ids)) if provider_ids is not None else None
    members, conflicts = {}, set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        ident = str(row.get(field, ''))
        if selected is not None and ident not in selected:
            continue
        if not ident.isdigit() or int(ident) < 1:
            continue
        previous = members.get(ident)
        if previous and any(str(previous.get(key) or '') != str(row.get(key) or '')
                            for key in ('name', 'title', 'year', 'tmdb_id', 'imdb_id')):
            conflicts.add(ident)
        members[ident] = row
    return {key: row for key, row in members.items() if key not in conflicts}


def external_ids(data):
    if not isinstance(data, dict):
        return {}
    return normalize_ids({'tmdb': data.get('tmdb_id') or data.get('tmdb'),
                          'imdb': data.get('imdb_id') or data.get('imdb'),
                          'tvdb': data.get('tvdb_id') or data.get('tvdb')})


def duration_seconds(info):
    seconds = info.get('duration_secs')
    if isinstance(seconds, str) and seconds.isdigit():
        seconds = int(seconds)
    return seconds if type(seconds) in (int, float) and math.isfinite(seconds) and 0 < seconds < 86400 else None


def verified_vod_records(directory, *, profile, provider_ids=None):
    root = Path(directory)
    members = catalog_members(root, profile, 'movie', provider_ids)
    result = []
    for provider_id, row in members.items():
        ids = external_ids(row)
        seconds = duration_seconds(row)
        details = read_object(root / ('data_cache_p%s_vod_info_%s.json' % (profile, provider_id)))
        if details:
            info, movie = details.get('info'), details.get('movie_data')
            if (isinstance(info, dict) and isinstance(movie, dict)
                    and str(movie.get('stream_id')) == provider_id
                    and not any(movie.get(key) and row.get(key) and str(movie[key]) != str(row[key])
                                for key in ('name', 'year'))):
                extra = external_ids(info)
                if any(ids[key] != value for key, value in extra.items() if key in ids):
                    continue
                ids.update(extra)
                seconds = duration_seconds(info) or seconds
        ids.pop('tvdb', None)
        if ids:
            result.append({'profile': str(profile), 'kind': 'movie', 'provider_id': provider_id,
                           'ids': ids, 'confidence': 'verified', 'duration_seconds': seconds})
    return result
