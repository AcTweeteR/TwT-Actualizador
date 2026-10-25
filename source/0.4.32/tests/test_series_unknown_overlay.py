"""Unknown or incomplete episode inventories must not remove earlier checks."""
import importlib.util
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock

MODULE = Path(__file__).resolve().parents[1] / 'addons/service.actweeter/resources/lib/series_state.py'
spec = importlib.util.spec_from_file_location('series_state_under_test', MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class UnknownInventoryOverlayTests(TestCase):
    def test_unknown_series_never_clears_existing_watched_overlay(self):
        item = Mock()
        self.assertFalse(module.apply_to_listitem(item, {'known': False}))
        item.getVideoInfoTag.assert_not_called()
        item.setProperty.assert_not_called()

    def test_incomplete_known_inventory_preserves_check_and_complete_flag(self):
        item = Mock()
        self.assertTrue(module.apply_to_listitem(item, {
            'known': True, 'complete': None, 'progress_label': '2/2'}))
        item.getVideoInfoTag.assert_not_called()
        self.assertEqual(item.setProperty.call_count, 1)
        item.setProperty.assert_called_once_with('XStream.SeriesProgressLabel', '2/2')

    def test_confirmed_complete_series_marks_watched(self):
        item = Mock()
        self.assertTrue(module.apply_to_listitem(item, {'known': True, 'complete': True}))
        item.getVideoInfoTag.return_value.setPlaycount.assert_called_once_with(1)
        item.setProperty.assert_any_call('XStream.SeriesComplete', 'true')

    def test_confirmed_unwatched_series_clears_check(self):
        item = Mock()
        self.assertTrue(module.apply_to_listitem(item, {'known': True, 'complete': False}))
        item.getVideoInfoTag.return_value.setPlaycount.assert_called_once_with(0)
        item.setProperty.assert_any_call('XStream.SeriesComplete', 'false')
