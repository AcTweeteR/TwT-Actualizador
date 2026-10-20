"""Small, rebuildable SQLite index over XStream's authoritative JSON catalog."""
import hashlib
import json
import mmap
import os
import sqlite3
import time
from contextlib import closing


def _string_end(raw, pos):
    pos += 1
    while pos < len(raw):
        if raw[pos] == 92:
            pos += 2
        elif raw[pos] == 34:
            return pos + 1
        else:
            pos += 1
    raise ValueError('unterminated JSON string')


def _value_end(raw, pos):
    while pos < len(raw) and raw[pos] in b' \t\r\n':
        pos += 1
    if pos >= len(raw):
        raise ValueError('missing JSON value')
    if raw[pos] == 34:
        return _string_end(raw, pos)
    if raw[pos] not in (123, 91):
        end = pos
        while end < len(raw) and raw[end] not in b',}] \t\r\n':
            end += 1
        return end
    stack = [125 if raw[pos] == 123 else 93]
    pos += 1
    while pos < len(raw) and stack:
        char = raw[pos]
        if char == 34:
            pos = _string_end(raw, pos)
            continue
        if char == 123:
            stack.append(125)
        elif char == 91:
            stack.append(93)
        elif char in (125, 93):
            if stack.pop() != char:
                raise ValueError('unbalanced JSON')
        pos += 1
    if stack:
        raise ValueError('incomplete JSON value')
    return pos


def _catalog_spans(raw):
    """Yield byte offsets for objects in the top-level _data array."""
    pos = 0
    if raw[pos:pos + 1] != b'{':
        raise ValueError('catalog root is not an object')
    pos += 1
    array_start = None
    while pos < len(raw):
        while raw[pos] in b' \t\r\n,':
            pos += 1
        if raw[pos] == 125:
            break
        if raw[pos] != 34:
            raise ValueError('invalid catalog object key')
        key_end = _string_end(raw, pos)
        key = json.loads(raw[pos:key_end].decode('utf-8'))
        pos = key_end
        while raw[pos] in b' \t\r\n':
            pos += 1
        if raw[pos] != 58:
            raise ValueError('missing catalog key separator')
        pos += 1
        while raw[pos] in b' \t\r\n':
            pos += 1
        if key == '_data':
            if raw[pos] != 91:
                raise ValueError('catalog data is not a list')
            array_start = pos + 1
            break
        pos = _value_end(raw, pos)
    if array_start is None:
        raise ValueError('catalog data missing')
    pos = array_start
    while pos < len(raw):
        while raw[pos] in b' \t\r\n,':
            pos += 1
        if raw[pos] == 93:
            return
        start = pos
        pos = _value_end(raw, pos)
        if raw[start:start + 1] != b'{':
            raise ValueError('catalog item is not an object')
        yield start, pos
    raise ValueError('unterminated catalog list')


def _provider_source(raw):
    pos = 1
    while pos < len(raw):
        while raw[pos] in b' \t\r\n,':
            pos += 1
        if raw[pos] == 125:
            break
        end = _string_end(raw, pos)
        key = json.loads(raw[pos:end].decode('utf-8'))
        pos = end
        while raw[pos] in b' \t\r\n':
            pos += 1
        if raw[pos] != 58:
            raise ValueError('invalid catalog metadata')
        pos += 1
        while raw[pos] in b' \t\r\n':
            pos += 1
        end = _value_end(raw, pos)
        if key == '_src':
            return json.loads(raw[pos:end].decode('utf-8'))
        pos = end
    return None


def _norm(value):
    import re
    import unicodedata
    value = re.sub(r'\s*\(\d{4}\)\s*$', '', str(value or ''))
    value = unicodedata.normalize('NFKD', value).casefold()
    return ''.join(char for char in value if char.isalnum())


def _stamp(path, source, profile, stype):
    stat = os.stat(path)
    return (str(stat.st_size), str(getattr(stat, 'st_mtime_ns', int(stat.st_mtime * 1e9))),
            str(getattr(stat, 'st_ino', 0)), '2', hashlib.sha256(
                (str(profile) + '\0' + source + '\0' + stype).encode('utf-8')).hexdigest())


