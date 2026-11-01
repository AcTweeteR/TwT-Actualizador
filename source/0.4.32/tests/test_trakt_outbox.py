"""No network: explicit operations, uncertain writes and restart safety."""
import importlib
import multiprocessing
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'addons/service.actweeter/resources'))
outbox = importlib.import_module('lib.trakt_outbox')
sync = importlib.import_module('lib.trakt_sync')


def _send_from_process(path, operation, start, output):
    queue = outbox.Outbox(path)
    start.wait(10)
    def post(_path, _payload):
        fd = os.open(output, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
        try:
            os.write(fd, b'1\n')
        finally:
            os.close(fd)
        return {'added': {'movies': 1}, 'not_found': {}}
    queue.send(operation, account='synthetic-account', profile='1',
               approved=operation, post=post, now=100)


def _send_manual_from_process(path, operation, start, output):
    queue = outbox.Outbox(path)
    start.wait(10)
    def post(_path, _payload):
        fd = os.open(output, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
        try:
            os.write(fd, b'1\n')
        finally:
            os.close(fd)
        return {'added': {'movies': 1}, 'not_found': {}}
    queue.send_manual(operation, account='synthetic-account', profile='1', provider_scope='a' * 64,
                      approved=operation, post=post, now=100)


def _enqueue_during_import(path, event, ready, done):
    ready.set()
    queue = outbox.Outbox(path)
    queue.enqueue_manual(event)
    done.set()


class OutboxTests(unittest.TestCase):
    def test_automatic_dispatch_never_selects_removals(self):
        with tempfile.TemporaryDirectory() as folder:
            queue=outbox.Outbox(Path(folder)/'outbox.sqlite')
            movie=sync.identity('movie', {'tmdb':42})
            for number,operation in enumerate(('history.remove','watchlist.remove','collection.remove','list.123.remove','watchlist.add')):
                event=outbox.manual_event('user','1',operation,movie,str(number)*32,provider_scope='a'*64)
                queue.enqueue_manual(event,held=True)
            selected=queue.pending_manual(account='user',profile='1',provider_scope='a'*64,now=100,include_held=True)
            self.assertEqual(len(selected),1)
            with queue.connect() as db:
                import json
                event=json.loads(db.execute('SELECT event FROM events WHERE id=?',(selected[0],)).fetchone()[0])
            self.assertEqual(event['operation'],'watchlist.add')

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'queue.sqlite'
        self.queue = outbox.Outbox(self.path)
        self.event = outbox.watched_event('synthetic-account', '1',
            sync.identity('movie', {'tmdb': 42}), '2026-10-21T12:00:00Z')
        self.op = self.queue.enqueue(self.event)
        self.calls = []

    def send(self, **kwargs):
        options = {'account': 'synthetic-account', 'profile': '1', 'approved': self.op,
                   'post': self.post, 'now': 100}
        options.update(kwargs)
        return self.queue.send(self.op, **options)

    def post(self, path, payload):
        self.calls.append((path, payload))
        return {'added': {'movies': 1, 'episodes': 0}, 'not_found': {}}

    def test_independent_processes_claim_only_one_network_send(self):
        context = multiprocessing.get_context('spawn')
        start = context.Event()
        output = str(self.path.parent / 'posts')
        workers = [context.Process(target=_send_from_process, args=(str(self.path), self.op, start, output))
                   for _ in range(2)]
        for worker in workers:
            worker.start()
        start.set()
        for worker in workers:
            worker.join(15)
            if worker.is_alive():
                worker.terminate()
                worker.join()
            self.assertEqual(worker.exitcode, 0)
        self.assertEqual(Path(output).read_text().splitlines(), ['1'])
        self.assertEqual(self.queue.status(self.op)['state'], 'confirmed')

    def test_snapshot_confirmation_is_not_overwritten_by_late_timeout(self):
        snapshot = {'account': 'synthetic-account', 'complete': True, 'history': [
            {'identity': self.event['identity'], 'watched_at': self.event['watched_at']}]}
        def confirm_then_timeout(*_args):
            self.assertEqual(self.queue.confirm_from_snapshot(self.op, snapshot,
                account='synthetic-account', profile='1'), 'confirmed')
            raise TimeoutError()
        self.assertEqual(self.send(post=confirm_then_timeout), 'confirmed')
        self.assertEqual(self.queue.status(self.op)['state'], 'confirmed')

    def test_manual_action_claim_is_exclusive_across_processes(self):
        event = outbox.manual_event('synthetic-account', '1', 'watchlist.add',
            sync.identity('movie', {'tmdb': 42}), 'f' * 32, provider_scope='a' * 64)
        op = self.queue.enqueue_manual(event)
        context = multiprocessing.get_context('spawn')
        start = context.Event()
        output = str(self.path.parent / 'manual-posts')
        workers = [context.Process(target=_send_manual_from_process,
                    args=(str(self.path), op, start, output)) for _ in range(2)]
        for worker in workers: worker.start()
        start.set()
        for worker in workers:
            worker.join(15)
            if worker.is_alive():
                worker.terminate()
                worker.join()
            self.assertEqual(worker.exitcode, 0)
        self.assertEqual(Path(output).read_text().splitlines(), ['1'])
        self.assertEqual(self.queue.status(op)['state'], 'confirmed')

    def test_due_manual_actions_are_bound_and_exclude_checkins_and_unknown(self):
        movie = sync.identity('movie', {'tmdb': 42})
        first = self.queue.enqueue_manual(outbox.manual_event('synthetic-account', '1',
            'watchlist.add', movie, '1' * 32, provider_scope='a' * 64))
        other = self.queue.enqueue_manual(outbox.manual_event('synthetic-account', '1',
            'collection.add', movie, '2' * 32, provider_scope='b' * 64))
        self.queue.enqueue_manual(outbox.manual_event('synthetic-account', '1',
            'checkin', movie, '3' * 32, provider_scope='a' * 64))
        unknown = self.queue.enqueue_manual(outbox.manual_event('synthetic-account', '1',
            'favorites.add', movie, '4' * 32, provider_scope='a' * 64))
        with self.queue.connect() as db:
            db.execute("update events set state='unknown' where id=?", (unknown,))
        with self.queue.connect() as db:
            db.execute("insert into events (id,event,state) values (?,?,?)", ('malformed', '[]', 'pending'))
        self.assertEqual(self.queue.pending_manual(account='synthetic-account', profile='1',
            provider_scope='a' * 64, now=100), [first])
        self.assertEqual(self.queue.pending_manual(account='synthetic-account', profile='1',
            provider_scope='b' * 64, now=100), [other])
        self.assertEqual(self.queue.pending_manual(account='other', profile='1',
            provider_scope='a' * 64, now=100), [])

    def test_import_guard_serializes_enqueue_in_another_process(self):
        context = multiprocessing.get_context('spawn')
        ready, done = context.Event(), context.Event()
        event = outbox.manual_event('synthetic-account', '1', 'history.remove',
            sync.identity('movie', {'tmdb': 42}), '8' * 32, provider_scope='a' * 64)
        worker = context.Process(target=_enqueue_during_import, args=(str(self.path), event, ready, done))
        with self.queue.import_guard(account='synthetic-account', profile='1', provider_scope='a' * 64):
            worker.start()
            self.assertTrue(ready.wait(10))
            self.assertFalse(done.wait(0.2))
        worker.join(15)
        if worker.is_alive():
            worker.terminate(); worker.join()
        self.assertEqual(worker.exitcode, 0)
        self.assertTrue(done.is_set())
        self.assertEqual(self.queue.status(event['id'])['state'], 'pending')

    def test_import_guard_defers_pending_and_confirmed_removal(self):
        event = outbox.manual_event('synthetic-account', '1', 'history.remove',
            sync.identity('movie', {'tmdb': 42}), '9' * 32, provider_scope='a' * 64)
        operation = self.queue.enqueue_manual(event)
        with self.queue.import_guard(account='synthetic-account', profile='1', provider_scope='a' * 64) as conflict:
            self.assertTrue(conflict({'identity': event['identity']}))
            self.assertFalse(conflict({'identity': sync.identity('movie', {'tmdb': 43})}))
        with self.queue.connect() as db:
            db.execute("update events set state='confirmed' where id=?", (operation,))
        with self.queue.import_guard(account='synthetic-account', profile='1', provider_scope='a' * 64) as conflict:
            self.assertTrue(conflict({'identity': event['identity']}))
        with self.queue.import_guard(account='synthetic-account', profile='2', provider_scope='a' * 64) as conflict:
            self.assertFalse(conflict({'identity': event['identity']}))

    def test_import_guard_fails_closed_on_unattributable_corrupt_action(self):
        with self.queue.connect() as db:
            db.execute("insert into events (id,event,state) values (?,?,?)", ('broken', '{}', 'pending'))
        with self.assertRaisesRegex(ValueError, 'unsafe pending action'):
            with self.queue.import_guard(account='synthetic-account', profile='1', provider_scope='a' * 64):
                pass

    def test_import_guard_defers_overlapping_but_conflicting_identifiers(self):
        content = sync.identity('movie', {'tmdb': 42, 'imdb': 'tt12345'})
        event = outbox.manual_event('synthetic-account', '1', 'history.remove', content,
                                    '7' * 32, provider_scope='a' * 64)
        self.queue.enqueue_manual(event)
        other = sync.identity('movie', {'tmdb': 42, 'imdb': 'tt99999'})
        with self.queue.import_guard(account='synthetic-account', profile='1', provider_scope='a' * 64) as conflict:
            self.assertTrue(conflict({'identity': other}))

    def test_manual_list_action_is_durable_and_does_not_retry_unknown(self):
        event = outbox.manual_event('synthetic-account', '1', 'watchlist.add',
            sync.identity('movie', {'tmdb': 42}), 'a' * 32, provider_scope='a' * 64)
        op = self.queue.enqueue_manual(event)
        self.assertEqual(outbox.Outbox(self.path).enqueue_manual(event), op)
        def lost(_path, _payload):
            raise TimeoutError()
        options = dict(account='synthetic-account', profile='1', provider_scope='a' * 64, approved=op, now=100)
        self.assertEqual(self.queue.send_manual(op, post=lost, **options), 'unknown')
        self.assertEqual(self.queue.send_manual(op, post=self.post, **options), 'unknown')
        self.assertFalse(self.calls)

    def test_manual_checkin_requires_individual_identity(self):
        with self.assertRaises(ValueError):
            outbox.manual_event('synthetic-account', '1', 'checkin',
                sync.identity('show', {'tmdb': 42}), 'b' * 32, provider_scope='a' * 64)
        event = outbox.manual_event('synthetic-account', '1', 'checkin',
            sync.identity('episode', show_ids={'tmdb': 42}, season=2, episode=3), 'c' * 32, provider_scope='a' * 64)
        self.assertEqual(event['payload']['episode'], {'season': 2, 'number': 3})
        op = self.queue.enqueue_manual(event)
        state = self.queue.send_manual(op, account='synthetic-account', profile='1', provider_scope='a' * 64, approved=op,
            post=lambda path, payload: {'id': 123}, now=100)
        self.assertEqual(state, 'confirmed')

    def test_history_snapshot_cannot_confirm_unknown_watchlist_action(self):
        event = outbox.manual_event('synthetic-account', '1', 'watchlist.add',
            sync.identity('movie', {'tmdb': 42}), 'e' * 32, provider_scope='a' * 64)
        op = self.queue.enqueue_manual(event)
        self.queue.send_manual(op, account='synthetic-account', profile='1', provider_scope='a' * 64, approved=op,
            post=lambda *_: (_ for _ in ()).throw(TimeoutError()), now=100)
        snapshot = {'account': 'synthetic-account', 'complete': True,
                    'history': [{'identity': event['identity'], 'watched_at': None}]}
        with self.assertRaisesRegex(ValueError, 'cannot confirm'):
            self.queue.confirm_from_snapshot(op, snapshot, account='synthetic-account', profile='1', provider_scope='a' * 64)
        self.assertEqual(self.queue.status(op)['state'], 'unknown')

    def test_manual_queue_rejects_payload_injection_and_wrong_account(self):
        event = outbox.manual_event('synthetic-account', '1', 'history.remove',
            sync.identity('movie', {'tmdb': 42}), 'd' * 32, provider_scope='a' * 64)
        op = self.queue.enqueue_manual(event)
        with self.assertRaises(PermissionError):
            self.queue.send_manual(op, account='other', profile='1', provider_scope='a' * 64, approved=op,
                                   post=self.post, now=100)
        with self.assertRaises(PermissionError):
            self.queue.send_manual(op, account='synthetic-account', profile='1', provider_scope='b' * 64,
                                   approved=op, post=self.post, now=100)
        self.assertFalse(self.calls)
        event['endpoint'] = 'https://example.invalid'
        with self.assertRaises(ValueError):
            self.queue.enqueue_manual(event)

    def test_repeated_enqueue_and_restart_do_not_duplicate(self):
        self.assertEqual(outbox.Outbox(self.path).enqueue(self.event), self.op)
        self.assertEqual(self.send(), 'confirmed')
        self.assertEqual(self.send(), 'confirmed')
        self.assertEqual(len(self.calls), 1)

    def test_symlink_queue_is_rejected(self):
        target = self.path.parent / 'other.sqlite'
        target.write_text('unchanged')
        link = self.path.parent / 'linked.sqlite'
        link.symlink_to(target)
        with self.assertRaises(ValueError):
            outbox.Outbox(link)
        self.assertEqual(target.read_text(), 'unchanged')

    def test_specific_approval_is_required_before_network(self):
        for approval in (None, True, 'another-operation'):
            with self.assertRaises(PermissionError): self.send(approved=approval)
        self.assertFalse(self.calls)

    def test_account_or_profile_change_blocks_send(self):
        for kwargs in ({'account': 'other'}, {'profile': '2'}):
            with self.assertRaises(PermissionError): self.send(**kwargs)
        self.assertFalse(self.calls)

    def test_unknown_outcome_is_never_retried(self):
        def timeout(*args): raise TimeoutError()
        self.assertEqual(self.send(post=timeout), 'unknown')
        self.assertEqual(self.send(), 'unknown')
        self.assertFalse(self.calls)
        self.assertEqual(self.queue.status(self.op)['attempts'], 1)

    def test_inflight_after_crash_is_not_retried(self):
        with self.queue.connect() as db:
            db.execute("UPDATE events SET state='inflight' WHERE id=?", (self.op,))
        self.queue = outbox.Outbox(self.path)
        self.assertEqual(self.send(), 'inflight')
        self.assertFalse(self.calls)

    def test_confirmed_rate_limit_waits_before_retry(self):
        def rate_limit(*args): raise outbox.RetryLater(30)
        self.assertEqual(self.send(post=rate_limit), 'pending')
        self.assertEqual(self.send(now=120), 'pending')
        self.assertFalse(self.calls)
        self.assertEqual(self.send(now=131), 'confirmed')

    def test_not_found_or_malformed_success_is_not_confirmed(self):
        self.assertEqual(self.send(post=lambda *_: {'added': {'movies': 0}}), 'unknown')

    def test_payload_cannot_inject_arbitrary_endpoint_or_url(self):
        self.event['payload']['url'] = 'https://invalid.example'
        with self.assertRaises(ValueError): self.queue.enqueue(self.event)

    def test_lost_response_can_be_confirmed_without_reposting(self):
        def timeout(*args): raise TimeoutError()
        self.send(post=timeout)
        snapshot = {'account': 'synthetic-account', 'complete': True, 'history': [
            {'identity': self.event['identity'], 'watched_at': self.event['watched_at']}]}
        self.assertEqual(self.queue.confirm_from_snapshot(self.op, snapshot,
                         account='synthetic-account', profile='1'), 'confirmed')
        self.assertEqual(self.send(), 'confirmed')
        self.assertFalse(self.calls)

    def test_different_date_or_content_does_not_resolve_unknown_write(self):
        def timeout(*args): raise TimeoutError()
        self.send(post=timeout)
        snapshot = {'account': 'synthetic-account', 'complete': True, 'history': [
            {'identity': self.event['identity'], 'watched_at': '2026-10-20T12:00:00Z'}]}
        self.assertEqual(self.queue.confirm_from_snapshot(self.op, snapshot,
                         account='synthetic-account', profile='1'), 'unknown')
        with self.assertRaises(PermissionError):
            self.queue.confirm_from_snapshot(self.op, snapshot, account='other', profile='1')

    def test_partial_history_never_confirms_uncertain_write(self):
        self.send(post=lambda *_: (_ for _ in ()).throw(TimeoutError()))
        snapshot = {'account': 'synthetic-account', 'history': [
            {'identity': self.event['identity'], 'watched_at': self.event['watched_at']}]}
        for complete in (None, False):
            candidate = dict(snapshot)
            if complete is not None:
                candidate['complete'] = complete
            with self.assertRaises(ValueError):
                self.queue.confirm_from_snapshot(self.op, candidate,
                    account='synthetic-account', profile='1')
        self.assertEqual(self.queue.status(self.op)['state'], 'unknown')
        self.assertEqual(self.send(), 'unknown')
        self.assertFalse(self.calls)

    def test_episode_payload_marks_only_one_explicit_episode(self):
        content = sync.identity('episode', show_ids={'tmdb': 42}, season=0, episode=1)
        event = outbox.watched_event('synthetic-account', '1', content, self.event['watched_at'])
        seasons = event['payload']['shows'][0]['seasons']
        self.assertEqual(seasons, [{'number': 0, 'episodes': [{'number': 1, 'watched_at': self.event['watched_at']}]}])
        with self.assertRaises(ValueError):
            outbox.watched_event('synthetic-account', '1', sync.identity('show', {'tmdb': 42}), self.event['watched_at'])


class ListOperationIntegrationTests(unittest.TestCase):
    def test_membership_endpoints_share_queue_confirmation_and_account_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            queue=outbox.Outbox(Path(folder)/'queue.sqlite')
            for number, target in enumerate(('watchlist', 'collection', 'list.123')):
                for action in ('add','remove'):
                    with self.subTest(target=target, action=action):
                        nonce=('%032x' % (number*2+(action=='remove')+1))
                        event=outbox.manual_event('account','1',target+'.'+action,
                            {'kind':'movie','ids':{'tmdb':198184}},nonce,provider_scope='a'*64)
                        identifier=queue.enqueue_manual(event,held=True)
                        sent=[]
                        def post(path,payload):
                            sent.append((path,payload))
                            return {'deleted' if action=='remove' else 'added':{'movies':1}}
                        with self.assertRaises(PermissionError):
                            queue.send_manual(identifier,account='other',profile='1',provider_scope='a'*64,
                                approved=identifier,post=post,now=1)
                        self.assertFalse(sent)
                        self.assertEqual(queue.send_manual(identifier,account='account',profile='1',provider_scope='a'*64,
                            approved=identifier,post=post,now=1),'confirmed')
                        self.assertEqual(queue.send_manual(identifier,account='account',profile='1',provider_scope='a'*64,
                            approved=identifier,post=post,now=2),'confirmed')
                        self.assertEqual(len(sent),1)
                        base='/users/me/lists/123/items' if target=='list.123' else '/sync/'+target
                        self.assertEqual(sent[0][0],base+('/remove' if action=='remove' else ''))
                        self.assertEqual(sent[0][1],{'movies':[{'ids':{'tmdb':198184}}]})
            for target in ('list../history.add','list.0.add','list.123/delete.add','list.me.add'):
                with self.assertRaises(ValueError):
                    outbox.manual_event('account','1',target,{'kind':'movie','ids':{'tmdb':1}},'a'*32,provider_scope='a'*64)


if __name__ == '__main__':
    unittest.main()
