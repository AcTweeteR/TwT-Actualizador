"""Provider snapshot worker; adapter must return a complete provider-only set."""

from __future__ import annotations

import time

from search_store import open_store, reconcile
from sync_scheduler import DEFAULT_INTERVAL_SECONDS, is_due


class SearchWorker:
    def __init__(self, db_path, snapshot_provider, *, catalogue="xtream",
                 interval=DEFAULT_INTERVAL_SECONDS, clock=time.time, metrics=None):
        if catalogue != "xtream":
            raise ValueError("V1.1 Search accepts only the Xtream provider catalogue")
        self.db_path = db_path
        self.snapshot_provider = snapshot_provider
        self.interval = interval
        self.clock = clock
        self.metrics = metrics or (lambda _event: None)

    def run_if_due(self, monitor):
        conn = open_store(self.db_path)
        try:
            meta = dict(conn.execute("SELECT key,value FROM meta"))
            last_success = float(meta.get("last_successful_sync", "0") or 0)
            if monitor.abortRequested() or not is_due(last_success, self.clock(), self.interval):
                return None

            started = self.clock()
            totals = {"scanned": 0, "added": 0, "changed": 0, "removed": 0}
            for stype in ("movie", "series"):
                if monitor.abortRequested():
                    return None
                records, checkpoint, complete = self.snapshot_provider(stype, monitor)
                if monitor.abortRequested():
                    return None
                delta = reconcile(conn, stype, records, checkpoint, complete=complete)
                for key in totals:
                    totals[key] += getattr(delta, key)

            duration_ms = max(0, int((self.clock() - started) * 1000))
            conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES (?,?)",
                         ("last_successful_sync", str(self.clock())))
            conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES (?,?)",
                         ("last_sync_duration_ms", str(duration_ms)))
            conn.commit()
            event = dict(totals, duration_ms=duration_ms, outcome="success")
            self.metrics(event)
            return event
        except Exception:
            conn.rollback()
            self.metrics({"outcome": "error"})
            raise
        finally:
            conn.close()
