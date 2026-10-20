#!/usr/bin/env python3
"""Compare v12 fallback, v13 synchronous build and v14 deferred build on synthetic JSON."""
import argparse
import cProfile
import importlib.util
import json
import math
import os
import platform
import pstats
import resource
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
SOURCE = 'synthetic|user|secret'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def measure(function):
    wall, cpu = time.perf_counter(), time.process_time()
    before = resource.getrusage(resource.RUSAGE_SELF)
    result = function()
    after = resource.getrusage(resource.RUSAGE_SELF)
    return result, {'wall_ms': (time.perf_counter() - wall) * 1000,
                    'cpu_ms': (time.process_time() - cpu) * 1000,
                    'block_in': after.ru_inblock - before.ru_inblock,
                    'block_out': after.ru_oublock - before.ru_oublock}


def summary(samples):
    result = {'n': len(samples)}
    for field in ('wall_ms', 'cpu_ms'):
        values = sorted(row[field] for row in samples)
        result[field] = {'p50': round(statistics.median(values), 3),
                         'p90': round(values[math.ceil(len(values) * .9) - 1], 3),
                         'min': round(values[0], 3), 'max': round(values[-1], 3)}
    result['block_io_total'] = {key: sum(row[key] for row in samples) for key in ('block_in', 'block_out')}
    return result


