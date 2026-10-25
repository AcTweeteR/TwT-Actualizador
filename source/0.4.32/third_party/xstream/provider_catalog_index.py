"""Small, rebuildable SQLite index over XStream's authoritative JSON catalog."""
import hashlib
import json
import mmap
import os
import re
import sqlite3
import time
from contextlib import closing
from urllib.parse import quote


_JSON_STRING = re.compile(rb'"[^"\\]*(?:\\.[^"\\]*)*"')
_JSON_TOKEN = re.compile(rb'"[^"\\]*(?:\\.[^"\\]*)*"|[{}\[\]]')


class IndexUnavailable(ValueError):
    def __init__(self, state):
        self.state = state
        super().__init__(state)


class BuildCancelled(ValueError):
    pass


def _connect(path):
    return sqlite3.connect('file:' + quote(os.path.abspath(path), safe='/') + '?mode=ro',
                           uri=True, timeout=0.05)


def _string_end(raw, pos):
    match = _JSON_STRING.match(raw, pos)
    if match is None:
        raise ValueError('unterminated JSON string')
    return match.end()


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
    for token in _JSON_TOKEN.finditer(raw, pos + 1):
        char = raw[token.start()]
        if char == 34:
            continue
        if char == 123:
            stack.append(125)
        elif char == 91:
            stack.append(93)
        elif char in (125, 93):
            if stack.pop() != char:
                raise ValueError('unbalanced JSON')
        if not stack:
            return token.end()
    raise ValueError('incomplete JSON value')


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
    def __init__(self, catalog_path, source, profile, stype, *, build=False,
                 trace=None, cancel=None, rebuild=False):
        self.catalog_path = catalog_path
        self.profile, self.stype = profile, stype
        self.stamp = _stamp(catalog_path, source, profile, stype)
        self.path = catalog_path + '.idx-' + self.stamp[4][:16] + '.sqlite'
        self.trace = trace
        state = self._state()
        self.reused = state == 'valid' and not rebuild
        self.invalidated = os.path.exists(self.path) and not self.reused
        if trace is not None:
            trace.count('index.' + state)
        if not self.reused:
            if not build:
                raise IndexUnavailable(state)
            self._ensure(source, cancel)
        with closing(_connect(self.path)) as db:
            self.item_count = db.execute('SELECT COUNT(*) FROM items').fetchone()[0]

    def _ensure(self, source, cancel):
        started = time.perf_counter()
        phases = dict.fromkeys(('source', 'scan', 'decode', 'fields', 'insert'), 0.0)
        trace = self.trace
        def check_cancel():
            if cancel is not None and cancel():
                raise BuildCancelled('cancelled')
        check_cancel()
        if trace is not None:
            trace.count('index.build.started')
        temporary = self.path + '.tmp-' + str(os.getpid()) + '-' + str(time.time_ns())
        connection = None
        try:
            phase = time.perf_counter()
            connection = sqlite3.connect(temporary)
            connection.execute('BEGIN')
            connection.execute('CREATE TABLE items (ordinal INTEGER PRIMARY KEY, id TEXT, norm TEXT, year TEXT, category TEXT, category_value TEXT, tmdb TEXT, added INTEGER, start INTEGER, length INTEGER)')
            if trace is not None:
                trace.timing('index.build.tables', (time.perf_counter() - phase) * 1000)
            rows = []
            row_count = 0
            with open(self.catalog_path, 'rb') as source_file:
                if not os.fstat(source_file.fileno()).st_size:
                    raise ValueError('empty catalog')
                with mmap.mmap(source_file.fileno(), 0, access=mmap.ACCESS_READ) as raw:
                    phase = time.perf_counter() if trace is not None else 0
                    if _provider_source(raw) != source:
                        raise ValueError('catalog provider does not match')
                    if trace is not None:
                        phases['source'] += time.perf_counter() - phase
                    spans = iter(_catalog_spans(raw))
                    while True:
                        phase = time.perf_counter() if trace is not None else 0
                        try:
                            start, end = next(spans)
                        except StopIteration:
                            break
                        if trace is not None:
                            phases['scan'] += time.perf_counter() - phase
                            phase = time.perf_counter()
                        item = json.loads(raw[start:end].decode('utf-8'))
                        if trace is not None:
                            phases['decode'] += time.perf_counter() - phase
                            phase = time.perf_counter()
                        if not isinstance(item, dict):
                            raise ValueError('invalid catalog item')
                        ident = item.get('stream_id') or item.get('series_id') or ''
                        try:
                            added = int(float(item.get('added') or 0))
                        except (ValueError, TypeError, OverflowError):
                            added = 0.0
                        rows.append((row_count, str(ident), _norm(item.get('name')), str(item.get('year') or ''),
                            str(item.get('category_id', '')), str(item.get('category_id')),
                            str(item.get('tmdb_id') or item.get('tmdb') or ''), added,
                            start, end - start))
                        row_count += 1
                        if trace is not None:
                            phases['fields'] += time.perf_counter() - phase
                        if len(rows) == 512:
                            check_cancel()
                            phase = time.perf_counter() if trace is not None else 0
                            connection.executemany('INSERT INTO items VALUES (?,?,?,?,?,?,?,?,?,?)', rows)
                            if trace is not None:
                                phases['insert'] += time.perf_counter() - phase
                            rows = []
            if rows:
                phase = time.perf_counter() if trace is not None else 0
                connection.executemany('INSERT INTO items VALUES (?,?,?,?,?,?,?,?,?,?)', rows)
                if trace is not None:
                    phases['insert'] += time.perf_counter() - phase
            check_cancel()
            phase = time.perf_counter()
            connection.execute('CREATE INDEX recent ON items(added DESC)')
            connection.execute('CREATE INDEX identity ON items(norm, year)')
            if trace is not None:
                trace.timing('index.build.sql_indexes', (time.perf_counter() - phase) * 1000)
            connection.execute('CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)')
            connection.executemany('INSERT INTO meta VALUES (?,?)',
                                   [(str(i), value) for i, value in enumerate(self.stamp)])
            phase = time.perf_counter()
            connection.commit()
            if trace is not None:
                trace.timing('index.build.commit', (time.perf_counter() - phase) * 1000)
            phase = time.perf_counter()
            if connection.execute('PRAGMA quick_check(1)').fetchone()[0] != 'ok':
                raise ValueError('index integrity check failed')
            if connection.execute('SELECT COUNT(*) FROM items').fetchone()[0] != row_count:
                raise ValueError('index row count mismatch')
            if trace is not None:
                trace.timing('index.build.validate', (time.perf_counter() - phase) * 1000)
            phase = time.perf_counter()
            connection.close()
            connection = None
            if trace is not None:
                trace.timing('index.build.close', (time.perf_counter() - phase) * 1000)
            check_cancel()
            if _stamp(self.catalog_path, source, self.profile, self.stype) != self.stamp:
                raise BuildCancelled('catalog changed')
            phase = time.perf_counter()
            os.replace(temporary, self.path)
            if trace is not None:
                trace.timing('index.build.publish', (time.perf_counter() - phase) * 1000)
                trace.count('index.build.rows', row_count)
                trace.count('index.build.storage_bytes', os.path.getsize(self.path))
        except Exception:
            if connection is not None:
                connection.close()
            if trace is not None:
                trace.count('index.build.failed')
            for path in (temporary, temporary + '-journal'):
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
            raise
        finally:
            if trace is not None:
                for name, seconds in phases.items():
                    trace.timing('index.build.' + name, seconds * 1000)
                trace.timing('index.build.duration', (time.perf_counter() - started) * 1000)

    def _state(self):
        if not os.path.isfile(self.path):
            return 'missing'
        try:
            with closing(_connect(self.path)) as db:
                saved = tuple(value for _key, value in db.execute(
                    'SELECT key,value FROM meta ORDER BY CAST(key AS INTEGER)'))
                db.execute('SELECT id,norm,year,category,category_value,tmdb,added,ordinal,start,length FROM items LIMIT 0')
                if {row[1] for row in db.execute('PRAGMA index_list(items)')} != {'recent', 'identity'}:
                    return 'invalid'
                return 'valid' if saved == self.stamp else 'stale'
        except (sqlite3.Error, OSError):
            return 'invalid'

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

    def search(self, query, blocked_categories=(), hidden_ids=(), limit=48):
        """Find visible catalog items using the shared SQLite catalog index.

        Uses bounded SQLite substring matching in original catalog order;
        never loads the full provider JSON catalog.
        """
        term = _norm(query)
        if not term:
            return []
        limit = min(100, max(1, int(limit)))
        with closing(_connect(self.path)) as db:
            db.execute('CREATE TEMP TABLE blocked(value TEXT PRIMARY KEY)')
            db.execute('CREATE TEMP TABLE hidden(value TEXT PRIMARY KEY)')
            db.executemany('INSERT OR IGNORE INTO blocked VALUES (?)',
                           [(str(value),) for value in blocked_categories])
            db.executemany('INSERT OR IGNORE INTO hidden VALUES (?)',
                           [(str(value),) for value in hidden_ids])
            visible = ('NOT EXISTS (SELECT 1 FROM blocked b WHERE b.value=i.category) '
                       'AND NOT EXISTS (SELECT 1 FROM hidden h WHERE h.value=i.id)')
            # Preserve catalog ordinal ordering for substring searches.
            # Prefix-first ranking would silently change Smart Search results.
            escaped = term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            rows = db.execute('SELECT i.id,i.start,i.length FROM items i WHERE '
                + visible + " AND i.norm LIKE ? ESCAPE '\\' ORDER BY i.ordinal LIMIT ?",
                ('%' + escaped + '%', limit)).fetchall()
        return self._read_items(rows)

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


