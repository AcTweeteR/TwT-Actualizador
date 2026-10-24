"""Durable, fail-closed synchronization checkpoints for account collections.

Never interprets an absent or incomplete snapshot as an empty collection.
Only confirmed, fully verified reads may advance the baseline. This module
never sends network requests or stores credentials.
"""
import json
import os
import sqlite3
from contextlib import contextmanager

from .triple_collections import COLLECTIONS, SOURCES, snapshot, delta


class Journal:
    def __init__(self, path):
        self.path = str(path)
        if os.path.islink(self.path):
            raise ValueError('journal symlink not allowed')
        if not os.path.exists(self.path):
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(fd)
        with self._db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS checkpoints ('
                       'account TEXT NOT NULL, source TEXT NOT NULL, collection TEXT NOT NULL,'
                       'payload TEXT NOT NULL, PRIMARY KEY(account,source,collection))')

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, account, source, collection):
        self._validate(account, source, collection)
        with self._db() as db:
            row = db.execute('SELECT payload FROM checkpoints WHERE account=? AND source=? AND collection=?',
                             (account, source, collection)).fetchone()
        if row is None:
            return None
        state = json.loads(row[0])
        if (state['account'], state['source'], state['collection'], state['complete']) != (account, source, collection, True):
            raise ValueError('corrupted checkpoint scope')
        return state

    @staticmethod
    def _validate(account, source, collection):
        if not isinstance(account, str) or not account or source not in SOURCES or collection not in COLLECTIONS:
            raise ValueError('invalid checkpoint scope')

    def observe(self, account, source, collection, rows, *, complete, verified, approved=False):
        """Read-only plan by default. Advance only on explicitly approved readback."""
        self._validate(account, source, collection)
        if verified is not True or complete is not True:
            raise ValueError('only complete verified observations are accepted')
        state = snapshot(source, collection, rows, account=account, complete=complete)
        previous = self.get(account, source, collection)
        change = None if previous is None else delta(previous, state, source=source)
        if approved is True:
            with self._db() as db:
                db.execute('INSERT INTO checkpoints(account,source,collection,payload) VALUES (?,?,?,?) '
                           'ON CONFLICT(account,source,collection) DO UPDATE SET payload=excluded.payload',
                           (account, source, collection, json.dumps(state, sort_keys=True)))
        return {'baseline_exists': previous is not None, 'changes': change,
                'committed': approved is True, 'count': len(state['items'])}
