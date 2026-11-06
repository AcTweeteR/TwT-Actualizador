#!/usr/bin/env python3
"""Promote verified TV recent Beta9/Beta6 without replacing any existing Stable ZIP."""
from __future__ import annotations
import hashlib
import json
import stat
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
RELEASES=(('skin.actweeter','1.2.41~beta9','1.2.42'),('service.actweeter','0.4.101~beta6','0.4.102'))

def digest(b):return hashlib.sha256(b).hexdigest()

def promote():
    old=ET.parse(ROOT/'repo/addons.xml').getroot()
    previous={a.get('id'):a.get('version') for a in old}
    assert previous['skin.actweeter']=='1.2.41' and previous['service.actweeter']=='0.4.101'
    assert previous['plugin.video.xstream-pro']=='1.1.2.45'
    results=[]
    for addon,beta,stable in RELEASES:
        source=ROOT/'docs/testing/repo'/addon/f'{addon}-{beta}.zip'
        destination=ROOT/'repo'/addon/f'{addon}-{stable}.zip'
        if destination.exists():raise FileExistsError(destination)
        with zipfile.ZipFile(source) as src:
            if src.testzip() is not None:raise ValueError('bad beta archive')
            files=src.infolist()
            original={i.filename:src.read(i) for i in files}
        root=ET.fromstring(original[addon+'/addon.xml'])
        if root.get('version')!=beta:raise ValueError('unexpected beta version')
        meta=root.find("extension[@point='xbmc.addon.metadata']")
        news=meta.findtext('news')
        if news!=f'changelog-{beta}.txt':raise ValueError('unexpected changelog')
        root.set('version',stable)
        meta.find('news').text=f'changelog-{stable}.txt'
        replacement=ET.tostring(root,encoding='utf-8',xml_declaration=True)
        # Preserve the entire Beta payload; modify only addon.xml and add Stable release note.
        note=(f'AcTweeteR {addon} {stable} Stable (2026-11-06).\n'
              'TV reciente en Inicio: historial MRU, EPG, actualización al regresar a Inicio y fondo blanco de selección.\n').encode()
        destination.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(destination,'x') as dst:
            for info in files:
                dst.writestr(info,replacement if info.filename==addon+'/addon.xml' else original[info.filename])
            entry=zipfile.ZipInfo(f'{addon}/changelog-{stable}.txt',files[0].date_time)
            entry.compress_type=zipfile.ZIP_DEFLATED
            entry.external_attr=(stat.S_IFREG|0o644)<<16
            dst.writestr(entry,note)
        with zipfile.ZipFile(destination) as z:
            if z.testzip() is not None:raise ValueError('bad stable archive')
            new=ET.fromstring(z.read(addon+'/addon.xml'))
            assert new.get('version')==stable
            assert z.read(f'{addon}/changelog-{stable}.txt')==note
            assert all(z.read(name)==data for name,data in original.items() if name!=addon+'/addon.xml')
            for path in [f'{addon}/changelog-{stable}.txt',f'{addon}/resources/icon.png'] if addon=='skin.actweeter' else [f'{addon}/changelog-{stable}.txt']:
                output=ROOT/'repo'/addon/path.split('/',1)[1]
                if output.exists():
                    if output.read_bytes()!=z.read(path):raise ValueError('refuse to overwrite metadata '+str(output))
                else:output.write_bytes(z.read(path))
        index_entry=next(a for a in old if a.get('id')==addon)
        at=list(old).index(index_entry)
        old.remove(index_entry);old.insert(at,new)
        results.append({'addon':addon,'beta':beta,'stable':stable,'beta_sha256':digest(source.read_bytes()),'stable_sha256':digest(destination.read_bytes())})
    data=ET.tostring(old,encoding='utf-8',xml_declaration=True)+b'\n'
    (ROOT/'repo/addons.xml').write_bytes(data)
    (ROOT/'repo/addons.xml.md5').write_text(hashlib.md5(data).hexdigest()+'\n')
    print(json.dumps({'results':results,'index_sha256':digest(data)},indent=2))

if __name__=='__main__':promote()
