"""Transactional delta writes for the existing provider-only search schema.

The caller supplies a complete, successfully read provider snapshot for one
media type. This module never discovers titles and never performs networking.
"""

from __future__ import annotations

import sqlite3
import re
from dataclasses import dataclass
from typing import Iterable, Mapping


FIELDS = (
    "stype", "provider_id", "title", "norm", "year", "poster", "fanart",
    "plot", "genre", "rating", "category_id", "category_name",
)


@dataclass(frozen=True)
class Delta:
    scanned: int
    added: int
    changed: int
    removed: int


def open_store(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=15)
    conn.execute("PRAGMA busy_timeout=15000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS items (
            stype TEXT NOT NULL, provider_id TEXT NOT NULL, title TEXT NOT NULL,
            norm TEXT NOT NULL, year TEXT, poster TEXT, fanart TEXT, plot TEXT,
            genre TEXT, rating TEXT, category_id TEXT, category_name TEXT,
            PRIMARY KEY(stype, provider_id))"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS items_type_norm ON items(stype, norm)")
    return conn


def reconcile(conn: sqlite3.Connection, stype: str,
               records: Iterable[Mapping[str, object]], checkpoint: str,
               *, complete: bool) -> Delta:
    """Atomically reconcile one provider media type by its stable provider ID.

    Incomplete/failed reads are rejected before starting the transaction so a
    timeout cannot be misinterpreted as thousands of provider removals.
    """
    if stype not in ("movie", "series"):
        raise ValueError("unsupported provider media type")
    if not complete:
        raise ValueError("refusing to reconcile an incomplete provider snapshot")
    if (not isinstance(checkpoint, str) or not checkpoint or len(checkpoint) > 128
            or re.search(r"(?:https?://|@|password|token)", checkpoint, re.I)):
        raise ValueError("checkpoint must be an opaque, non-sensitive source stamp")

    prepared = {}
    for record in records:
        row = tuple(record.get(field) for field in FIELDS)
        if row[0] != stype or not row[1] or not row[2] or not row[3]:
            continue
        prepared[str(row[1])] = row

    conn.execute("BEGIN IMMEDIATE")
    try:
        previous = {
            str(row[0]): tuple(row[1:])
            for row in conn.execute(
                "SELECT provider_id,title,norm,year,poster,fanart,plot,genre,"
                "rating,category_id,category_name FROM items WHERE stype=?",
                (stype,),
            )
        }
        added = changed = 0
        upsert = "INSERT OR REPLACE INTO items VALUES (" + ",".join("?" for _ in FIELDS) + ")"
        for provider_id, row in prepared.items():
            old = previous.get(provider_id)
            values = tuple(row[2:])
            if old is None:
                added += 1
            elif old != values:
                changed += 1
            if old != values:
                conn.execute(upsert, row)

        removed_ids = previous.keys() - prepared.keys()
        if removed_ids:
            conn.executemany(
                "DELETE FROM items WHERE stype=? AND provider_id=?",
                ((stype, provider_id) for provider_id in removed_ids),
            )
        conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES (?,?)",
                     ("sync." + stype, str(checkpoint)))
        conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES (?,?)",
                     ("schema_version", "1"))
        conn.commit()
        return Delta(len(prepared), added, changed, len(removed_ids))
    except Exception:
        conn.rollback()
        raise
