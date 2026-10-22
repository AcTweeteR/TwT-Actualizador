"""Durable explicit watched events, not a second playback scrobbler.

Only the service owns this queue. A POST whose outcome is unknown is never
retried automatically: Trakt does not guarantee idempotency for history writes.
"""
import hashlib
import json
import os
import sqlite3
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


class Outbox:
    def __init__(self, path):
        self.path = str(path)
        try:
            os.close(os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
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

    def enqueue(self, event):
        # Rebuild at the trust boundary; arbitrary payloads/URLs are not accepted.
        expected = watched_event(event['account'], event['profile'], event['identity'], event['watched_at'])
        if event != expected:
            raise ValueError('event payload or identity modified')
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO events (id,event,state) VALUES (?,?,?)',
                       (event['id'], json.dumps(event, sort_keys=True), 'pending'))
        return event['id']

    def status(self, operation):
        with self.connect() as db:
            row = db.execute('SELECT state,attempts FROM events WHERE id=?', (operation,)).fetchone()
        return None if row is None else {'state': row[0], 'attempts': row[1]}

    def confirm_from_snapshot(self, operation, snapshot, *, account, profile):
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
            db.execute('UPDATE events SET state=?, retry_at=? WHERE id=?', (state, retry_at, operation))
        return state