_REQUEST_PREFIX = 'catalog-index-request-'


def _write_request(path, payload):
    temporary = path + '.tmp-' + str(os.getpid()) + '-' + str(time.time_ns())
    try:
        with open(temporary, 'w', encoding='utf-8') as stream:
            json.dump(payload, stream, separators=(',', ':'))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def schedule_rebuild(catalog_path, source, profile, stype, trace=None):
    """Persist a credential-free request; the existing XStream service owns its lifetime."""
    stamp = _stamp(catalog_path, source, profile, stype)
    generation = hashlib.sha256(json.dumps(stamp).encode()).hexdigest()[:24]
    path = os.path.join(os.path.dirname(catalog_path), _REQUEST_PREFIX + generation + '.json')
    if os.path.exists(path):
        return False
    _write_request(path, {'catalog': os.path.basename(catalog_path), 'profile': int(profile),
                        'stype': stype, 'stamp': list(stamp),
                        'not_before': time.time() + 5, 'attempts': 0})
    if trace is not None:
        trace.count('index.rebuild.scheduled')
    return True


class IndexBuildWorker:
    """One idle, cancellable worker owned by XStream's already resident service."""
    def __init__(self, profile_dir, *, idle, cancelled, trace_factory=None):
        import threading
        self.profile_dir = profile_dir
        self.idle = idle
        self.cancelled = cancelled
        self.trace_factory = trace_factory
        self.stopping = threading.Event()
        self.thread = None
        self.next_poll = 0

    def tick(self):
        import threading
        if self.stopping.is_set() or (self.thread is not None and self.thread.is_alive()):
            return
        if time.monotonic() < self.next_poll:
            return
        self.next_poll = time.monotonic() + 5
        if not self.idle():
            return
        try:
            with os.scandir(self.profile_dir) as entries:
                if not any(entry.name.startswith(_REQUEST_PREFIX) and entry.name.endswith('.json')
                           for entry in entries):
                    return
        except OSError:
            return
        self.thread = threading.Thread(target=self.run_pending, name='XStreamCatalogIndex', daemon=True)
        self.thread.start()

    def close(self):
        self.stopping.set()
        if self.thread is not None:
            self.thread.join(timeout=2)

    def _cancel(self):
        return self.stopping.is_set() or self.cancelled()

    def run_pending(self):
        """Also callable synchronously by deterministic tests and diagnostics."""
        if self._cancel() or not self.idle():
            return
        trace = None
        try:
            import fcntl
            with open(os.path.join(self.profile_dir, 'catalog-index-builder.lock'), 'a') as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    return
                for name in sorted(os.listdir(self.profile_dir)):
                    if not re.fullmatch(_REQUEST_PREFIX + r'[a-f0-9]{24}\.json', name):
                        continue
                    path = os.path.join(self.profile_dir, name)
                    if os.path.islink(path):
                        continue
                    try:
                        with open(path, encoding='utf-8') as stream:
                            payload = json.loads(stream.read(4096))
                        catalog = payload['catalog']
                        if (os.path.basename(catalog) != catalog or not catalog.endswith('.json')
                                or type(payload['profile']) is not int or payload['profile'] < 1
                                or payload['stype'] != 'movie' or len(payload['stamp']) != 5):
                            raise ValueError('invalid build request')
                        if payload['not_before'] > time.time():
                            continue
                    except (OSError, ValueError, KeyError, TypeError):
                        os.remove(path)
                        continue
                    trace = self.trace_factory() if self.trace_factory is not None else None
                    self._build_request(path, payload, trace)
                    break
        except Exception:
            if trace is not None:
                trace.count('index.build.failed')
        finally:
            if trace is not None:
                trace.emit()

    def _build_request(self, request_path, payload, trace):
        catalog_path = os.path.join(self.profile_dir, payload['catalog'])
        try:
            self._check_cancel()
            with open(catalog_path, 'rb') as stream:
                with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as raw:
                    source = _provider_source(raw)
            if _stamp(catalog_path, source, payload['profile'], payload['stype']) != tuple(payload['stamp']):
                if trace is not None:
                    trace.count('index.stale')
                os.remove(request_path)
                return
            prefix = os.path.basename(catalog_path) + '.idx-' + payload['stamp'][4][:16] + '.sqlite.tmp-'
            for name in os.listdir(self.profile_dir):
                if name.startswith(prefix):
                    os.remove(os.path.join(self.profile_dir, name))
            CatalogIndex(catalog_path, source, payload['profile'], payload['stype'],
                         build=True, trace=trace, cancel=self._cancel, rebuild=True)
            if trace is not None:
                trace.count('index.rebuild.completed')
            os.remove(request_path)
        except Exception as exc:
            if trace is not None:
                trace.count('index.build.cancelled' if isinstance(exc, BuildCancelled)
                            else 'index.rebuild.failed')
            payload['attempts'] = min(int(payload.get('attempts', 0)) + 1, 10)
            payload['not_before'] = time.time() + min(300, 5 * 2 ** payload['attempts'])
            _write_request(request_path, payload)

    def _check_cancel(self):
        if self._cancel():
            raise BuildCancelled('cancelled')
