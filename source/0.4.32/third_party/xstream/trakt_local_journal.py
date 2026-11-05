"""Durable, non-exporting audit of XStream history changes; no URLs are stored."""
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import threading
import time
import uuid

_origin = threading.local()


@contextmanager
def remote_changes():
    previous = getattr(_origin, 'value', 'local')
    _origin.value = 'trakt_import'
    try:
        yield
    finally:
        _origin.value = previous


@contextmanager
def verified_scope(*, account, profile, provider_scope, kodi_profile, generation):
    """Caller must verify this binding before entering the mutation, never after it."""
    if (not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', account)
            or not re.fullmatch(r'[1-9][0-9]?', str(profile))
            or any(not re.fullmatch(r'[0-9a-f]{64}', value)
                   for value in (provider_scope, kodi_profile, generation))):
        raise ValueError('verified capture scope required')
    previous = getattr(_origin, 'scope', None)
    _origin.scope = dict(account=account, profile=str(profile), provider_scope=provider_scope,
                         kodi_profile=kodi_profile, generation=generation)
    try:
        yield
    finally:
        _origin.scope = previous


def _completed_state(event):
    if event.get('origin') == 'trakt_import':
        return 'observed'
    return 'ready' if event.get('scope') else 'quarantined'


def _hash(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _state_hash(value):
    return _hash(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True))


def _safe_id(value):
    text = str(value)
    return text if re.fullmatch(r'(?:[0-9]+|tmdb:movie:[0-9]+|tmdb:episode:[0-9]+:s[0-9]+:e[0-9]+)', text) else 'sha256:' + _hash(text)


def _episode_set(data):
    result = set()
    for series, seasons in data.items():
        if not isinstance(seasons, dict):
            raise ValueError('invalid episode history')
        for season, episodes in seasons.items():
            if not isinstance(episodes, list):
                raise ValueError('invalid episode history')
            result.update((str(series), str(season), str(episode)) for episode in episodes)
    return result


def _delta(kind, before, after):
    if kind == 'Favorites':
        result = []
        for folder in sorted((set(before) | set(after)) - {'version'}):
            def members(data):
                return {(str(item.get('stype', 'live')), str(item.get('id')))
                        for item in data.get(folder, [])}
            old, new = members(before), members(after)
            semantic = 'pending' if folder in ('AcTweeteR Pending - Movies', 'AcTweeteR Pending - Series') else 'local_folder'
            for kind_id in sorted(old ^ new):
                result.append({'identity': [_safe_id(value) for value in kind_id],
                    'collection': semantic, 'media_type': kind_id[0] if kind_id[0] in ('movie', 'series', 'live') else 'unknown', 'folder_sha256': _hash(folder),
                    'change': 'add' if kind_id in new else 'remove'})
        return result
    if kind == 'WatchedEpisodes':
        old, new = _episode_set(before), _episode_set(after)
        return [{'identity': [_safe_id(v) for v in key], 'change': 'add' if key in new else 'remove'}
                for key in sorted(old ^ new)]
    result = []
    for key in sorted(set(before) | set(after)):
        old, new = before.get(key), after.get(key)
        if old == new and (key in before) == (key in after):
            continue
        change = 'remove' if key not in after else 'add' if key not in before else 'update'
        row = {'identity': ('sha256:' + _hash(str(key)) if kind == 'ResumePoints' else _safe_id(key)),
               'change': change}
        if kind == 'ResumePoints' and isinstance(new, dict):
            for field in ('timestamp', 'position', 'duration'):
                value = new.get(field)
                if type(value) in (int, float) and math.isfinite(value):
                    row[field] = value
            position, duration = row.get('position'), row.get('duration')
            if (type(position) in (int, float) and type(duration) in (int, float)
                    and 0 <= position <= duration and duration > 0):
                row['percent'] = 100.0 * position / duration
        elif kind == 'WatchedMovies' and type(new) is bool:
            row['watched'] = new
        result.append(row)
    return result


