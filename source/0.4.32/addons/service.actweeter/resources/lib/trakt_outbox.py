"""Durable explicit watched events, not a second playback scrobbler.

Only the service owns this queue. A POST whose outcome is unknown is never
retried automatically: Trakt does not guarantee idempotency for history writes.
"""
import hashlib
import json
import os
import re
import sqlite3
from pathlib import Path
from contextlib import contextmanager

from .trakt_sync import _timestamp, identity


class RetryLater(Exception):
    """Transport confirmed rejection without mutation, e.g. HTTP 429."""
    def __init__(self, seconds):
        self.seconds = max(1, min(int(seconds), 86400))


def watched_event(account, profile, content, watched_at):
    if not account or not str(profile).isdigit() or _timestamp(watched_at) is None:
        raise ValueError('explicit account/profile/date required')
    kind = content.get('kind')
    clean = identity(kind, content.get('ids'), show_ids=content.get('ids'),
                     season=content.get('season'), episode=content.get('episode'))
    if clean is None or kind not in ('movie', 'episode'):
        raise ValueError('verified movie or individual episode identity required')
    ids = {key: (value if key == 'imdb' else int(value)) for key, value in clean['ids'].items()}
    if kind == 'movie':
        payload = {'movies': [{'ids': ids, 'watched_at': watched_at}]}
    else:
        payload = {'shows': [{'ids': ids, 'seasons': [{'number': clean['season'],
                   'episodes': [{'number': clean['episode'], 'watched_at': watched_at}]}]}]}
    result = {'account': account, 'profile': str(profile), 'identity': clean,
              'watched_at': watched_at, 'payload': payload}
    result['id'] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    return result