def dataset(path, count):
    with path.open('w', encoding='utf-8') as stream:
        stream.write('{"_src":' + json.dumps(SOURCE) + ',"_data":[')
        for i in range(count):
            if i: stream.write(',')
            json.dump({'stream_id': str(i), 'name': 'Title %05d' % (i // 3),
                       'year': str(1980 + i % 45), 'category_id': str(i % 8),
                       'tmdb_id': str(i), 'added': str(count - i),
                       'plot': 'Text escaped " sample \\ unicode é. ' * 48,
                       'stream_icon': 'https://images.invalid/' + 'p' * 200}, stream)
        stream.write(']}')


def run_size(count, repeats, build_repeats, old, new, legacy, diagnostics):
    with tempfile.TemporaryDirectory(prefix='xstream-synthetic-') as tmp:
        root = Path(tmp); path = root / 'catalog.json'; dataset(path, count)
        expected, baseline = [], []
        for _ in range(repeats):
            expected, sample = measure(lambda: legacy.old_query(path, 'recent')); baseline.append(sample)
        expected = (expected[0], expected[1] > 20)
        cold13, cold14, builds14, warm13, warm14, open14 = [], [], [], [], [], []
        traces, index_bytes = [], 0
        for trial in range(build_repeats):
            directory = root / ('trial-%s' % trial); directory.mkdir()
            old_path = directory / 'old.json'; new_path = directory / 'new.json'
            os.link(path, old_path); os.link(path, new_path)
            holder = {}
            def old_cold():
                holder['old'] = old.CatalogIndex(str(old_path), SOURCE, 1, 'movie')
                return holder['old'].page(mode='recent', limit=20)
            actual, sample = measure(old_cold); cold13.append(sample); assert actual == expected
            def fallback():
                try:
                    new.CatalogIndex(str(new_path), SOURCE, 1, 'movie')
                except new.IndexUnavailable:
                    new.schedule_rebuild(str(new_path), SOURCE, 1, 'movie')
                    rows, total = legacy.old_query(new_path, 'recent')
                    return rows, total > 20
                raise AssertionError('first request unexpectedly has an index')
            actual, sample = measure(fallback); cold14.append(sample); assert actual == expected
            logs = []
            trace = diagnostics.PerformanceTrace(log=logs.append)
            index, sample = measure(lambda: new.CatalogIndex(str(new_path), SOURCE, 1, 'movie', build=True, trace=trace))
            builds14.append(sample); trace.emit()
            traces.append(json.loads(logs[0].split(' ', 2)[2]))
            index_bytes = Path(index.path).stat().st_size
            for _ in range(repeats):
                actual, sample = measure(lambda: holder['old'].page(mode='recent', limit=20)); warm13.append(sample); assert actual == expected
                actual, sample = measure(lambda: index.page(mode='recent', limit=20)); warm14.append(sample); assert actual == expected
                _, sample = measure(lambda: new.CatalogIndex(str(new_path), SOURCE, 1, 'movie')); open14.append(sample)
        tracemalloc.start(); legacy.old_query(path, 'recent')
        legacy_peak = tracemalloc.get_traced_memory()[1]; tracemalloc.stop()
        tracemalloc.start(); index.page(mode='recent', limit=20)
        hot_peak = tracemalloc.get_traced_memory()[1]; tracemalloc.stop()
        return {'rows': count, 'requested': 20, 'source_bytes': path.stat().st_size,
                'index_bytes': index_bytes, 'legacy_v12': summary(baseline),
                'cold_v13': summary(cold13), 'cold_v14_fallback': summary(cold14),
                'background_build_v14': summary(builds14),
                'warm_v13': summary(warm13), 'warm_v14': summary(warm14),
                'open_v14': summary(open14), 'parity': 'identical full dictionaries and has_more',
                'python_peak_bytes': {'legacy': legacy_peak, 'warm_index': hot_peak},
                'build_traces': traces}


def profile_builds(count, old, new):
    output = {'rows': count, 'warning': 'cProfile adds overhead; timings are not runtime Kodi measurements', 'builds': {}}
    with tempfile.TemporaryDirectory(prefix='xstream-profile-') as tmp:
        root = Path(tmp)
        for version, module, kwargs in (('v13', old, {}), ('v14', new, {'build': True})):
            path = root / (version + '.json'); dataset(path, count)
            profiler = cProfile.Profile()
            _, measured = measure(lambda: profiler.runcall(module.CatalogIndex, str(path), SOURCE, 1, 'movie', **kwargs))
            stats = pstats.Stats(profiler)
            functions = []
            for (filename, line, name), (primitive, calls, own, cumulative, callers) in stats.stats.items():
                if any(token in filename for token in ('v13.py', 'provider_catalog_index.py')) or 'sqlite3.' in name:
                    functions.append({'function': name, 'calls': calls, 'own_ms': round(own * 1000, 3),
                                      'cumulative_ms': round(cumulative * 1000, 3)})
            output['builds'][version] = {'measured': measured, 'functions': sorted(functions,
                key=lambda row: row['cumulative_ms'], reverse=True)}
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sizes', type=int, nargs='+', default=[1000,10000,26337,50000,100000])
    parser.add_argument('--repeats', type=int, default=10)
    parser.add_argument('--build-repeats', type=int, default=3)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--profile-only', type=int, metavar='ROWS')
    parser.add_argument('--memory-only', action='store_true')
    parser.add_argument('--memory-child', choices=('v13', 'v14'))
    parser.add_argument('--catalog', type=Path)
    args = parser.parse_args()
    if min(args.sizes) < 1 or min(args.repeats, args.build_repeats) < 1: parser.error('positive counts required')
    new = load('catalog14', ROOT / 'third_party/xstream/provider_catalog_index.py')
    legacy = load('legacy_bench', ROOT / 'tools/benchmark_provider_catalog_index.py')
    diagnostics = load('trace_bench', ROOT / 'third_party/xstream/performance_diagnostics.py')
    with tempfile.TemporaryDirectory() as temp:
        previous = Path(temp) / 'v13.py'
        with zipfile.ZipFile(REPO / 'docs/testing/repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.13.zip') as archive:
            previous.write_bytes(archive.read('plugin.video.xstream-pro/resources/lib/provider_catalog_index.py'))
        old = load('catalog13', previous)
        if args.memory_child:
            if args.catalog is None: parser.error('--catalog required')
            baseline = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            module, kwargs = (old, {}) if args.memory_child == 'v13' else (new, {'build': True})
            index, measured = measure(lambda: module.CatalogIndex(str(args.catalog), SOURCE, 1, 'movie', **kwargs))
            scale = 1 if sys.platform == 'darwin' else 1024
            measured.update(peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * scale,
                            baseline_peak_rss_bytes=baseline * scale,
                            index_bytes=Path(index.path).stat().st_size)
            print(json.dumps(measured)); return
        if args.memory_only:
            output = {'kind': 'isolated fresh-process build RSS; one sample per size/version; synthetic', 'results': []}
            for count in args.sizes:
                with tempfile.TemporaryDirectory(prefix='xstream-memory-') as memory_temp:
                    row = {'rows': count}
                    for version in ('v13', 'v14'):
                        path = Path(memory_temp) / (version + '.json'); dataset(path, count)
                        child = subprocess.run([sys.executable, __file__, '--memory-child', version,
                            '--catalog', str(path), '--output', str(args.output)],
                            check=True, capture_output=True, text=True)
                        row[version] = json.loads(child.stdout)
                    output['results'].append(row)
                    args.output.write_text(json.dumps(output, indent=2) + '\n')
                    print('completed isolated memory rows=%s' % count, flush=True)
            return
        if args.profile_only is not None:
            if args.profile_only < 1: parser.error('positive profile size required')
            args.output.write_text(json.dumps(profile_builds(args.profile_only, old, new), indent=2) + '\n')
            return
        output = {'kind': 'synthetic; external Kodi runtime is not measured',
                  'python': sys.version, 'platform': platform.platform(), 'results': []}
        for size in args.sizes:
            output['results'].append(run_size(size, args.repeats, args.build_repeats, old, new, legacy, diagnostics))
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(output, indent=2) + '\n')
            print('completed synthetic rows=%s' % size, flush=True)


if __name__ == '__main__':
    main()
