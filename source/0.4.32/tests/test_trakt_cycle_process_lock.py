"""Real independent-process exclusion; no Kodi, credentials, or remote requests."""
import multiprocessing
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'addons/service.actweeter/resources'))
from lib import trakt_auto_cycle as cycle


def _worker(root, start, release, entered, results):
    def body(*args, **kwargs):
        entered.put(os.getpid())
        deadline = time.monotonic() + 15
        while not Path(release).exists():
            if time.monotonic() >= deadline:
                raise TimeoutError('test owner was not released')
            time.sleep(0.01)
        return {'status': 'completed'}
    if not start.wait(15):
        return
    cycle._run_cycle = body
    results.put(cycle.run_cycle(root, root))


class CycleProcessLockTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / 'trakt_live'
        self.state.mkdir(mode=0o700)
        self.lock = self.state / 'cycle.lock'
        self.ctx = multiprocessing.get_context('spawn')
        self.events = []

    def launch(self, count):
        start = self.ctx.Event()
        self.events.append(start)
        release = self.root / ('release-' + str(len(self.events)))
        entered, results = self.ctx.Queue(), self.ctx.Queue()
        processes = [self.ctx.Process(target=_worker,
                     args=(str(self.root), start, release, entered, results))
                     for _ in range(count)]
        def cleanup():
            release.touch()
            for process in processes:
                process.join(3)
                if process.is_alive():
                    process.terminate()
                    process.join(3)
            entered.close()
            results.close()
        self.addCleanup(cleanup)
        for process in processes:
            process.start()
        start.set()
        return processes, release, entered, results

    def test_simultaneous_recovery_keeps_one_owner_and_same_inode(self):
        # Old PID and malformed legacy locks are inert, not deleted during recovery.
        for legacy in ('99999999', ''):
            with self.subTest(legacy=legacy):
                self.lock.write_text(legacy)
                inode = self.lock.stat().st_ino
                processes, release, entered, results = self.launch(6)
                entered.get(timeout=10)
                outcomes = [results.get(timeout=10) for _ in range(5)]
                self.assertEqual(outcomes, [{'status': 'busy'}] * 5)
                self.assertEqual(self.lock.stat().st_ino, inode)
                release.touch()
                self.assertEqual(results.get(timeout=10), {'status': 'completed'})
                for process in processes:
                    process.join(5)
                    self.assertEqual(process.exitcode, 0)
                self.assertEqual(self.lock.stat().st_ino, inode)

    def test_killed_owner_releases_without_stale_timeout(self):
        processes, release, entered, results = self.launch(1)
        entered.get(timeout=10)
        inode = self.lock.stat().st_ino
        with patch.object(cycle, '_run_cycle', return_value={'status': 'recovered'}) as body:
            self.assertEqual(cycle.run_cycle(self.root, self.root), {'status': 'busy'})
            body.assert_not_called()
            processes[0].terminate()
            processes[0].join(5)
            self.assertEqual(cycle.run_cycle(self.root, self.root), {'status': 'recovered'})
            body.assert_called_once()
        self.assertEqual(self.lock.stat().st_ino, inode)

    def test_exception_releases_and_retains_lock(self):
        with patch.object(cycle, '_run_cycle', side_effect=RuntimeError('synthetic')):
            with self.assertRaisesRegex(RuntimeError, 'synthetic'):
                cycle.run_cycle(self.root, self.root)
        inode = self.lock.stat().st_ino
        with patch.object(cycle, '_run_cycle', return_value={'status': 'ok'}):
            self.assertEqual(cycle.run_cycle(self.root, self.root), {'status': 'ok'})
        self.assertEqual(self.lock.stat().st_ino, inode)

    def test_symlink_and_shared_state_rejected(self):
        target = self.root / 'untouched'
        target.write_text('keep')
        self.lock.symlink_to(target)
        with patch.object(cycle, '_run_cycle') as body:
            self.assertEqual(cycle.run_cycle(self.root, self.root)['reason'], 'unsafe_cycle_lock')
            self.assertEqual(target.read_text(), 'keep')
            self.state.chmod(0o755)
            self.assertEqual(cycle.run_cycle(self.root, self.root)['reason'],
                             'sync_state_directory_not_private')
            body.assert_not_called()


if __name__ == '__main__':
    unittest.main()
