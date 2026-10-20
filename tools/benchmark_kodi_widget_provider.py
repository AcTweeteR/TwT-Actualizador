#!/usr/bin/env python3
"""Read-only JSON-RPC directory benchmark: output timings/counts, never result URLs."""
import argparse,json,socket,statistics,time

URLS={
'movie-recent':'plugin://plugin.video.xstream-pro/?mode=premium&view=recent&stype=movie&actweeter_expand=1&limit=20',
'movie-popular':'plugin://plugin.video.xstream-pro/?mode=premium&view=popular&stype=movie&actweeter_expand=1&limit=20',
}

def request_directory(host,port,directory,timeout):
    req={'jsonrpc':'2.0','id':1,'method':'Files.GetDirectory',
         'params':{'directory':directory,'media':'video','properties':['title','art']}}
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
            return len((res.get('result') or {}).get('files') or [])
    raise RuntimeError('Kodi response too large')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,required=True)
    parser.add_argument('--name',default='Kodi')
    parser.add_argument('--samples',type=int,default=4)
    parser.add_argument('--timeout',type=float,default=45)
    args=parser.parse_args()
    if not 1<=args.samples<=20:parser.error('samples must be 1..20')
    for name,url in URLS.items():
        elapsed=[];counts=[]
        for i in range(args.samples):
            start=time.perf_counter()
            try:
                n=request_directory(args.host,args.port,url,args.timeout)
                d=time.perf_counter()-start
                elapsed.append(d);counts.append(n)
                print(json.dumps({'device':args.name,'widget':name,
                    'sample':i+1,'seconds':round(d,3),'items':n}),flush=True)
            except (OSError,RuntimeError) as exc:
                print(json.dumps({'device':args.name,'widget':name,
                    'sample':i+1,'error_type':type(exc).__name__}),flush=True)
        if elapsed:
            print(json.dumps({'device':args.name,'widget':name,
                'median_seconds':round(statistics.median(elapsed),3),
                'items_consistent':len(set(counts))==1}),flush=True)

if __name__=='__main__':main()
