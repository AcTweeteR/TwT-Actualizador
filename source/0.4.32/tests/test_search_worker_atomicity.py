"""End-to-end SQLite worker transaction tests with a fake provider."""
import sqlite3
from contextlib import closing
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'addons/service.actweeter/resources/lib'))
from search_worker import SearchWorker
from search_store import open_store, reconcile


def item(stype, provider_id):
    return dict(stype=stype,provider_id=provider_id,title='Example '+provider_id,
                norm='example '+provider_id,year='2026',poster='',fanart='',plot='',
                genre='',rating='',category_id='',category_name='')


class WorkerAtomicityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name)/'index.sqlite')
        self.monitor = Mock()
        self.monitor.abortRequested.return_value = False

    def rows(self):
        with closing(sqlite3.connect(self.db)) as conn:
            return conn.execute('SELECT stype,provider_id FROM items ORDER BY stype,provider_id').fetchall()

    def worker(self, provider):
        return SearchWorker(self.db,provider,clock=lambda:7200)

    def test_two_snapshots_commit_together(self):
        def provider(stype, monitor):
            return [item(stype,stype+'1')], 'stamp_'+stype, True
        result=self.worker(provider).run_if_due(self.monitor)
        self.assertEqual(result['added'],2)
        self.assertEqual(self.rows(),[('movie','movie1'),('series','series1')])

    def test_second_snapshot_error_leaves_first_untouched(self):
        def provider(stype, monitor):
            if stype=='series':raise RuntimeError('provider failure')
            return [item(stype,'m1')],'stamp_movie',True
        with self.assertRaises(RuntimeError):
            self.worker(provider).run_if_due(self.monitor)
        self.assertEqual(self.rows(),[])

    def test_second_snapshot_incomplete_rolls_back_first(self):
        def provider(stype, monitor):
            return [item(stype,stype+'1')],'stamp_'+stype,stype=='movie'
        with self.assertRaises(ValueError):
            self.worker(provider).run_if_due(self.monitor)
        self.assertEqual(self.rows(),[])

    def test_second_reconcile_error_rolls_back_first(self):
        def provider(stype, monitor):
            if stype=='series':return [item(stype,'s1')],'password=unsafe',True
            return [item(stype,'m1')],'stamp_movie',True
        with self.assertRaises(ValueError):
            self.worker(provider).run_if_due(self.monitor)
        self.assertEqual(self.rows(),[])

    def test_aborted_between_snapshots_preserves_database(self):
        def provider(stype, monitor):
            if stype=='movie':
                monitor.abortRequested.return_value=True
            return [item(stype,'m1')],'stamp_movie',True
        self.assertIsNone(self.worker(provider).run_if_due(self.monitor))
        self.assertEqual(self.rows(),[])

    def test_reconcile_cannot_join_missing_caller_transaction(self):
        conn=open_store(self.db)
        try:
            conn.commit()
            with self.assertRaises(RuntimeError):
                reconcile(conn,'movie',[item('movie','m1')],'stamp',complete=True,
                          manage_transaction=False)
        finally:
            conn.close()