def _database(store_path):
    target = Path(store_path)
    root = target.parent
    if root.is_symlink() or target.is_symlink():
        raise ValueError('unsafe history journal path')
    match = re.fullmatch(r'(?:(?:watched_movies|watched_episodes|resume_points)_p|favorites_)([1-9][0-9]?)\.json', target.name)
    if not match:
        raise ValueError('unknown history store')
    journal = root / 'trakt_local_changes.sqlite'
    if journal.is_symlink() or (journal.exists() and not journal.is_file()):
        raise ValueError('unsafe history journal')
    try:
        os.close(os.open(str(journal), os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, 'O_NOFOLLOW', 0), 0o600))
    except FileExistsError:
        if journal.is_symlink():
            raise ValueError('unsafe history journal')
    return journal, match.group(1)


def prepare(store_path, kind, before, after):
    if kind not in ('WatchedMovies', 'WatchedEpisodes', 'ResumePoints', 'Favorites'):
        raise ValueError('unsupported history store')
    delta = _delta(kind, before, after)
    if not delta:
        return None
    journal, profile = _database(store_path)
    event = {'id': uuid.uuid4().hex, 'profile': profile, 'kind': kind,
             'store': Path(store_path).name, 'before_sha256': _state_hash(before),
             'after_sha256': _state_hash(after),
             'origin': getattr(_origin, 'value', 'local'), 'created_at': time.time(), 'changes': delta}
    scope = getattr(_origin, 'scope', None)
    if scope and scope['profile'] == profile:
        event['scope'] = dict(scope)
        if kind == 'Favorites':
            _capture_native_destinations(Path(store_path).parent, scope, delta)
        if kind == 'WatchedMovies':
            _capture_movie_identities(Path(store_path).parent, profile, scope, delta)
        if kind == 'WatchedEpisodes':
            for change in delta:
                external = _episode_identity(Path(store_path).parent, profile, scope, change['identity'])
                if external is not None:
                    change['external_identity'] = external
        if kind == 'ResumePoints':
            _capture_resume_identities(Path(store_path).parent, profile, scope, delta, after)
    with sqlite3.connect(str(journal), timeout=5) as db:
        db.execute('CREATE TABLE IF NOT EXISTS changes (id TEXT PRIMARY KEY, event TEXT NOT NULL, state TEXT NOT NULL)')
        db.execute('INSERT INTO changes VALUES (?,?,?)', (event['id'], json.dumps(event, sort_keys=True), 'prepared'))
    return str(journal), event['id']


def recover(store_path, current):
    """Classify interrupted writes while holding the corresponding store lock."""
    journal, _ = _database(store_path)
    with sqlite3.connect(str(journal), timeout=5) as db:
        db.execute('CREATE TABLE IF NOT EXISTS changes (id TEXT PRIMARY KEY, event TEXT NOT NULL, state TEXT NOT NULL)')
        rows = db.execute("SELECT id,event FROM changes WHERE state='prepared'").fetchall()
        digest = _state_hash(current)
        for identifier, raw in rows:
            event = json.loads(raw)
            if event.get('store') != Path(store_path).name:
                continue
            # No captured account/provider binding is available for local events.
            state = _completed_state(event) if event.get('after_sha256') == digest else 'quarantined'
            db.execute("UPDATE changes SET state=? WHERE id=? AND state='prepared'", (state, identifier))


def finish(ticket):
    if ticket is None:
        return
    journal, identifier = ticket
    with sqlite3.connect(journal, timeout=5) as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("SELECT event FROM changes WHERE id=? AND state='prepared'", (identifier,)).fetchone()
        if row is None:
            raise RuntimeError('history journal confirmation missing')
        event = json.loads(row[0])
        state = _completed_state(event)
        if _consolidate_resume(db, event):
            state = 'superseded'
        cursor = db.execute("UPDATE changes SET state=? WHERE id=? AND state='prepared'", (state, identifier))
        if cursor.rowcount != 1:
            raise RuntimeError('history journal confirmation missing')


