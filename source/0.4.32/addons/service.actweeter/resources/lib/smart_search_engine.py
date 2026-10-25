"""Read-only, accent/word-order tolerant search over XStream's existing index.

No provider requests, credentials, playback or new persistent catalogue. The
small title index lives for one search window; artwork/plots are read on demand.
"""
from __future__ import annotations

import bisect
from collections import defaultdict
from contextlib import contextmanager
from difflib import SequenceMatcher
import re
import sqlite3
import unicodedata
from pathlib import Path


STOP_WORDS = frozenset(
    "a al ante bajo con contra de del desde durante en entre hacia hasta la las lo los "
    "mediante para por sin sobre tras un una unos unas y the of a an and with in on at to by for from".split()
)
MAX_QUERY = 160


def normalize(value):
    text = unicodedata.normalize("NFKD", str(value or "")).casefold()
    return " ".join(re.findall(r"[^\W_]+", "".join(
        c for c in text if not unicodedata.combining(c)), re.UNICODE))


def words(value):
    tokens = normalize(value).split()
    return tuple(dict.fromkeys(t for t in tokens if t not in STOP_WORDS)) or tuple(tokens)


def title_words(title, year):
    cleaned = re.sub(r"\[(?:es|en|lat|multi|hd|fhd|uhd|4k|1080p|2160p)\]", " ", str(title), flags=re.I)
    tokens = words(cleaned)
    technical = {"hd", "fhd", "uhd", "4k", "1080p", "720p", "2160p", "bluray"}
    return tuple(t for t in tokens if t not in technical and
                 not (len(tokens) > 1 and str(year)[:4] == t))


def unique_rows(rows):
    """Collapse confirmed identities or same-title/year editions, never unknown remakes."""
    output, seen = [], set()
    for row in rows:
        if row.get("tmdb_id"):
            key = row["kind"], "tmdb", str(row["tmdb_id"]), bool(row.get("available"))
        elif row.get("year") and row["kind"] in ("movie", "series"):
            key = row["kind"], title_words(row["title"], row["year"]), str(row["year"])[:4]
        else:
            key = row["kind"], str(row["id"])
        if key not in seen:
            output.append(row)
            seen.add(key)
    return output


def trigrams(value):
    return {value[i:i + 3] for i in range(max(1, len(value) - 2))}


@contextmanager
def readonly(path):
    conn = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=1)
    conn.execute("PRAGMA query_only=ON")
    try:
        yield conn
    finally:
        conn.close()


def provider_path(kind, identity, profile):
    """These are XStream's existing premium/search result destinations."""
    from urllib.parse import urlencode
    if kind not in ("movie", "series") or not str(identity).isdigit():
        raise ValueError("invalid provider identity")
    if type(profile) is not int or not 1 <= profile <= 10:
        raise ValueError("invalid provider profile")
    params = ({"mode": "xtream_series", "series_id": str(identity)} if kind == "series"
              else {"mode": "premium", "view": "play", "stype": "movie", "id": str(identity)})
    return "plugin://plugin.video.xstream-pro/?" + urlencode(dict(params, profile_num=profile))


