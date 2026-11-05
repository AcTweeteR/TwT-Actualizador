#!/usr/bin/env python3
"""Create-only deterministic AcTweeteR EPG/watch-state/performance Beta.

Starts from published Beta skin and XStream ZIPs; Service/PVR/Trakt packages,
Kodi user profiles and Stable index are immutable.
"""
from __future__ import annotations
import argparse,hashlib,json,stat,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from epg_watch_performance_patch import patch

ROOT=Path(__file__).resolve().parents[1]
FIXED_TIME=(2026,11,5,0,0,0)
SPEC={
 'skin.actweeter':{
  'base':'1.2.41~beta3','beta':'1.2.41~beta4',
  'sha256':'1eafc3c983f032b2849796c0625f65333f82a02812f40806ac74e72626a0f358',
  'members':('1080i/IncludesViews.xml',)},
 'plugin.video.xstream-pro':{
  'base':'1.1.2.40~beta1','beta':'1.1.2.40~beta2',
  'sha256':'9c3c7c175eed44229734249a630c80027aaec0087548b07889900efb18d1e893',
  'members':('resources/lib/watched_actions.py','resources/lib/addon.py',
             'resources/lib/premium_routes.py','resources/lib/series_changes.py',
             'resources/lib/watch_ui_refresh.py')},
}
NEWS = {
 'skin.actweeter':("AcTweeteR Beta4: visible EPG event cards on timeline; "
                    "four formerly zero-width titles and three narrow backgrounds corrected. "
                    "Other skin windows and remote mode remain untouched.\n"),
 'plugin.video.xstream-pro':("XStream Beta2: immediate visual watch-state invalidation "
  "with a delayed refresh after context menus; COMPLETE/new episode state recalculates. "
  "Premium 19-item widgets show existing provider/cached metadata without "
  "blocking on cold TMDb search and logo lookups; new episode inventory invalidates widget status. Browse unchanged.\n")
}

def sha(data):return hashlib.sha256(data).hexdigest()

def build(output):
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    result={}
    for addon,spec in SPEC.items():
        target=output/f"{addon}-{spec['beta']}.zip"
        if target.exists() or target.is_symlink():
            raise FileExistsError('Refusing overwrite: '+str(target))
        parent=ROOT/'docs/testing/repo'/addon/f"{addon}-{spec['base']}.zip"
        if sha(parent.read_bytes())!=spec['sha256']:
            raise ValueError('Immutable Beta baseline mismatch for '+addon)
        with zipfile.ZipFile(parent) as z:
            if z.testzip() is not None:raise ValueError('Baseline CRC failed')
            payloads={n:z.read(n) for n in z.namelist() if n and not n.endswith('/')}
        old=dict(payloads)
        if addon=='skin.actweeter':
            for rel in spec['members']:
                source=ROOT/'source/0.4.32/addons'/addon/rel
                if not source.is_file() or source.is_symlink():
                    raise ValueError('Invalid skin source '+rel)
                payloads[f'{addon}/{rel}']=source.read_bytes()
        else:patch(payloads)
        manifest=f'{addon}/addon.xml'
        document=ET.fromstring(payloads[manifest])
        if document.get('id')!=addon or document.get('version')!=spec['base']:
            raise ValueError('Bad baseline addon.xml '+addon)
        extension=document.find("./extension[@point='xbmc.addon.metadata']/news")
        # XStream's metadata contains an empty news field. Keep that existing
        # schema; a retained release note is provided separately in the ZIP.
        if addon == 'skin.actweeter':
            if extension is None or extension.text!=f"changelog-{spec['base']}.txt":
                raise ValueError('Bad baseline changelog '+addon)
            extension.text=f"changelog-{spec['beta']}.txt"
        elif extension is not None and extension.text not in (None, '',
                                                               f"changelog-{spec['base']}.txt"):
            raise ValueError('Unexpected XStream news metadata')
        elif extension is not None and extension.text:
            extension.text=f"changelog-{spec['beta']}.txt"
        document.set('version',spec['beta'])
        payloads[manifest]=ET.tostring(document,xml_declaration=True,encoding='utf-8')+b'\n'
        note=f"{addon}/changelog-{spec['beta']}.txt"
        payloads[note]=NEWS[addon].encode()
        changed={k for k,v in payloads.items() if old.get(k)!=v}
        allowed={f'{addon}/{x}' for x in spec['members']} | {manifest,note}
        if changed!=allowed:raise ValueError('Out-of-scope ZIP change: '+str(changed^allowed))
        for n,b in payloads.items():
            if n.endswith('.py'):compile(b,n,'exec')
            if n.endswith('.xml'):ET.fromstring(b)
        with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for member,b in sorted(payloads.items()):
                if not member.startswith(addon+'/') or '..' in Path(member).parts:
                    raise ValueError('Unsafe zip path')
                info=zipfile.ZipInfo(member,FIXED_TIME)
                info.compress_type=zipfile.ZIP_DEFLATED
                info.external_attr=(stat.S_IFREG|0o644)<<16
                z.writestr(info,b,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
        with zipfile.ZipFile(target) as z:
            assert z.testzip() is None
            assert ET.fromstring(z.read(manifest)).get('version')==spec['beta']
        result[addon]={'version':spec['beta'],'size':target.stat().st_size,
                       'sha256':sha(target.read_bytes()),'changed':sorted(changed)}
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'build/epg-watched-perf-beta')
    print(json.dumps(build(parser.parse_args().output),indent=2,ensure_ascii=False))
