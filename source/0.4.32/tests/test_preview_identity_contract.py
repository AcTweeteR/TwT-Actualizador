import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/service.actweeter/resources/lib'))
from kodi_auto_preview import stable_identity
from slyguy_preview_bridge import _identity, request_is_current


class PreviewIdentityContractTests(unittest.TestCase):
    def test_provider_accepts_the_same_title_identity_as_coordinator(self):
        data = {'media_type': 'movie', 'title': 'Synthetic movie', 'year': '2026'}
        self.assertEqual(_identity(data), stable_identity(data))
        self.assertTrue(_identity(data))

    def test_current_card_is_verified_using_title_when_ids_are_missing(self):
        data = {'media_type': 'movie', 'title': 'Synthetic movie', 'year': '2026'}
        labels = {'System.CurrentControlId': '13003', 'Container(13003).CurrentItem': '1',
                  'Window(Home).Property(ACTWEETER_AUTO_PREVIEW_REQUEST)': 'request',
                  'Container(13003).ListItem.DBType': 'movie',
                  'Container(13003).ListItem.Title': data['title'],
                  'Container(13003).ListItem.Year': data['year']}
        kodi = SimpleNamespace(getInfoLabel=lambda key: labels.get(key, ''),
                               getCondVisibility=lambda key: key == 'Window.IsActive(10000)')
        request = dict(data, generation=1, window=10000, container=13003,
                       focus=13003, position=1, request_id='request', identity=stable_identity(data))
        self.assertTrue(request_is_current(kodi, request))
        labels['Container(13003).ListItem.Title'] = 'Another movie'
        self.assertFalse(request_is_current(kodi, request))