class CatalogIndex:
    def __init__(self, catalog_path, source, profile, stype):
        self.catalog_path = catalog_path
        self.stamp = _stamp(catalog_path, source, profile, stype)
        self.path = catalog_path + '.idx-' + self.stamp[4][:16] + '.sqlite'
        self.reused = self._valid()
        self.invalidated = os.path.exists(self.path) and not self.reused
        self._ensure(source, self.reused)
        with closing(sqlite3.connect(self.path, timeout=0.2)) as db:
            self.item_count = db.execute('SELECT COUNT(*) FROM items').fetchone()[0]

    def _ensure(self, source, valid):
        if valid:
            return
        temporary = self.path + '.tmp-' + str(os.getpid()) + '-' + str(time.time_ns())
        connection = sqlite3.connect(temporary)
        try:
            connection.execute('CREATE TABLE items (ordinal INTEGER PRIMARY KEY, id TEXT, norm TEXT, year TEXT, category TEXT, category_value TEXT, tmdb TEXT, added INTEGER, start INTEGER, length INTEGER)')
            connection.execute('CREATE INDEX recent ON items(added DESC)')
            connection.execute('CREATE INDEX identity ON items(norm, year)')
            rows = []
            with open(self.catalog_path, 'rb') as source_file:
                if not os.fstat(source_file.fileno()).st_size:
                    raise ValueError('empty catalog')
                with mmap.mmap(source_file.fileno(), 0, access=mmap.ACCESS_READ) as raw:
                    if _provider_source(raw) != source:
                        raise ValueError('catalog provider does not match')
                    for ordinal, (start, end) in enumerate(_catalog_spans(raw)):
                        item = json.loads(raw[start:end].decode('utf-8'))
                        if not isinstance(item, dict):
                            raise ValueError('invalid catalog item')
                        ident = item.get('stream_id') or item.get('series_id') or ''
                        try:
                            added = int(float(item.get('added') or 0))
                        except (ValueError, TypeError, OverflowError):
                            added = 0.0
                        rows.append((ordinal, str(ident), _norm(item.get('name')), str(item.get('year') or ''),
                            str(item.get('category_id', '')), str(item.get('category_id')),
                            str(item.get('tmdb_id') or item.get('tmdb') or ''), added,
                            start, end - start))
                        if len(rows) == 512:
                            connection.executemany('INSERT INTO items VALUES (?,?,?,?,?,?,?,?,?,?)', rows)
                            rows = []
            if rows:
                connection.executemany('INSERT INTO items VALUES (?,?,?,?,?,?,?,?,?,?)', rows)
            connection.execute('CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)')
            connection.executemany('INSERT INTO meta VALUES (?,?)',
                                   [(str(i), value) for i, value in enumerate(self.stamp)])
            connection.commit()
        except Exception:
            connection.close()
            for path in (temporary, temporary + '-journal'):
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
            raise
        else:
            connection.close()
        try:
            os.replace(temporary, self.path)
        except Exception:
            for path in (temporary, temporary + '-journal'):
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
            raise

    def _valid(self):
        try:
            with closing(sqlite3.connect(self.path, timeout=0.2)) as db:
                return tuple(value for _key, value in db.execute(
                    'SELECT key,value FROM meta ORDER BY CAST(key AS INTEGER)')) == self.stamp
        except (sqlite3.Error, OSError):
            return False

    def _read_items(self, rows):
        with open(self.catalog_path, 'rb') as stream:
            stat = os.fstat(stream.fileno())
            current = (str(stat.st_size), str(getattr(stat, 'st_mtime_ns', int(stat.st_mtime * 1e9))),
                       str(getattr(stat, 'st_ino', 0)))
            if current != self.stamp[:3]:
                raise ValueError('catalog changed during indexed read')
            items = []
            for _ident, start, length in rows:
                stream.seek(start)
                items.append(json.loads(stream.read(length).decode('utf-8')))
            return items

    def _rows(self, mode, blocked_categories=(), hidden_ids=(), category='',
              provider_id='', browse=False, page=1, limit=24):
        start = (max(1, int(page)) - 1) * min(48, max(1, int(limit)))
        size = min(48, max(1, int(limit)))
        needed = start + size + 1
        dedupe = not browse and not provider_id
        with closing(sqlite3.connect(self.path, timeout=0.2)) as db:
            db.execute('CREATE TEMP TABLE blocked(value TEXT PRIMARY KEY)')
            db.execute('CREATE TEMP TABLE hidden(value TEXT PRIMARY KEY)')
            db.executemany('INSERT OR IGNORE INTO blocked VALUES (?)',
                           [(str(value),) for value in blocked_categories])
            db.executemany('INSERT OR IGNORE INTO hidden VALUES (?)',
                           [(str(value),) for value in hidden_ids])
            clause = ('NOT EXISTS (SELECT 1 FROM blocked b WHERE b.value=i.category) '
                      'AND NOT EXISTS (SELECT 1 FROM hidden h WHERE h.value=i.id)')
            args = []
            if category:
                clause += ' AND i.category_value=?'
                args.append(str(category))
            if provider_id:
                clause += ' AND i.id=?'
                args.append(str(provider_id))
            if mode == 'recent':
                clause += ' AND i.added>0'
                order = 'i.added DESC,i.ordinal'
            else:
                order = 'i.ordinal'
            cursor = db.execute('SELECT i.id,i.norm,i.year,i.start,i.length FROM items i WHERE '
                                + clause + ' ORDER BY ' + order, args)
            rows, seen = [], set()
            for ident, norm, year, offset, length in cursor:
                identity = (norm, year)
                if dedupe and identity in seen:
                    continue
                seen.add(identity)
                rows.append((ident, offset, length))
                if len(rows) == needed:
                    break
        has_more = len(rows) > start + size
        return rows[start:start + size], has_more

    def page(self, mode='catalog', blocked_categories=(), hidden_ids=(), category='', provider_id='',
             browse=False, page=1, limit=24):
        rows, has_more = self._rows(mode, blocked_categories, hidden_ids, category,
                                 provider_id, browse, page, limit)
        return self._read_items(rows), has_more

    def ranked(self, ranks, blocked_categories=(), hidden_ids=(), category='',
               provider_id='', browse=False, page=1, limit=24):
        """Resolve cached Trakt ranks to visible provider items, as the old path did."""
        selected = []
        used = set()
        with closing(sqlite3.connect(self.path, timeout=0.2)) as db:
            db.execute('CREATE TEMP TABLE blocked(value TEXT PRIMARY KEY)')
            db.execute('CREATE TEMP TABLE hidden(value TEXT PRIMARY KEY)')
            db.executemany('INSERT OR IGNORE INTO blocked VALUES (?)',
                           [(str(value),) for value in blocked_categories])
            db.executemany('INSERT OR IGNORE INTO hidden VALUES (?)',
                           [(str(value),) for value in hidden_ids])
            visible = ('NOT EXISTS (SELECT 1 FROM blocked b WHERE b.value=i.category) '
                       'AND NOT EXISTS (SELECT 1 FROM hidden h WHERE h.value=i.id)')
            for rank in ranks:
                target = str(rank.get('tmdb_id') or '')
                titles = sorted({_norm(title) for title in rank.get('titles', []) if title})
                clauses, args = [], []
                if target:
                    clauses.append('i.tmdb=?')
                    args.append(target)
                if rank.get('year') and titles:
                    clauses.append('(i.year=? AND i.norm IN (' + ','.join('?' for _ in titles) + '))')
                    args.extend([str(rank['year'])] + titles)
                if not clauses:
                    continue
                matches = ' AND ' + visible + ' AND (' + ' OR '.join(clauses) + ')'
                identities = db.execute(
                    'SELECT COUNT(*) FROM (SELECT DISTINCT i.norm,i.year FROM items i '
                    'WHERE 1=1' + matches + ')', args).fetchone()[0]
                if identities != 1:
                    continue
                row = db.execute('SELECT i.id,i.start,i.length FROM items i WHERE 1=1'
                    + matches + ' ORDER BY i.ordinal LIMIT 1', args).fetchone()
                if row and row[0] not in used:
                    selected.append(row)
                    used.add(row[0])
        matched_items = self._read_items(selected)
        items = []
        for item in matched_items:
            if category and str(item.get('category_id')) != str(category):
                continue
            if provider_id and str(item.get('stream_id') or item.get('series_id') or '') != str(provider_id):
                continue
            items.append(item)
        if not browse and not provider_id:
            seen, unique = set(), []
            for item in items:
                identity = (_norm(item.get('name')), str(item.get('year') or ''))
                if identity not in seen:
                    seen.add(identity)
                    unique.append(item)
            items = unique
        offset = (max(1, int(page)) - 1) * min(48, max(1, int(limit)))
        size = min(48, max(1, int(limit)))
        return items[offset:offset + size], len(items) > offset + size
