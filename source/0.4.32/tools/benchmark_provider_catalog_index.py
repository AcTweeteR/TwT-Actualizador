#!/usr/bin/env python3
"""Synthetic JSON catalog benchmark; contains no provider or account data."""
import argparse
import importlib.util
import json
import statistics
import tempfile
import time
import tracemalloc
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'provider_catalog_index', ROOT / 'third_party/xstream/provider_catalog_index.py')
INDEX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INDEX)


def summary(values):
    ordered = sorted(values)
    return {'median_ms': round(statistics.median(ordered) * 1000, 3),
            'p90_ms': round(ordered[min(len(ordered) - 1, int(len(ordered) * .9))] * 1000, 3),
            'min_ms': round(ordered[0] * 1000, 3),
            'max_ms': round(ordered[-1] * 1000, 3)}


def old_query(path, mode):
    with open(path, encoding='utf-8') as stream:
        items = json.load(stream)['_data']
    if mode == 'recent':
        items = [item for item in items if int(float(item.get('added') or 0)) > 0]
        items.sort(key=lambda item: int(float(item.get('added') or 0)), reverse=True)
    seen, selected = set(), []
    for item in items:
        identity = (INDEX._norm(item.get('name')), str(item.get('year') or ''))
        if identity not in seen:
            seen.add(identity)
            selected.append(item)
    return selected[:20], len(selected)


def run_size(count, repeats):
    source = 'synthetic://provider|synthetic-user|synthetic-secret'
    items = [{'stream_id': str(index), 'name': 'Title %05d' % (index // 3),
              'year': str(1980 + index % 45), 'category_id': str(index % 8),
              'tmdb_id': str(index), 'added': str(count - index),
              'stream_icon': 'https://images.invalid/poster.jpg'}
             for index in range(count)]
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / 'catalog.json'
        with path.open('w', encoding='utf-8') as stream:
            json.dump({'_src': source, '_data': items}, stream, separators=(',', ':'))
        file_bytes = path.stat().st_size
        rows = {}
        build_started = time.perf_counter()
        index = INDEX.CatalogIndex(str(path), source, 1, 'movie', build=True)
        build_seconds = time.perf_counter() - build_started
        for mode in ('catalog', 'recent'):
            old_times, new_times = [], []
            expected = None
            for _ in range(repeats):
                started = time.perf_counter()
                old_rows, old_count = old_query(path, mode)
                old_times.append(time.perf_counter() - started)
                expected = ([row['stream_id'] for row in old_rows], old_count > 20)
                started = time.perf_counter()
                new_rows, new_count = index.page(mode=mode, limit=20)
                new_times.append(time.perf_counter() - started)
                actual = ([row['stream_id'] for row in new_rows], new_count)
                if actual != expected:
                    raise AssertionError('%s result mismatch at %s rows' % (mode, count))
            tracemalloc.start()
            old_query(path, mode)
            legacy_peak = tracemalloc.get_traced_memory()[1]
            tracemalloc.stop()
            tracemalloc.start()
            index.page(mode=mode, limit=20)
            indexed_peak = tracemalloc.get_traced_memory()[1]
            tracemalloc.stop()
            rows[mode] = {'legacy': summary(old_times), 'indexed_warm': summary(new_times),
                          'legacy_peak_python_bytes': legacy_peak,
                          'indexed_peak_python_bytes': indexed_peak}
        return {'items': count, 'requested': 20, 'catalog_bytes': file_bytes,
                'index_bytes': Path(index.path).stat().st_size,
                'index_build_ms': round(build_seconds * 1000, 3), 'routes': rows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sizes', nargs='+', type=int,
                        default=[1000, 10000, 26337, 50000, 100000])
    parser.add_argument('--repeats', type=int, default=10)
    args = parser.parse_args()
    if args.repeats < 2 or any(size < 1 for size in args.sizes):
        parser.error('sizes must be positive and repeats at least 2')
    print(json.dumps({'benchmark': 'synthetic-json-vs-sqlite-offset-index',
                      'repeats': args.repeats,
                      'results': [run_size(size, args.repeats) for size in args.sizes]},
                     sort_keys=True))


if __name__ == '__main__':
    main()
