"""Stable cross-service list identities and safe automatic creation plans.

Plans are inert: adapters must authorize, create, read back and persist the
returned remote ID before any membership synchronization. No name-based merges.
"""
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager

SERVICES = ('trakt', 'tmdb')


def _name(value):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 120:
        raise ValueError('list name must contain 1..120 characters')
    return value.strip()


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

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def create_local(self, name, *, kind='mixed'):
        title = _name(name)
        if kind not in ('movie', 'show', 'mixed'):
            raise ValueError('unsupported list kind')
        identifier = str(uuid.uuid4())
        with self._db() as db:
            db.execute('INSERT INTO lists VALUES (?,?,?,?)',
                       (identifier, title, kind, '{}'))
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
            cursor = db.execute('UPDATE lists SET name=? WHERE local_id=?', (title, identifier))
            if cursor.rowcount != 1:
                raise ValueError('unknown local list')
