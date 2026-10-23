#!/usr/bin/env python3
"""Read-only before/after identity-gate benchmark; never invokes apply_batch."""
import argparse
import ast
import importlib.util
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
from prepare_trakt_catalog_mac import private_json

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'source/0.4.32/addons/service.actweeter/resources/lib'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog',type=Path,required=True)
    parser.add_argument('--operations',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    kodi=Path.home()/'Library/Application Support/Kodi'
    if (args.output.is_symlink() or args.output.resolve().is_relative_to(ROOT)
            or args.output.resolve().is_relative_to(kodi)):
        parser.error('private output outside repository required')
    source='source/0.4.32/third_party/xstream/trakt_live_consumer.py'
    tree=ast.parse(subprocess.check_output(['git','show','cabd460:'+source],cwd=ROOT))
    functions=[node for node in tree.body if isinstance(node,ast.FunctionDef)
               and node.name in ('_cache','_catalog_identity_exact')]
    old={'Path':Path,'json':json}
    exec(compile(ast.Module(body=functions,type_ignores=[]),'baseline-readonly-gate','exec'),old)
    spec=importlib.util.spec_from_file_location('current_gate',ROOT/source)
    current=importlib.util.module_from_spec(spec);spec.loader.exec_module(current)
    plan=json.loads(args.operations.read_text())['plan']
    profile=plan['profile']
    operations=[dict(item,kind=item['identity']['kind']) for item in plan['items']]
    results={}
    for label in ('legacy','corrected'):
        rows=[];valid=[]
        for _ in range(10):
            wall,cpu=time.perf_counter(),time.process_time()
            if label=='legacy': values=[old['_catalog_identity_exact'](op,args.catalog,profile) for op in operations]
            else:
                index=current._verified_catalog_index(operations,args.catalog,profile)
                values=[current._catalog_identity_exact(op,index) for op in operations]
            rows.append({'wall_ms':(time.perf_counter()-wall)*1000,'cpu_ms':(time.process_time()-cpu)*1000})
            valid.append(sum(values))
        summary={}
        for key in ('wall_ms','cpu_ms'):
            values=sorted(r[key] for r in rows)
            summary[key]={'p50':round(statistics.median(values),3),'p90':round(values[8],3),
                          'min':round(values[0],3),'max':round(values[-1],3)}
        results[label]={'samples':rows,'summary':summary,'verified_counts':valid}
    results.update(operations_per_batch=len(operations),state_writes=0,
        warning='baseline may reject before reading; verify acceptance counts before comparing speed')
    args.output.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    private_json(args.output,results)
    print(json.dumps({label:{'summary':value['summary'],'verified':value['verified_counts']}
                      for label,value in results.items() if isinstance(value,dict)}))


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'status':'FAILED','error_type':type(error).__name__}));raise SystemExit(1)
