#!/usr/bin/env python3
"""Create-only Stable Service 0.4.99 from the exact published Beta4 package.

The functional ZIP payload is immutable. Historical Stable packages and
unrelated add-ons are preserved exactly; only release metadata changes.
"""
from __future__ import annotations
import hashlib
import json
import stat
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'source/0.4.32/tools'))
from build_distribution_index import addon_from_zip

ADDON = 'service.actweeter'
BETA = '0.4.99~beta4'
STABLE = '0.4.99'
BETA_SHA256 = '750ce627ae200fda96de96779ce24a4f8f2d6d034a16b5a9ded0141b843f89a1'
PREVIOUS_INDEX_SHA256 = 'ac4bffccee2d60b1bd05eeafb33c1e7b037c881c030b16b67e9faef4d206412a'
RELEASE = 'actweeter-stable-stabilization-20261105'
NOTES = ("AcTweeteR Service 0.4.99 Stable (2026-11-05).\n"
         "Conserva la configuración completada y las decisiones Trakt al actualizar.\n"
         "Tráilers automáticos: admite identidad por título y año en widgets.\n"
         "tvOS: desactiva la gestión del servidor integrado incompatible de Rivulet,\n"
         "sin cambiar su servidor externo ni su cuenta. Validación tvOS pendiente.\n").encode()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build(output: Path) -> dict:
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError('refusing to overwrite output directory')
    beta = ROOT / 'docs/testing/repo' / ADDON / f'{ADDON}-{BETA}.zip'
    if sha(beta.read_bytes()) != BETA_SHA256:
        raise ValueError('Beta4 source ZIP hash mismatch')
    addon_from_zip(beta, ADDON, BETA)
    before = (ROOT / 'repo/addons.xml').read_bytes()
    if sha(before) != PREVIOUS_INDEX_SHA256:
        archive = ROOT / 'manifests/archive/epg-watched-perf-stable-addons-20261105.xml'
        before = archive.read_bytes()
        if sha(before) != PREVIOUS_INDEX_SHA256:
            raise ValueError('previous Stable index does not match expected predecessor')
    root = ET.fromstring(before)
    service = root.find(f"addon[@id='{ADDON}']")
    if service is None or service.get('version') != '0.4.98':
        raise ValueError('unexpected existing Stable Service')
    dest = output / 'repo' / ADDON / f'{ADDON}-{STABLE}.zip'
    dest.parent.mkdir(parents=True)
    with zipfile.ZipFile(beta) as source, zipfile.ZipFile(dest, 'x') as target:
        infos = source.infolist()
        for entry in infos:
            data = source.read(entry)
            if entry.filename == f'{ADDON}/addon.xml':
                original = f'version="{BETA}"'.encode()
                if data.count(original) != 1:
                    raise ValueError('Beta manifest version not unique')
                data = data.replace(original, f'version="{STABLE}"'.encode())
                former = b'<news>changelog-0.4.98.txt</news>'
                if data.count(former) != 1:
                    raise ValueError('unexpected Beta changelog reference')
                data = data.replace(former, f'<news>changelog-{STABLE}.txt</news>'.encode())
                # Ensure Stable's existing XStream meets the published dependency.
                service_old = root.find(f"addon[@id='plugin.video.xstream-pro']")
                stable_xstream = tuple(map(int, service_old.get('version').split('.')))
                dep_xml = ET.fromstring(data).find("requires/import[@addon='plugin.video.xstream-pro']")
                minimum = tuple(map(int, dep_xml.get('version').split('.')))
                if stable_xstream < minimum:
                    raise ValueError('Stable XStream would not meet Service dependency')
            target.writestr(entry, data)
        release_note = zipfile.ZipInfo(f'{ADDON}/changelog-{STABLE}.txt', infos[0].date_time)
        release_note.compress_type = zipfile.ZIP_DEFLATED
        release_note.external_attr = (stat.S_IFREG | 0o644) << 16
        target.writestr(release_note, NOTES)
    addon = addon_from_zip(dest, ADDON, STABLE)
    if zipfile.ZipFile(dest).testzip() is not None:
        raise ValueError('Stable package corrupt')
    service_index = list(root).index(service)
    root.remove(service)
    root.insert(service_index, addon)
    # Stable metadata assets must be served alongside the ZIP.
    metadata = addon.find("extension[@point='xbmc.addon.metadata']")
    assets = []
    for filename in [metadata.findtext('news')] + [x.text for x in metadata.findall('assets/*')]:
        if not filename or filename.startswith('/') or '..' in Path(filename).parts:
            raise ValueError('unsafe metadata reference')
        data = zipfile.ZipFile(dest).read(f'{ADDON}/{filename}')
        target = output / 'repo' / ADDON / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        assets.append({'path':str(target.relative_to(output)), 'sha256':sha(data)})
    index_data = ET.tostring(root, encoding='utf-8', xml_declaration=True) + b'\n'
    (output / 'repo/addons.xml').write_bytes(index_data)
    (output / 'repo/addons.xml.md5').write_text(hashlib.md5(index_data).hexdigest() + '\n')
    entries=[]
    for item in root:
        aid, version = item.get('id'), item.get('version')
        file = output / 'repo' / aid / f'{aid}-{version}.zip' if aid == ADDON else ROOT / 'repo' / aid / f'{aid}-{version}.zip'
        with zipfile.ZipFile(file) as archive:
            if archive.testzip() is not None:
                raise ValueError('invalid package ' + aid)
        entries.append({'id':aid,'version':version,'path':f'repo/{aid}/{aid}-{version}.zip','sha256':sha(file.read_bytes())})
    manifest={'release':RELEASE,'channel':'stable','release_date':'2026-11-05',
              'beta_version':BETA,'beta_sha256':BETA_SHA256,
              'previous_index_sha256':PREVIOUS_INDEX_SHA256,
              'index_sha256':sha(index_data),'index_md5':hashlib.md5(index_data).hexdigest(),
              'addons':entries,'assets':assets,'runtime_tvos_verified':False}
    (output/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2,ensure_ascii=False)+'\n')
    return manifest

if __name__ == '__main__':
    if len(sys.argv) != 2: raise SystemExit('Usage: script OUTPUT_DIR')
    result=build(Path(sys.argv[1]))
    print(json.dumps({'release':result['release'],'sha256':result['index_sha256'],'service_version':STABLE}, indent=2))
