#!/usr/bin/env python3
"""Read-only Kodi JSON-RPC directory benchmark; never emits playback URLs."""
import argparse
import hashlib
import json
import math
import socket
import statistics
import time

URLS={
'movie-recent':'plugin://plugin.video.xstream-pro/?mode=premium&view=recent&stype=movie&actweeter_expand=1&limit=20',
'movie-popular':'plugin://plugin.video.xstream-pro/?mode=premium&view=popular&stype=movie&actweeter_expand=1&limit=20',
'movie-trending':'plugin://plugin.video.xstream-pro/?mode=premium&view=trending&stype=movie&actweeter_expand=1&limit=20',
'movie-catalog':'plugin://plugin.video.xstream-pro/?mode=premium&view=catalog&stype=movie&actweeter_expand=1&limit=20',
'series-recent':'plugin://plugin.video.xstream-pro/?mode=premium&view=series_recent&stype=series&actweeter_expand=1&limit=20',
'series-popular':'plugin://plugin.video.xstream-pro/?mode=premium&view=popular&stype=series&actweeter_expand=1&limit=20',
'series-catalog':'plugin://plugin.video.xstream-pro/?mode=premium&view=catalog&stype=series&actweeter_expand=1&limit=20',
'series-continue':'plugin://plugin.video.xstream-pro/?mode=premium&view=continue&stype=series&actweeter_expand=1&limit=20',
'movie-favorites':'plugin://plugin.video.xstream-pro/?mode=premium&view=favorites&stype=movie&actweeter_expand=1&limit=20',
'series-favorites':'plugin://plugin.video.xstream-pro/?mode=premium&view=favorites&stype=series&actweeter_expand=1&limit=20',
}

def request_directory(host,port,directory,timeout):
    req={'jsonrpc':'2.0','id':1,'method':'Files.GetDirectory',
            'params':{'directory':directory,'media':'video','properties':['title','uniqueid']}}
    with socket.create_connection((host,port),timeout=min(timeout,5.0)) as s:
        s.settimeout(timeout)
        s.sendall((json.dumps(req)+'\r\n').encode())
        blob=bytearray()
        while len(blob)<16_000_000:
            buf=s.recv(1_000_000)
            if not buf:raise RuntimeError('Kodi connection ended before complete response')
            blob.extend(buf)
            try:res=json.loads(blob)
            except (UnicodeDecodeError,json.JSONDecodeError):continue
            if 'error' in res:raise RuntimeError('Kodi directory query failed')
            files=(res.get('result') or {}).get('files') or []
            # The digest allows old/new ordered-result comparison without exposing labels or URLs.
            fingerprint=[{'label':str(item.get('label') or ''),
                          'uniqueid':item.get('uniqueid') or {},
                          'type':str(item.get('type') or '')} for item in files]
            digest=hashlib.sha256(json.dumps(fingerprint,sort_keys=True,
                separators=(',',':'),ensure_ascii=False).encode('utf-8')).hexdigest()
            return len(files),digest
    raise RuntimeError('Kodi response too large')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,required=True)
    parser.add_argument('--name',default='Kodi')
    parser.add_argument('--samples',type=int,default=10)
    parser.add_argument('--timeout',type=float,default=60)
    args=parser.parse_args()
    if not 1<=args.samples<=100:parser.error('samples must be 1..100')
    for name,url in URLS.items():
        elapsed=[];counts=[]; fingerprints=[]
        for i in range(args.samples):
            start=time.perf_counter()
            try:
                n,digest=request_directory(args.host,args.port,url,args.timeout)
                d=time.perf_counter()-start
                elapsed.append(d);counts.append(n);fingerprints.append(digest)
                print(json.dumps({'device':args.name,'widget':name,
                    'sample':i+1,'seconds':round(d,3),'items':n,
                    'ordered_result_sha256':digest}),flush=True)
            except (OSError,RuntimeError) as exc:
                print(json.dumps({'device':args.name,'widget':name,
                    'sample':i+1,'error_type':type(exc).__name__}),flush=True)
        if elapsed:
            ordered=sorted(elapsed)
            print(json.dumps({'device':args.name,'widget':name,
                'median_seconds':round(statistics.median(ordered),3),
                'p90_seconds':round(ordered[min(len(ordered)-1,math.ceil(len(ordered)*.9)-1)],3),
                'min_seconds':round(min(ordered),3),'max_seconds':round(max(ordered),3),
                'stdev_seconds':round(statistics.pstdev(ordered),3),
                'items_consistent':len(set(counts))==1,
                'ordered_results_consistent':len(set(fingerprints))==1}),flush=True)

if __name__=='__main__':main()