class CatalogSearch:
    def __init__(self, path, profile):
        self.path, self.profile = Path(path), profile
        self.rows, self.inverted, self.grams = [], defaultdict(set), defaultdict(set)
        self.signature = None
        self.vocabulary = []

    def fork(self):
        """Share a completed immutable title snapshot; refresh replaces, never edits it."""
        view = CatalogSearch(self.path, self.profile)
        view.rows, view.inverted, view.grams = self.rows, self.inverted, self.grams
        view.vocabulary, view.signature = self.vocabulary, self.signature
        return view

    def refresh(self):
        stat = self.path.stat()
        wal = Path(str(self.path) + "-wal")
        signature = (stat.st_size, stat.st_mtime_ns,
                     wal.stat().st_mtime_ns if wal.exists() else 0)
        if signature == self.signature:
            return
        with readonly(self.path) as db:
            rows = db.execute("SELECT stype,provider_id,title,year FROM items "
                              "WHERE stype IN ('movie','series')").fetchall()
        inverted, grams = defaultdict(set), defaultdict(set)
        prepared = []
        for row in rows:
            if not str(row[1]).isdigit():
                continue
            tokens = title_words(row[2], row[3])
            index = len(prepared)
            prepared.append((*row, tokens))
            for token in tokens:
                inverted[token].add(index)
        for token in inverted:
            for gram in trigrams(token):
                grams[gram].add(token)
        self.rows, self.inverted, self.grams = prepared, inverted, grams
        self.vocabulary, self.signature = sorted(inverted), signature

    def _token_matches(self, token, prefix=True, fuzzy=True):
        matches = {token: 1.0} if token in self.inverted else {}
        if prefix:
            start = bisect.bisect_left(self.vocabulary, token)
            for candidate in self.vocabulary[start:start + 80]:
                if not candidate.startswith(token):
                    break
                matches.setdefault(candidate, 0.93)
        if fuzzy and len(token) >= 4:
            pool = set()
            for gram in trigrams(token):
                pool.update(self.grams.get(gram, ()))
            # A bounded candidate set keeps typo handling out of the UI's hot path.
            pool = sorted(pool, key=lambda t: (-len(trigrams(t) & trigrams(token)), t))[:100]
            for candidate in pool:
                if abs(len(candidate) - len(token)) > 2:
                    continue
                score = SequenceMatcher(None, token, candidate).ratio()
                if score >= 0.78:
                    matches.setdefault(candidate, score * 0.86)
        return matches

    def search(self, query, limit=30):
        self.refresh()
        tokens = words(str(query)[:MAX_QUERY])
        if not tokens:
            return []
        candidates, quality = None, {}
        for fuzzy in (False, True):
            candidates, quality = None, {}
            for offset, token in enumerate(tokens):
                matches = self._token_matches(token, prefix=offset == len(tokens) - 1, fuzzy=fuzzy)
                indexes = set()
                for match, score in matches.items():
                    for index in self.inverted[match]:
                        indexes.add(index)
                        quality[index, offset] = max(quality.get((index, offset), 0), score)
                candidates = indexes if candidates is None else candidates & indexes
                if not candidates:
                    break
            if candidates:
                break
        if not candidates:
            return []
        confidence = {index: sum(quality[index, i] for i in range(len(tokens))) / len(tokens)
                      for index in candidates}
        if fuzzy:
            best = max(confidence.values())
            candidates = {i for i in candidates if confidence[i] >= best - 0.055}
        phrase = normalize(query)
        def rank(index):
            row = self.rows[index]
            exact = normalize(row[2]) == phrase
            canonical = row[4] == tokens
            leading = " ".join(row[4]).startswith(" ".join(tokens))
            score = sum(quality[index, i] for i in range(len(tokens))) / len(tokens)
            return (-int(exact), -int(canonical), -int(leading), -score, len(row[4]), normalize(row[2]), row[1])
        selected = sorted(candidates, key=rank)
        counts, chosen = defaultdict(int), []
        for index in selected:
            row = self.rows[index]
            if counts[row[0]] < limit:
                chosen.append(row)
                counts[row[0]] += 1
            if len(chosen) >= limit * 2:
                break
        return unique_rows(self.details(chosen))

    def details(self, selected):
        if not selected:
            return []
        output = []
        with readonly(self.path) as db:
            clauses = " OR ".join("(stype=? AND provider_id=?)" for _ in selected)
            params = tuple(value for row in selected for value in row[:2])
            details = {(row[0], str(row[1])): row[2:] for row in db.execute(
                "SELECT stype,provider_id,poster,fanart,plot,genre,rating FROM items WHERE "
                + clauses, params)}
            identities = {}
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                          "AND name='identity_matches'").fetchone():
                identities = {(kind, str(identifier)): tmdb_id
                              for kind, identifier, tmdb_id in db.execute(
                                  "SELECT m.stype,m.provider_id,m.tmdb_id "
                                  "FROM identity_matches m JOIN items i ON "
                                  "m.stype=i.stype AND m.provider_id=i.provider_id "
                                  "AND m.title_key=i.norm AND m.year=i.year "
                                  "WHERE " + clauses.replace("stype=?", "m.stype=?").replace(
                                      "provider_id=?", "m.provider_id=?"), params)}
            for kind, identity, title, year, _tokens in selected:
                row = details.get((kind, str(identity)))
                if row is not None:
                    item = dict(kind=kind, id=str(identity), title=title, year=year,
                        poster=row[0] or "", fanart=row[1] or "", plot=row[2] or "",
                        genre=row[3] or "", rating=row[4] or "", available=True,
                        path=provider_path(kind, identity, self.profile))
                    cached = identities.get((kind, str(identity)))
                    if cached and str(cached).isdigit():
                        item["tmdb_id"] = str(cached)
                    output.append(item)
        return output

    def remember_tmdb(self, item):
        """Keep a profile-local visual identity in the existing provider index."""
        kind, identifier = item.get("kind"), str(item.get("id") or "")
        tmdb_id, year = str(item.get("tmdb_id") or ""), str(item.get("year") or "")
        if (kind not in ("movie", "series") or not identifier.isdigit()
                or not tmdb_id.isdigit() or not re.fullmatch(r"\d{4}", year)
                or not normalize(item.get("title"))):
            return False
        try:
            with sqlite3.connect(self.path, timeout=1) as db:
                current = db.execute("SELECT title,norm,year FROM items "
                                     "WHERE stype=? AND provider_id=?", (kind, identifier)).fetchone()
                if not current or current[0] != item["title"] or str(current[2]) != year:
                    return False
                db.execute("CREATE TABLE IF NOT EXISTS identity_matches ("
                           "stype TEXT NOT NULL, provider_id TEXT NOT NULL, "
                           "title_key TEXT NOT NULL, year TEXT NOT NULL, tmdb_id TEXT NOT NULL, "
                           "PRIMARY KEY(stype,provider_id,title_key,year))")
                db.execute("INSERT OR IGNORE INTO identity_matches VALUES (?,?,?,?,?)",
                           (kind, identifier, current[1], year, tmdb_id))
            return True
        except sqlite3.OperationalError:
            return False

    def match_metadata(self, items):
        """Match canonical metadata to provider titles without inventing availability.

        Do not map approximate homonyms/remakes to a playable item. Query typos
        may be fuzzy; the metadata-to-provider identity join must be conservative.
        """
        self.refresh()
        selected, metadata = [], {}
        for item in items:
            kind = item.get("kind")
            if kind not in ("movie", "series"):
                continue
            for name in (item.get("title"), item.get("originaltitle"), *item.get("aliases", ())):
                tokens = words(name)
                if not tokens:
                    continue
                matches = set.intersection(*(self.inverted.get(t, set()) for t in tokens))
                eligible = [self.rows[index] for index in sorted(matches)
                            if self.rows[index][0] == kind and set(self.rows[index][4]) == set(tokens)]
                if not item.get("year") and len({str(row[3]) for row in eligible}) > 1:
                    continue
                for row in eligible:
                    if row[0] != kind or set(row[4]) != set(tokens):
                        continue
                    year, provider_year = str(item.get("year") or "")[:4], str(row[3] or "")[:4]
                    if year and year != provider_year:
                        continue
                    key = row[0], str(row[1])
                    if key not in metadata:
                        selected.append(row)
                        metadata[key] = item
        result = self.details(selected)
        for row in result:
            extra = metadata[row["kind"], row["id"]]
            row["canonical_title"] = extra.get("title") or row["title"]
            row["tmdb_id"] = row.get("tmdb_id") or extra.get("tmdb_id", "")
            for key in ("poster", "fanart", "plot"):
                if extra.get(key):
                    row[key] = extra[key]
        return unique_rows(result)


class LatestRequest:
    """One running job plus one replaceable pending job; stale results never paint."""
    def __init__(self):
        import threading
        self.condition = threading.Condition()
        self.generation, self.pending, self.closed = 0, None, False

    def submit(self, value):
        with self.condition:
            self.generation += 1
            self.pending = (self.generation, value)
            self.condition.notify()
            return self.generation

    def take(self):
        with self.condition:
            self.condition.wait_for(lambda: self.closed or self.pending is not None)
            job, self.pending = self.pending, None
            return None if self.closed else job

    def invalidate(self):
        with self.condition:
            self.generation += 1
            self.pending = None

    def current(self, generation):
        with self.condition:
            return not self.closed and generation == self.generation

    def close(self):
        with self.condition:
            self.closed, self.pending = True, None
            self.condition.notify_all()
