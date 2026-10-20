import contextlib
import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('widget_bench31', ROOT / 'tools/benchmark_kodi_widget_provider.py')
BENCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BENCH)


class WidgetBenchmarkCliTests(unittest.TestCase):
    def test_single_cold_query_preserves_exact_route_and_properties(self):
        with mock.patch.object(sys, 'argv', ['benchmark', '--port', '19091', '--samples', '1',
                '--widgets', 'movie-recent', '--properties', 'title', 'art']), \
             mock.patch.object(BENCH, 'request_directory', return_value=(21, 'digest')) as request, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            BENCH.main()
        request.assert_called_once_with('127.0.0.1', 19091, BENCH.URLS['movie-recent'], 60, ['title', 'art'])
        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(rows[0]['items'], 21)
        self.assertNotIn('plugin://', output.getvalue())

    def test_errors_record_only_type_without_sensitive_message(self):
        with mock.patch.object(sys, 'argv', ['benchmark', '--port', '9090', '--samples', '1', '--widgets', 'movie-recent']), \
             mock.patch.object(BENCH, 'request_directory', side_effect=OSError('private provider secret')), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            BENCH.main()
        self.assertNotIn('secret', output.getvalue())
        self.assertEqual(json.loads(output.getvalue())['error_type'], 'OSError')
