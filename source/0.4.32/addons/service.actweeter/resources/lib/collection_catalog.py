"""Stable cross-service list identities and safe automatic creation plans.

Plans are inert: adapters must authorize, create, read back and persist the
returned remote ID before any membership synchronization. No name-based merges.
"""
import hashlib
import json
import os
import re
import math
import sqlite3
import uuid
from contextlib import contextmanager

SERVICES = ('trakt', 'tmdb')


def _name(value):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 120:
        raise ValueError('list name must contain 1..120 characters')
    return value.strip()


def _runtime_scope():
    try:
        import sys
        import xbmcaddon
        import xbmcvfs
        from pathlib import Path
        addon=xbmcaddon.Addon('plugin.video.xstream-pro')
        library=str(Path(xbmcvfs.translatePath(addon.getAddonInfo('path'))) / 'resources/lib')
        if library not in sys.path:
            sys.path.insert(0,library)
        import trakt_local_journal as journal
        root=Path(xbmcvfs.translatePath(addon.getAddonInfo('profile')))
        with journal.runtime_scope(root/'favorites_1.json'):
            scope=getattr(journal._origin,'scope',None)
            return dict(scope) if scope else None
    except (ImportError,OSError,ValueError,AttributeError):
        return None


class Catalog:
    def __init__(self, path):
        self.path = str(path)
        if os.path.islink(self.path):
            raise ValueError('catalog symlink not allowed')
        if not os.path.exists(self.path):
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(fd)
        with self._db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS lists (local_id TEXT PRIMARY KEY, '
                       'name TEXT NOT NULL, kind TEXT NOT NULL, mappings TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS members (local_id TEXT NOT NULL, '
                       'kind TEXT NOT NULL, tmdb_id INTEGER NOT NULL, title TEXT NOT NULL, '
                       'PRIMARY KEY(local_id,kind,tmdb_id), '
                       'FOREIGN KEY(local_id) REFERENCES lists(local_id))')
            db.execute('CREATE TABLE IF NOT EXISTS changes (id INTEGER PRIMARY KEY AUTOINCREMENT, '
                       'local_id TEXT NOT NULL, operation TEXT NOT NULL, kind TEXT, '
                       'tmdb_id INTEGER, origin TEXT NOT NULL, created_at TEXT NOT NULL '
                       "DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')), status TEXT NOT NULL DEFAULT 'pending')")
            db.execute('CREATE TABLE IF NOT EXISTS remote_state (local_id TEXT PRIMARY KEY, revision TEXT NOT NULL, timestamp REAL NOT NULL, members TEXT NOT NULL)')
            db.execute('BEGIN IMMEDIATE')
            if 'capture' not in {row[1] for row in db.execute('PRAGMA table_info(changes)')}:
                db.execute('ALTER TABLE changes ADD COLUMN capture TEXT')

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def configure_destination(self, identifier, *, scope, destination, verified, confirmed):
        if verified is not True or confirmed is not True:
            raise PermissionError('verified destination and explicit confirmation required')
        if (not isinstance(scope, dict) or set(scope) != {'account','profile','provider_scope','kodi_profile','generation'}
                or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', str(scope['account']))
                or not re.fullmatch(r'[1-9][0-9]?', str(scope['profile']))
                or any(not re.fullmatch(r'[0-9a-f]{64}', str(scope[key])) for key in ('provider_scope','kodi_profile','generation'))):
            raise ValueError('invalid mapping scope')
        if destination not in ('watchlist','collection','favorites') and not re.fullmatch(r'list\.[1-9][0-9]{0,18}', str(destination)):
            raise ValueError('invalid destination')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT mappings FROM lists WHERE local_id=?',(identifier,)).fetchone()
            if row is None:
                raise ValueError('unknown collection')
            mappings=json.loads(row[0])
            mappings['trakt_sync']={'scope':dict(scope),'destination':destination,'revision':uuid.uuid4().hex}
            db.execute('UPDATE lists SET mappings=? WHERE local_id=?',(json.dumps(mappings,sort_keys=True),identifier))
        return mappings['trakt_sync']

    def _capture_destination(self, db, identifier, scope, origin):
        if origin != 'local' or scope is None:
            return
        row=db.execute('SELECT mappings FROM lists WHERE local_id=?',(identifier,)).fetchone()
        mapping=json.loads(row[0]).get('trakt_sync')
        if isinstance(mapping,dict) and mapping.get('scope') == scope:
            db.execute('UPDATE changes SET capture=? WHERE id=last_insert_rowid()',
                       (json.dumps(mapping,sort_keys=True),))

    def confirmed_changes(self, outbox):
        """Capture acknowledgements before reading the remote snapshot."""
        with self._db() as db:
            rows = db.execute("SELECT id,status FROM changes WHERE status LIKE 'queued:%'").fetchall()
        return {identifier for identifier,status in rows
                if (outbox.status(status.split(':',1)[1]) or {}).get('state') == 'confirmed'}

    def apply_remote(self, identifier, *, scope, revision, items, observed_at, complete, confirmed=()):
        if complete is not True or type(observed_at) not in (int,float) or not math.isfinite(observed_at) or observed_at <= 0:
            raise ValueError('complete timestamped remote snapshot required')
        incoming={}
        for item in items:
            kind, tmdb=item.get('kind'),item.get('tmdb_id')
            if kind not in ('movie','show') or type(tmdb) is not int or tmdb < 1:
                raise ValueError('verified remote identity required')
            key=kind+':'+str(tmdb)
            if key in incoming:
                raise ValueError('duplicate remote identity')
            incoming[key]=(kind,tmdb,_name(item.get('title')))
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT mappings,kind FROM lists WHERE local_id=?',(identifier,)).fetchone()
            if row is None:
                raise ValueError('unknown collection')
            mapping=json.loads(row[0]).get('trakt_sync',{})
            if mapping.get('scope') != scope or mapping.get('revision') != revision:
                raise PermissionError('mapping changed during remote read')
            if any(row[1] not in ('mixed',value[0]) for value in incoming.values()):
                raise ValueError('remote media type incompatible')
            previous=db.execute('SELECT revision,timestamp,members FROM remote_state WHERE local_id=?',(identifier,)).fetchone()
            if previous and previous[0]==revision and observed_at <= previous[1]:
                return {'stale':True,'added':0,'removed':0}
            owned=set(json.loads(previous[2])) if previous and previous[0]==revision else set()
            # Release local intent only when both the queue and a later snapshot agree.
            for change_id,operation,kind,tmdb,status,capture in db.execute(
                    "SELECT id,operation,kind,tmdb_id,status,capture FROM changes WHERE local_id=? AND status LIKE 'queued:%'", (identifier,)).fetchall():
                if change_id not in confirmed or not capture or json.loads(capture).get('revision') != revision:
                    continue
                key=str(kind)+':'+str(tmdb)
                if (operation == 'member_add' and key in incoming) or (operation == 'member_remove' and key not in incoming):
                    db.execute('UPDATE changes SET status=? WHERE id=?',
                               ('confirmed:'+status.split(':',1)[1],change_id))
                    if operation == 'member_add':
                        owned.add(key)
            pending={str(kind)+':'+str(tmdb) for kind,tmdb in db.execute(
                "SELECT kind,tmdb_id FROM changes WHERE local_id=? AND origin='local' AND status!='observed' AND status NOT LIKE 'confirmed:%'",(identifier,))}
            removed=owned-set(incoming)-pending
            if len(removed)>20:
                raise PermissionError('large remote removal requires explicit review')
            added=deleted=0
            for key,value in incoming.items():
                if key in pending:
                    continue
                cursor=db.execute('INSERT OR IGNORE INTO members VALUES (?,?,?,?)',(identifier,*value))
                if cursor.rowcount:
                    owned.add(key);added+=1
                    db.execute("INSERT INTO changes (local_id,operation,kind,tmdb_id,origin,status) VALUES (?,?,?,?, 'trakt_import','observed')",(identifier,'member_add',value[0],value[1]))
            for key in removed:
                kind,tmdb=key.split(':')
                cursor=db.execute('DELETE FROM members WHERE local_id=? AND kind=? AND tmdb_id=?',(identifier,kind,int(tmdb)))
                deleted+=cursor.rowcount
                db.execute("INSERT INTO changes (local_id,operation,kind,tmdb_id,origin,status) VALUES (?,?,?,?, 'trakt_import','observed')",(identifier,'member_remove',kind,int(tmdb)))
                owned.discard(key)
            db.execute('INSERT OR REPLACE INTO remote_state VALUES (?,?,?,?)',(identifier,revision,observed_at,json.dumps(sorted(owned))))
        return {'stale':False,'added':added,'removed':deleted}

    def handoff_changes(self, outbox):
        # Historical changes lack captured account/provider scope: retain, never rebind.
        with self._db() as db:
            rows = db.execute("SELECT id,local_id,operation,kind,tmdb_id,origin,created_at,capture FROM changes WHERE status='pending'").fetchall()
        for row in rows:
            if row[5] != 'local':
                continue
            if row[7] and row[2] in ('member_add','member_remove'):
                mapping=json.loads(row[7]); scope=mapping['scope']
                from lib.trakt_outbox import manual_event
                event=manual_event(scope['account'],scope['profile'],
                    mapping['destination']+('.add' if row[2]=='member_add' else '.remove'),
                    {'kind':row[3],'ids':{'tmdb':row[4]}},
                    hashlib.sha256((str(row[1])+':'+str(row[0])+':'+mapping['revision']).encode()).hexdigest()[:32],
                    provider_scope=scope['provider_scope'])
                receipt=outbox.enqueue_manual(event,held=True)
                with self._db() as db:
                    db.execute("UPDATE changes SET status=? WHERE id=? AND status='pending'",('queued:'+receipt,row[0]))
                continue
            receipt = outbox.retain_capture(source='collections',
                source_id=hashlib.sha256((str(row[1]) + ':' + str(row[0])).encode()).hexdigest(),
                fingerprint=hashlib.sha256(json.dumps(row).encode()).hexdigest(), reason='scope_or_mapping_unverified')
            with self._db() as db:
                db.execute("UPDATE changes SET status=? WHERE id=? AND status='pending'", ('retained:' + receipt, row[0]))

    def create_local(self, name, *, kind='mixed', origin=None):
        if origin != 'mis_colecciones':
            raise PermissionError('only Mis Colecciones may create synced lists')
        title = _name(name)
        if kind not in ('movie', 'show', 'mixed'):
            raise ValueError('unsupported list kind')
        identifier = str(uuid.uuid4())
        with self._db() as db:
            db.execute('INSERT INTO lists VALUES (?,?,?,?)',
                       (identifier, title, kind, '{}'))
            db.execute('INSERT INTO changes (local_id,operation,kind,origin) VALUES (?,?,?,?)',
                       (identifier, 'list_create', kind, 'local'))
        return identifier

    def get(self, identifier):
        with self._db() as db:
            row = db.execute('SELECT name,kind,mappings FROM lists WHERE local_id=?',
                             (identifier,)).fetchone()
        if row is None:
            raise ValueError('unknown local list')
        return {'id': identifier, 'name': row[0], 'kind': row[1], 'mappings': json.loads(row[2])}

    def plan_creation(self, identifier, *, connected, automatic_creation):
        """Never write if consent is off or account connection is unverified."""
        entry = self.get(identifier)
        if automatic_creation is not True:
            return []
        return [{'service': service, 'local_id': identifier, 'name': entry['name'],
                 'kind': entry['kind']}
                for service in SERVICES if connected.get(service) is True
                and service not in entry['mappings']]

    def confirm_remote(self, identifier, service, remote_id, *, account, verified):
        """Bind only a readback-verified remote ID scoped to the real account."""
        if service not in SERVICES or verified is not True or not isinstance(account, str) or not account.strip():
            raise ValueError('verified account-scoped mapping required')
        if not isinstance(remote_id, (str, int)) or not str(remote_id).strip():
            raise ValueError('remote list ID required')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT mappings FROM lists WHERE local_id=?', (identifier,)).fetchone()
            if row is None:
                raise ValueError('unknown local list')
            mappings = json.loads(row[0])
            target = {'account': account, 'remote_id': str(remote_id)}
            if service in mappings and mappings[service] != target:
                raise ValueError('existing mapping cannot be silently rebound')
            mappings[service] = target
            db.execute('UPDATE lists SET mappings=? WHERE local_id=?',
                       (json.dumps(mappings, sort_keys=True), identifier))
        return target

    def rename_local(self, identifier, name):
        """Stable identity survives a rename; remote rename requires separate verified operations."""
        title = _name(name)
        with self._db() as db:
            row = db.execute('SELECT name FROM lists WHERE local_id=?', (identifier,)).fetchone()
            if row is None:
                raise ValueError('unknown local list')
            if row[0] != title:
                db.execute('UPDATE lists SET name=? WHERE local_id=?', (title, identifier))
                db.execute('INSERT INTO changes (local_id,operation,origin) VALUES (?,?,?)',
                           (identifier, 'list_rename', 'local'))

    def add_member(self, identifier, *, kind, tmdb_id, title, origin='local', scope=None):
        """Add verified portable identity; local only, no remote side effects."""
        if kind not in ('movie', 'show') or type(tmdb_id) is not int or tmdb_id < 1:
            raise ValueError('verified movie or show TMDb ID required')
        if origin not in ('local', 'trakt_import'):
            raise ValueError('invalid list change origin')
        name = _name(title)
        scope = _runtime_scope() if scope is None else scope
        entry = self.get(identifier)
        if entry['kind'] not in ('mixed', kind):
            raise ValueError('media type incompatible with list')
        with self._db() as db:
            cursor = db.execute('INSERT OR IGNORE INTO members VALUES (?,?,?,?)',
                                (identifier, kind, tmdb_id, name))
            if cursor.rowcount:
                db.execute('INSERT INTO changes (local_id,operation,kind,tmdb_id,origin,status) VALUES (?,?,?,?,?,?)',
                           (identifier, 'member_add', kind, tmdb_id, origin,
                            'observed' if origin == 'trakt_import' else 'pending'))
                self._capture_destination(db, identifier, scope, origin)


    def members(self, identifier):
        self.get(identifier)
        with self._db() as db:
            rows = db.execute('SELECT kind,tmdb_id,title FROM members WHERE local_id=? '
                              'ORDER BY title COLLATE NOCASE,kind,tmdb_id', (identifier,)).fetchall()
        return [{'kind': kind, 'tmdb_id': tmdb_id, 'title': title}
                for kind, tmdb_id, title in rows]

    def remove_member(self, identifier, *, kind, tmdb_id, origin='local', scope=None):
        scope = _runtime_scope() if scope is None else scope
        self.get(identifier)
        if origin not in ('local', 'trakt_import'):
            raise ValueError('invalid list change origin')
        if kind not in ('movie', 'show') or type(tmdb_id) is not int or tmdb_id < 1:
            raise ValueError('invalid member identity')
        with self._db() as db:
            cursor = db.execute('DELETE FROM members WHERE local_id=? AND kind=? AND tmdb_id=?',
                                (identifier, kind, tmdb_id))
            if cursor.rowcount:
                db.execute('INSERT INTO changes (local_id,operation,kind,tmdb_id,origin,status) VALUES (?,?,?,?,?,?)',
                           (identifier, 'member_remove', kind, tmdb_id, origin,
                            'observed' if origin == 'trakt_import' else 'pending'))
                self._capture_destination(db, identifier, scope, origin)