def deliver(store_path, outbox, *, scope):
    """Idempotent handoff; a crash after enqueue retries the same operation ID."""
    from datetime import datetime, timezone
    from lib.trakt_outbox import manual_event
    journal, _ = _database(store_path)
    delivered = 0
    with sqlite3.connect(str(journal), timeout=5) as db:
        rows = db.execute("SELECT id,event FROM changes WHERE state='ready'").fetchall()
        for identifier, raw in rows:
            event = json.loads(raw)
            if event.get('scope') != scope or event.get('origin') != 'local':
                continue
            if ((event['kind'] == 'ResumePoints' and
                    not all(change.get('external_identity') and change.get('progress') is not None
                            for change in event['changes'])) or
                    (event['kind'] == 'Favorites' and
                     not all(change.get('destination_capture') and change.get('external_identity')
                             for change in event['changes']))):
                receipt = outbox.retain_capture(source='resume' if event['kind'] == 'ResumePoints' else 'favorites', source_id=_hash(identifier),
                    fingerprint=_state_hash(event), reason='identity_or_authority_unverified')
                event['outbox_ids'] = [receipt]
                db.execute("UPDATE changes SET event=?,state='retained' WHERE id=?",
                           (json.dumps(event, sort_keys=True), identifier))
                db.commit()
                delivered += 1
                continue
            operations = []
            for index, change in enumerate(event['changes']):
                if event['kind'] == 'Favorites':
                    captured = change['destination_capture']
                    if captured.get('scope') != scope or change['change'] not in ('add', 'remove'):
                        break
                    content = change['external_identity']
                    expected = {'movie': 'movie', 'series': 'show'}.get(change.get('media_type'))
                    if expected is None or content.get('kind') != expected:
                        break
                    operations.append(manual_event(scope['account'], scope['profile'],
                        captured['destination'] + '.' + change['change'], content,
                        _hash(identifier + ':' + str(index))[:32],
                        provider_scope=scope['provider_scope']))
                    continue
                if event['kind'] == 'ResumePoints':
                    content = change.get('external_identity')
                    progress = change.get('progress')
                    if (change.get('change') not in ('add', 'update')
                            or not isinstance(content, dict) or content.get('kind') not in ('movie', 'episode')
                            or type(progress) not in (int, float) or not 1.0 <= progress < 93.0):
                        break
                    operations.append(manual_event(scope['account'], scope['profile'],
                        'playback.pause', content, _hash(identifier + ':' + str(index))[:32],
                        provider_scope=scope['provider_scope'], progress=progress))
                    continue
                # Provider IDs are never sent as Trakt IDs. Only strict catalog
                # evidence captured at mutation time may attribute them.
                match = re.fullmatch(r'tmdb:movie:([1-9][0-9]*)', str(change['identity']))
                if event['kind'] == 'WatchedMovies' and (match or change.get('external_identity')):
                    if change['change'] != 'remove' and type(change.get('watched')) is not bool:
                        break
                    content = change.get('external_identity') or {'kind': 'movie', 'ids': {'tmdb': int(match.group(1))}}
                    if not isinstance(content, dict) or content.get('kind') != 'movie':
                        break
                    watched = change['change'] != 'remove' and change.get('watched') is True
                elif event['kind'] == 'WatchedEpisodes' and change.get('external_identity'):
                    content = change['external_identity']
                    if content.get('kind') != 'episode':
                        break
                    watched = change['change'] == 'add'
                else:
                    break
                when = datetime.fromtimestamp(event['created_at'], timezone.utc).isoformat().replace('+00:00', 'Z')
                operations.append(manual_event(scope['account'], scope['profile'],
                    'history.add' if watched else 'history.remove',
                    content,
                    _hash(identifier + ':' + str(index))[:32], when if watched else None,
                    provider_scope=scope['provider_scope']))
            else:
                for operation in operations:
                    outbox.enqueue_manual(operation, held=True)
                event['outbox_ids'] = [operation['id'] for operation in operations]
                db.execute("UPDATE changes SET event=?,state='queued' WHERE id=?",
                           (json.dumps(event, sort_keys=True), identifier))
                db.commit()
                delivered += 1
                continue
            db.execute("UPDATE changes SET state='quarantined' WHERE id=?", (identifier,))
    return delivered


