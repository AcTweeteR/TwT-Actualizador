#!/usr/bin/env python3
"""Reproducible read-only comparison on an existing real provider search index.

No credentials, catalogue rows or private paths are emitted. Cold means a new
in-process search session, not a forced OS disk-cache flush. No Kodi playback.
"""
import argparse
import gc
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
import tracemalloc
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source/0.4.32/addons/service.actweeter/resources/lib"))
import smart_search_engine as candidate

QUERIES = ("maquina guerra", "máquina de guerra", "matrix", "matrx", "casa pap", "guerra", "tom cruise")
TYPING = ("ma", "maq", "maqu", "maqui", "maquin", "maquina", "maquina g", "maquina gu", "maquina gue", "maquina guerra")


def summary(values):
    ordered = sorted(values)
    return {"p50_ms": round(statistics.median(values), 3),
            "p90_ms": round(ordered[max(0, (9 * len(ordered) + 9) // 10 - 1)], 3)}


def measure(module, index, profile, rounds):
    cold = []
    for _ in range(3):
        start = time.perf_counter()
        engine = module.CatalogSearch(index, profile)
        engine.refresh()
        cold.append((time.perf_counter() - start) * 1000)
    result = {"cold_new_session": summary(cold), "titles": len(engine.rows), "warm": {}}
    for query in QUERIES:
        values = []
        for _ in range(rounds):
            start = time.perf_counter()
            rows = engine.search(query)
            values.append((time.perf_counter() - start) * 1000)
        result["warm"][query] = dict(summary(values), results=len(rows))
    values = []
    for _ in range(rounds):
        for query in TYPING:
            start = time.perf_counter()
            engine.search(query)
            values.append((time.perf_counter() - start) * 1000)
    result["typing_backend_queries"] = dict(summary(values), samples=len(values))
    del engine
    gc.collect()
    tracemalloc.start()
    one = module.CatalogSearch(index, profile)
    one.refresh()
    if hasattr(one, "fork"):
        two = one.fork()
    else:
        two = module.CatalogSearch(index, profile)
        two.refresh()
    result["two_worker_index_peak_mib"] = round(tracemalloc.get_traced_memory()[1] / 1048576, 3)
    result["shared_rows"] = one.rows is two.rows
    tracemalloc.stop()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--profile", type=int, default=1)
    parser.add_argument("--baseline-ref", default="3d4a8c3")
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not 1 <= args.profile <= 10 or not 1 <= args.rounds <= 100:
        parser.error("invalid profile or sample count")
    if not args.index.is_file():
        parser.error("existing provider index required")
    before = args.index.stat()
    source = subprocess.check_output(["git", "show", args.baseline_ref +
        ":source/0.4.32/addons/service.actweeter/resources/lib/smart_search_engine.py"], cwd=ROOT)
    baseline = types.ModuleType("search_benchmark_baseline")
    exec(compile(source, "baseline_smart_search_engine.py", "exec"), baseline.__dict__)
    report = {"measurement": "REAL_MAC_BACKEND_EXISTING_CATALOGUE",
              "not_measured": ["physical_disk_cold_cache", "UI_end_to_end", "provider_network", "tvOS", "Android"],
              "python": platform.python_version(), "platform": platform.platform(),
              "baseline_ref": args.baseline_ref, "rounds": args.rounds,
              "baseline": measure(baseline, args.index, args.profile, args.rounds),
              "candidate": measure(candidate, args.index, args.profile, args.rounds)}
    after = args.index.stat()
    report["index_file_unchanged"] = (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    if not report["index_file_unchanged"]:
        raise SystemExit("index changed during measurement; rerun on a stable snapshot")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