def manual_event(account, profile, operation, content, nonce, watched_at=None, *, provider_scope, progress=None):
    """Build a bounded explicit action; distinct user actions retain distinct IDs."""
    if (not isinstance(account, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', account)
            or not re.fullmatch(r'[1-9][0-9]?', str(profile))):
        raise ValueError('explicit account and profile required')
    if not isinstance(provider_scope, str) or not re.fullmatch(r'[0-9a-f]{64}', provider_scope):
        raise ValueError('verified provider scope required')
    if not isinstance(nonce, str) or not re.fullmatch(r'[0-9a-f]{32}', nonce):
        raise ValueError('unique action ID required')
    supported = {'history.add', 'history.remove', 'watchlist.add', 'watchlist.remove',
                 'collection.add', 'collection.remove', 'favorites.add', 'favorites.remove',
                 'checkin', 'playback.pause'}
    personal_list = re.fullmatch(r'list\.([1-9][0-9]{0,18})\.(add|remove)', operation) if isinstance(operation, str) else None
    if (operation not in supported and personal_list is None) or not isinstance(content, dict):
        raise ValueError('unsupported explicit operation')
    kind = content.get('kind')
    clean = identity(kind, content.get('ids'), show_ids=content.get('ids'),
                     season=content.get('season'), episode=content.get('episode'))
    if clean is None:
        raise ValueError('verified identity required')
    ids = {key: value if key == 'imdb' else int(value) for key, value in clean['ids'].items()}
    item = {'ids': ids}
    if kind == 'episode':
        item['seasons'] = [{'number': clean['season'], 'episodes': [{'number': clean['episode']}]}]
    if operation == 'playback.pause':
        if (kind not in ('movie', 'episode') or watched_at is not None
                or type(progress) not in (int, float) or not 1 <= progress < 93):
            raise ValueError('bounded playback pause requires exact movie/episode identity')
        progress = round(float(progress), 5)
    elif progress is not None:
        raise ValueError('progress applies only to playback pause')
    if operation == 'history.add':
        if _timestamp(watched_at) is None or kind not in ('movie', 'episode'):
            raise ValueError('individual event and UTC timestamp required')
        if kind == 'episode':
            item['seasons'][0]['episodes'][0]['watched_at'] = watched_at
        else:
            item['watched_at'] = watched_at
    elif watched_at is not None:
        raise ValueError('timestamp only applies to watched events')
    if operation == 'playback.pause':
        endpoint = '/scrobble/pause'
        payload = {'progress': progress}
        if kind == 'movie':
            payload['movie'] = {'ids': ids}
        else:
            payload['show'] = {'ids': ids}
            payload['episode'] = {'season': clean['season'], 'number': clean['episode']}
    elif operation == 'checkin':
        if kind == 'show':
            raise ValueError('check-in requires a specific episode')
        endpoint = '/checkin'
        payload = {'movie': {'ids': ids}} if kind == 'movie' else {
            'show': {'ids': ids}, 'episode': {'season': clean['season'], 'number': clean['episode']}}
        payload['sharing'] = {'twitter': False, 'tumblr': False, 'medium': False}
    elif personal_list:
        endpoint = '/users/me/lists/' + personal_list.group(1) + '/items' + ('/remove' if personal_list.group(2) == 'remove' else '')
        payload = {'movies' if kind == 'movie' else 'shows': [item]}
    else:
        section, action = operation.split('.')
        endpoint = '/sync/' + section + ('/remove' if action == 'remove' else '')
        payload = {'movies' if kind == 'movie' else 'shows': [item]}
    event = {'schema': 2, 'account': account, 'profile': str(profile), 'operation': operation,
             'identity': clean, 'nonce': nonce, 'watched_at': watched_at, 'provider_scope': provider_scope,
             'endpoint': endpoint, 'payload': payload}
    if progress is not None:
        event['progress'] = progress
    event['id'] = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
    return event


class Outbox:
    def __init__(self, path):
        target = Path(path)
        if target.is_symlink() or target.parent.is_symlink() or (target.exists() and not target.is_file()):
            raise ValueError('unsafe outbox path')
        self.path = str(target)
        try:
            os.close(os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, 'O_NOFOLLOW', 0), 0o600))
        except FileExistsError:
            pass
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, event TEXT NOT NULL, '
                       'state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, retry_at REAL NOT NULL DEFAULT 0)')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    def retain_capture(self, *, source, source_id, fingerprint, reason):
        """Visible source evidence, never an implicitly authorized remote mutation."""
        if (source not in ('resume', 'collections', 'favorites')
                or not isinstance(source_id, str) or not re.fullmatch(r'[0-9a-f]{64}', source_id)
                or not isinstance(fingerprint, str) or not re.fullmatch(r'[0-9a-f]{64}', fingerprint)
                or reason not in ('identity_or_authority_unverified', 'scope_or_mapping_unverified')):
            raise ValueError('invalid retained capture')
        event = dict(schema=3, source=source, source_id=source_id, fingerprint=fingerprint, reason=reason)
        identifier = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
        event['id'] = identifier
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO events (id,event,state) VALUES (?,?,?)',
                       (identifier, json.dumps(event, sort_keys=True), 'retained'))
        return identifier

    def enqueue(self, event):
        # Rebuild at the trust boundary; arbitrary payloads/URLs are not accepted.
        expected = watched_event(event['account'], event['profile'], event['identity'], event['watched_at'])
        if event != expected:
            raise ValueError('event payload or identity modified')
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO events (id,event,state) VALUES (?,?,?)',
                       (event['id'], json.dumps(event, sort_keys=True), 'pending'))
        return event['id']

    def enqueue_manual(self, event, *, held=False):
        expected = manual_event(event['account'], event['profile'], event['operation'],
                                event['identity'], event['nonce'], event['watched_at'], provider_scope=event['provider_scope'],
                                progress=event.get('progress'))
        if event != expected:
            raise ValueError('manual action payload or identity modified')
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO events (id,event,state) VALUES (?,?,?)',
                       (event['id'], json.dumps(event, sort_keys=True), 'held' if held else 'pending'))
        return event['id']

    def send_manual(self, operation, *, account, profile, provider_scope, approved, post, now):
        if approved != operation:
            raise PermissionError('specific operation approval required')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT event,state,retry_at FROM events WHERE id=?', (operation,)).fetchone()
            if row is None:
                raise ValueError('unknown operation')
            event = json.loads(row[0])
            if (event.get('schema') != 2 or event['account'] != account
                    or event['profile'] != str(profile) or event.get('provider_scope') != provider_scope):
                raise PermissionError('account or profile changed')
            expected = manual_event(account, profile, event['operation'], event['identity'],
                                    event['nonce'], event['watched_at'], provider_scope=provider_scope,
                                    progress=event.get('progress'))
            if event != expected:
                raise ValueError('stored action changed')
            if row[1] not in ('pending', 'held') or row[2] > now:
                return row[1]
            db.execute('UPDATE events SET state=?, attempts=attempts+1 WHERE id=?', ('inflight', operation))
        state, retry_at = 'unknown', 0
        try:
            response = post(event['endpoint'], event['payload'])
            if isinstance(response, dict) and not any((response.get('not_found') or {}).values()):
                if event['operation'] == 'playback.pause':
                    remote = response.get('progress')
                    if (response.get('action') == 'pause'
                            and type(remote) in (int, float)
                            and abs(float(remote) - event['progress']) <= 0.5):
                        state = 'confirmed'
                elif event['operation'] == 'checkin':
                    if type(response.get('id')) is int and response['id'] > 0:
                        state = 'confirmed'
                else:
                    key = 'deleted' if event['operation'].endswith('.remove') else 'added'
                    counts = response.get(key, {})
                    item_key = {'movie': 'movies', 'episode': 'episodes', 'show': 'shows'}[event['identity']['kind']]
                    value = counts.get(item_key) if isinstance(counts, dict) else None
                    if type(value) is int and value == 1:
                        state = 'confirmed'
        except RetryLater as exc:
            state, retry_at = ('held' if row[1] == 'held' else 'pending'), now + exc.seconds
        except Exception:
            pass  # The server may have committed before the response was lost.
        with self.connect() as db:
            db.execute('UPDATE events SET state=?,retry_at=? WHERE id=? AND state=?',
                       (state, retry_at, operation, 'inflight'))
            return db.execute('SELECT state FROM events WHERE id=?', (operation,)).fetchone()[0]

    def pending_remote_watched(self, *, account, profile, provider_scope, now, limit=20):
        """Inspect authorized outgoing watched additions before a network POST.

        The caller must verify every target against a complete authenticated
        Trakt watched snapshot. No send occurs here and uncertain events are
        never replayed.
        """
        if type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError('invalid bounded watched batch size')
        selected = []
        with self.connect() as db:
            for identifier, raw in db.execute(
                    "SELECT id,event FROM events WHERE state='held' AND retry_at<=? ORDER BY rowid", (now,)):
                try:
                    event = json.loads(raw)
                    if (event.get('schema') != 2 or event.get('operation') != 'history.add'
                            or event.get('account') != account or event.get('profile') != str(profile)
                            or event.get('provider_scope') != provider_scope):
                        continue
                    if manual_event(account, profile, 'history.add', event['identity'],
                            event['nonce'], event['watched_at'], provider_scope=provider_scope) != event:
                        continue
                    selected.append((identifier, event['identity']))
                except (KeyError, TypeError, ValueError):
                    continue
                if len(selected) >= limit:
                    break
        return selected

    def mark_remote_already_watched(self, identifier, *, account, profile, provider_scope):
        """A complete remote GET is required by the caller before this method."""
        with self.connect() as db:
            row = db.execute('SELECT event,state FROM events WHERE id=?',(identifier,)).fetchone()
            if not row or row[1] != 'held':
                return False
            event = json.loads(row[0])
            if (event.get('account'), event.get('profile'), event.get('provider_scope'),
                    event.get('operation')) != (account, str(profile), provider_scope, 'history.add'):
                raise PermissionError('remote watched status bound to another account')
            db.execute('UPDATE events SET state=? WHERE id=? AND state=?',
                       ('confirmed',identifier,'held'))
        return True

    def pending_manual(self, *, account, profile, provider_scope, now, limit=5, include_held=False):
        """Return due explicit actions for this exact binding, never unknown sends."""
        if type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError('invalid pending-action limit')
        selected = []
        with self.connect() as db:
            rows = db.execute("SELECT id,event,state FROM events WHERE (state='pending' OR (state='held' AND ?)) AND retry_at<=? ORDER BY rowid", (include_held is True, now))
            for identifier, raw, state in rows:
                try:
                    event = json.loads(raw)
                    if not isinstance(event, dict):
                        continue
                    # Removals require an individual user decision in the experimental beta.
                    if str(event.get('operation', '')).endswith('.remove'):
                        continue
                    # Account-scoped export consent authorizes native manual
                    # watched changes and settled resume pauses. Playback
                    # scrobbling still belongs to the official script.trakt.
                    if (event.get('schema') == 2 and event.get('account') == account
                            and event.get('profile') == str(profile)
                            and event.get('provider_scope') == provider_scope
                            and event.get('operation') != 'checkin'):
                        expected = manual_event(account, profile, event['operation'], event['identity'],
                                                event['nonce'], event['watched_at'], provider_scope=provider_scope,
                                    progress=event.get('progress'))
                        if expected == event and identifier == event['id']:
                            selected.append(identifier)
                except (KeyError, TypeError, ValueError):
                    continue
                if len(selected) == limit:
                    break
        return selected

    @contextmanager
    def import_guard(self, *, account, profile, provider_scope):
        """Serialize remote projection with local intent creation for this binding."""
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            rows = db.execute("SELECT event,state FROM events WHERE state IN ('held','pending','inflight','unknown','confirmed')").fetchall()
            intents = []
            for raw, state in rows:
                try:
                    event = json.loads(raw)
                    if (not isinstance(event, dict) or not isinstance(event.get('account'), str)
                            or not isinstance(event.get('profile'), str)):
                        raise ValueError('invalid queued action')
                    if event.get('account') != account or event.get('profile') != str(profile):
                        continue
                    if event.get('schema') == 2:
                        if event.get('provider_scope') != provider_scope:
                            continue
                        action = event.get('operation')
                        if action not in ('history.add', 'history.remove', 'playback.pause'):
                            continue
                        # A confirmed removal still protects against an older remote snapshot.
                        if state == 'confirmed' and action != 'history.remove':
                            continue
                        expected = manual_event(account, profile, action, event['identity'],
                                                event['nonce'], event['watched_at'], provider_scope=provider_scope,
                                    progress=event.get('progress'))
                    else:
                        if state == 'confirmed':
                            continue
                        expected = watched_event(account, profile, event['identity'], event['watched_at'])
                    if expected != event:
                        raise ValueError('queued action failed integrity validation')
                    intents.append(event['identity'])
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError('unsafe pending action; remote import deferred') from exc
            def conflict(operation):
                item = operation.get('identity')
                if not isinstance(item, dict) or not isinstance(item.get('ids'), dict):
                    return True
                for intent in intents:
                    kind = intent.get('kind')
                    if kind != item.get('kind') and not (kind == 'show' and item.get('kind') == 'episode'):
                        continue
                    if kind == 'episode' and (intent.get('season'), intent.get('episode')) != (item.get('season'), item.get('episode')):
                        continue
                    common = set(intent['ids']) & set(item['ids'])
                    if common and any(intent['ids'][key] == item['ids'][key] for key in common):
                        return True
                return False
            yield conflict

    def status(self, operation):
        with self.connect() as db:
            row = db.execute('SELECT state,attempts FROM events WHERE id=?', (operation,)).fetchone()
        return None if row is None else {'state': row[0], 'attempts': row[1]}

    def confirm_from_snapshot(self, operation, snapshot, *, account, profile, provider_scope=None):
        """Resolve an uncertain POST only from a complete authenticated GET snapshot."""
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT event,state FROM events WHERE id=?', (operation,)).fetchone()
            if row is None:
                raise ValueError('unknown operation')
            event = json.loads(row[0])
            if (snapshot['account'] != account or event['account'] != account
                    or event['profile'] != str(profile)):
                raise PermissionError('account/profile changed')
            # A partial or unauthenticated history must never resolve an uncertain POST.
            if (snapshot.get('complete') is not True or
                    not isinstance(snapshot.get('history'), list)):
                raise ValueError('complete authenticated history snapshot required')
            if event.get('schema') == 2 and event.get('provider_scope') != provider_scope:
                raise PermissionError('provider scope changed')
            if event.get('schema') == 2 and event.get('operation') != 'history.add':
                raise ValueError('history snapshot cannot confirm this action')
            expected = event['identity']
            for history in snapshot['history']:
                actual = history['identity']
                if any(actual.get(key) != expected.get(key) for key in ('kind', 'season', 'episode')):
                    continue
                common = set(actual['ids']) & set(expected['ids'])
                if (common and all(actual['ids'][key] == expected['ids'][key] for key in common)
                        and _timestamp(history['watched_at']) == _timestamp(event['watched_at'])):
                    db.execute('UPDATE events SET state=? WHERE id=?', ('confirmed', operation))
                    return 'confirmed'
        return row[1]

    def send(self, operation, *, account, profile, approved, post, now):
        """Caller supplies a separately authorized operation ID and native transport.

        No worker invokes this automatically. An approval for another operation,
        account or profile cannot authorize this one.
        """
        if approved != operation:
            raise PermissionError('specific operation approval required')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT event,state,retry_at FROM events WHERE id=?', (operation,)).fetchone()
            if row is None:
                raise ValueError('unknown operation')
            event = json.loads(row[0])
            if event['account'] != account or event['profile'] != str(profile):
                raise PermissionError('account/profile changed')
            if row[1] != 'pending' or row[2] > now:
                return row[1]
            db.execute('UPDATE events SET state=?, attempts=attempts+1 WHERE id=?', ('inflight', operation))
        # Persist inflight before the network call, including across process death.
        state, retry_at = 'unknown', 0
        try:
            response = post('/sync/history', event['payload'])
            key = 'movies' if event['identity']['kind'] == 'movie' else 'episodes'
            added = response.get('added', {}) if isinstance(response, dict) else {}
            if (type(added.get(key)) is int and added[key] == 1
                    and not any((response.get('not_found') or {}).values())):
                state = 'confirmed'
        except RetryLater as exc:
            state, retry_at = 'pending', now + exc.seconds
        except Exception:
            # Connection loss can happen after a successful server-side commit.
            pass
        with self.connect() as db:
            db.execute('UPDATE events SET state=?, retry_at=? WHERE id=? AND state=?',
                       (state, retry_at, operation, 'inflight'))
            row = db.execute('SELECT state FROM events WHERE id=?', (operation,)).fetchone()
        return row[0]