def remember_binding(addon, account, profile, provider_scope, tokens, vfs):
    """Persist only the fingerprint of credentials used for a verified account GET."""
    import tempfile
    root = Path(vfs.translatePath(addon.getAddonInfo('profile')))
    credential = tokens.get('access_token')
    if not isinstance(credential, str) or not credential:
        return
    kodi_profile = _hash(vfs.translatePath('special://profile/'))
    generation = _hash(json.dumps([account, profile, provider_scope, kodi_profile, credential]))
    binding = dict(account=account, profile=profile, provider_scope=provider_scope,
                   kodi_profile=kodi_profile, generation=generation)
    with verified_scope(**binding):
        pass
    target = root / 'trakt_capture_binding.json'
    if root.is_symlink() or target.is_symlink():
        raise ValueError('unsafe capture binding')
    fd, temporary = tempfile.mkstemp(prefix='.capture-', dir=str(root))
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(dict(scope=binding, credential_sha256=_hash(credential)), stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def runtime_scope(store_path):
    """No network during store writes; changed credentials invalidate the binding."""
    binding = None
    try:
        import xbmcaddon
        import xbmcvfs
        import trakt
        from profiles import ProfileManager
        from trakt_live_queue import provider_fingerprint
        addon = xbmcaddon.Addon('plugin.video.xstream-pro')
        root = Path(xbmcvfs.translatePath(addon.getAddonInfo('profile')))
        target = root / 'trakt_capture_binding.json'
        if (root.resolve() != Path(store_path).parent.resolve() or root.is_symlink()
                or target.is_symlink() or target.stat().st_size > 4096):
            raise ValueError('invalid capture location')
        record = json.loads(target.read_text())
        manager = ProfileManager(addon)
        creds = manager.get_credentials()
        provider = provider_fingerprint(str(manager.active), creds.get('source_type'),
            creds.get('xtream_url'), creds.get('xtream_username'), creds.get('m3u_url'))
        candidate = record['scope']
        token = trakt._read_tokens().get('access_token')
        if (isinstance(token, str) and token and record['credential_sha256'] == _hash(token)
                and candidate['profile'] == str(manager.active)
                and candidate['provider_scope'] == provider
                and candidate['kodi_profile'] == _hash(xbmcvfs.translatePath('special://profile/'))):
            binding = candidate
    except (ImportError, OSError, ValueError, KeyError, TypeError, AttributeError):
        pass
    if binding is None:
        previous = getattr(_origin, 'scope', None)
        _origin.scope = None
        try:
            yield
        finally:
            _origin.scope = previous
    else:
        with verified_scope(**binding):
            yield


def runtime_handoff(store_path):
    if getattr(_origin, 'value', 'local') != 'local':
        return
    from history_store_coordinator import _locked
    with _locked(str(store_path)):
        with open(store_path, 'r', encoding='utf-8') as stream:
            current = json.load(stream)
        if not isinstance(current, (dict, list)):
            raise ValueError('invalid history store')
        recover(store_path, current)
    with runtime_scope(store_path):
        scope = getattr(_origin, 'scope', None)
        if scope is None:
            return
        import sys
        import xbmcaddon
        import xbmcvfs
        service = xbmcaddon.Addon('service.actweeter')
        resources = str(Path(xbmcvfs.translatePath(service.getAddonInfo('path'))) / 'resources')
        if resources not in sys.path:
            sys.path.insert(0, resources)
        from lib.trakt_outbox import Outbox
        root = Path(xbmcvfs.translatePath(service.getAddonInfo('profile')))
        deliver(store_path, Outbox(root / 'trakt_explicit_outbox.sqlite'), scope=scope)


def _catalog_binding_valid(root, profile, scope, kind):
    """Provider auth/source must match exactly; no inferred cross-account IDs."""
    try:
        import xbmcaddon
        from trakt_live_consumer import _catalog_scope_verified
        return _catalog_scope_verified([{'kind': kind}], root, profile,
                                       scope['provider_scope'],
                                       xbmcaddon.Addon('plugin.video.xstream-pro'))
    except (ImportError, OSError, ValueError, KeyError, TypeError, AttributeError):
        return False


def _capture_movie_identities(root, profile, scope, changes):
    """Attribute provider-specific seen flags using current immutable catalog IDs."""
    pending = [change for change in changes
               if str(change.get('identity', '')).isdigit()]
    if not pending or not _catalog_binding_valid(root, profile, scope, 'movie'):
        return
    try:
        from trakt_provider_index import verified_vod_records
        provider_ids = [change['identity'] for change in pending]
        records = verified_vod_records(root, profile=profile, provider_ids=provider_ids)
        owners = {}
        for record in records:
            owners.setdefault(str(record['provider_id']), []).append(record)
        for change in pending:
            hits = owners.get(change['identity'], [])
            if len(hits) == 1 and hits[0].get('ids'):
                change['external_identity'] = {'kind': 'movie', 'ids': hits[0]['ids']}
    except (ImportError, OSError, ValueError, KeyError, TypeError, AttributeError):
        return


def _capture_resume_identities(root, profile, scope, changes, after):
    """Capture only exact playback references, never URLs or credentials."""
    from urllib.parse import urlsplit
    for change in changes:
        if change.get('change') not in ('add', 'update'):
            continue
        # The native resume key contains a user-specific URL; use it only in
        # memory, and persist solely a validated catalog ID and percentage.
        matched = [row for key, row in after.items()
                   if isinstance(row, dict) and _hash(str(key)) ==
                   str(change.get('identity', '')).removeprefix('sha256:')]
        if len(matched) != 1:
            continue
        row = matched[0]
        if row.get('stype') not in ('movie', 'series'):
            continue
        url = row.get('url')
        if not isinstance(url, str):
            continue
        media = 'movie' if row['stype'] == 'movie' else 'episode'
        try:
            path = urlsplit(url).path
            match = re.search(r'/(?:movie|series)/[^/]+/[^/]+/([1-9][0-9]*)\.[A-Za-z0-9]+$', path)
        except ValueError:
            continue
        if not match or not _catalog_binding_valid(root, profile, scope, media):
            continue
        try:
            if media == 'movie':
                from trakt_provider_index import verified_vod_records
                records = verified_vod_records(root, profile=profile, provider_ids=[match.group(1)])
                if len(records) != 1 or str(records[0]['provider_id']) != match.group(1):
                    continue
                content = {'kind': 'movie', 'ids': records[0]['ids']}
            else:
                series = str(row.get('series_id') or '')
                season = str(row.get('season_num') or '')
                provider_episode = str(row.get('ep_id') or '')
                if (not series.isdigit() or not season.isdigit()
                        or not provider_episode.isdigit() or provider_episode != match.group(1)):
                    continue
                content = _episode_identity(root, profile, scope,
                                            [series, season, provider_episode])
                if content is None:
                    continue
                number = row.get('episode_num')
                if str(number) != str(content['episode']):
                    continue
        except (ImportError, OSError, ValueError, KeyError, TypeError, AttributeError):
            continue
        progress = change.get('percent')
        if type(progress) not in (int, float) or not 1 <= progress < 93:
            continue
        change['external_identity'] = content
        change['progress'] = round(float(progress), 5)


def _episode_identity(root, profile, scope, key):
    """Resolve at capture time using the same verified inventories as imports."""
    try:
        import xbmcaddon
        from trakt_live_consumer import _catalog_scope_verified
        from trakt_series_index import verified_show_records
        from trakt_episode_index import verified_episode_records
        from trakt_provider_index import read_object
        series, season, provider_episode = key
        if not all(str(value).isdigit() for value in key):
            return None
        addon = xbmcaddon.Addon('plugin.video.xstream-pro')
        if not _catalog_scope_verified([{'kind': 'episode'}], root, profile, scope['provider_scope'], addon):
            return None
        shows = [row for row in verified_show_records(root, profile=profile)
                 if str(row['provider_id']) == series]
        if len(shows) != 1:
            return None
        detail = read_object(root / ('data_cache_p%s_series_info_%s.json' % (profile, series))) or {}
        episodes = detail.get('episodes', {}).get(str(season), [])
        matches = [row for row in episodes if isinstance(row, dict)
                   and str(row.get('id')) == provider_episode]
        if len(matches) != 1 or not str(matches[0].get('episode_num', '')).isdigit():
            return None
        content = dict(kind='episode', ids=shows[0]['ids'], season=int(season),
                       episode=int(matches[0]['episode_num']))
        records = verified_episode_records(root, profile=profile,
            snapshot={'records': {'capture': {'identity': content}}}, show_records=shows)['records']
        if (len(records) == 1 and str(records[0]['provider_series_id']) == series
                and str(records[0]['provider_episode_id']) == provider_episode):
            return content
    except (ImportError, OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
    return None


def _consolidate_resume(db, event):
    """Keep immutable evidence, supersede only unsent, older single-item advances."""
    if (event.get('kind') != 'ResumePoints' or event.get('origin') != 'local'
            or not event.get('scope') or len(event.get('changes', [])) != 1):
        return
    latest = event['changes'][0]
    stamp = latest.get('timestamp')
    if type(stamp) not in (int, float) or not math.isfinite(stamp):
        return
    for identifier, raw in db.execute("SELECT id,event FROM changes WHERE state IN ('ready','quarantined')").fetchall():
        previous = json.loads(raw)
        changes = previous.get('changes', [])
        if (previous.get('kind') != 'ResumePoints' or previous.get('origin') != 'local'
                or previous.get('scope') != event['scope'] or len(changes) != 1):
            continue
        old = changes[0]
        old_stamp = old.get('timestamp')
        if (old.get('identity') == latest.get('identity')
                and type(old_stamp) in (int, float) and old_stamp >= stamp):
            return True
        if (old.get('identity') == latest.get('identity')
                and type(old_stamp) in (int, float) and old_stamp < stamp):
            previous['superseded_by'] = event['id']
            db.execute("UPDATE changes SET state='superseded',event=? WHERE id=?",
                       (json.dumps(previous, sort_keys=True), identifier))


def _capture_native_destinations(root, scope, changes):
    """Bind only new native events, using the current verified provider catalog."""
    import sys
    try:
        import xbmcaddon
        import xbmcvfs
        service = xbmcaddon.Addon('service.actweeter')
        resources = str(Path(xbmcvfs.translatePath(service.getAddonInfo('path'))) / 'resources')
        if resources not in sys.path:
            sys.path.insert(0, resources)
        from lib.collection_catalog import Catalog
        from trakt_live_consumer import _catalog_scope_verified
        from trakt_provider_index import verified_vod_records
        from trakt_series_index import verified_show_records
        path = Path(xbmcvfs.translatePath(service.getAddonInfo('profile'))) / 'collections_catalog.db'
        if not path.is_file() or path.is_symlink():
            return
        catalog = Catalog(path)
        with catalog._db() as db:
            mappings = [json.loads(row[0]) for row in db.execute('SELECT mappings FROM lists')]
        addon = xbmcaddon.Addon('plugin.video.xstream-pro')
        for change in changes:
            media = change.get('media_type')
            if media not in ('movie', 'series'):
                continue
            matches = [row['trakt_sync'] for row in mappings
                       if row.get('xstream_source', {}).get('folder_sha256') == change['folder_sha256']
                       and row.get('xstream_source', {}).get('media_type') == media
                       and row.get('trakt_sync', {}).get('scope') == scope]
            if len(matches) != 1:
                continue
            kind = 'movie' if media == 'movie' else 'show'
            if not _catalog_scope_verified([{'kind': kind}], root, scope['profile'], scope['provider_scope'], addon):
                continue
            provider_id = change['identity'][1]
            records = (verified_vod_records(root, profile=scope['profile'], provider_ids=[provider_id])
                       if media == 'movie' else verified_show_records(root, profile=scope['profile']))
            records = [row for row in records if str(row['provider_id']) == provider_id]
            if len(records) == 1:
                change['external_identity'] = dict(kind=kind, ids=records[0]['ids'])
                change['destination_capture'] = matches[0]
    except (ImportError, OSError, ValueError, sqlite3.Error):
        # No retrospective attribution: failed evidence keeps the event retained.
        return
