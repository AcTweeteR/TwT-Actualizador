"""A Trakt snapshot becomes complete only after all authenticated read fences."""
import unittest
from test_trakt_sync import API, sync


class SnapshotCompletionContract(unittest.TestCase):
    def test_successful_import_is_explicitly_complete(self):
        snapshot = sync.fetch_snapshot(API().get)
        self.assertIs(snapshot['complete'], True)
        self.assertEqual(snapshot['account'], 'synthetic-user')

    def test_changed_remote_activity_never_yields_complete_snapshot(self):
        api = API()
        stamps = iter([({'all': '2026-10-21T10:00:00Z'}, 1),
                       ({'all': '2026-10-21T11:00:00Z'}, 1)])
        api.responses['/sync/last_activities'] = lambda _: next(stamps)
        with self.assertRaises(sync.IncompleteSnapshot):
            sync.fetch_snapshot(api.get)

    def test_changed_account_never_yields_complete_snapshot(self):
        api = API()
        users = iter([({'user': {'ids': {'slug': 'synthetic-user'}}}, 1),
                      ({'user': {'ids': {'slug': 'other-user'}}}, 1)])
        api.responses['/users/settings'] = lambda _: next(users)
        with self.assertRaises(sync.IncompleteSnapshot):
            sync.fetch_snapshot(api.get)
