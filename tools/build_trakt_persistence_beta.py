"""Reproducible minimal XStream Beta patch; never edits installed Kodi profiles."""
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from build_test_channel import zip_tree

ROOT = Path(__file__).resolve().parents[1]
ADDON = 'plugin.video.xstream-pro'
BASE = '1.1.2.41'
BETA = '1.1.2.42~beta1'
BASE_SHA = '8d4404087ddc9b5640eb64a905df6c3372274b02a95c0080a9d46f6f07dad137'

def replace_once(src, old, new):
    if src.count(old) != 1:
        raise ValueError('ambiguous patch source')
    return src.replace(old, new, 1)

def build(output):
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    baseline = ROOT / 'repo' / ADDON / f'{ADDON}-{BASE}.zip'
    if hashlib.sha256(baseline.read_bytes()).hexdigest() != BASE_SHA:
        raise ValueError('baseline hash mismatch')
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        with zipfile.ZipFile(baseline) as arc:
            if arc.testzip() is not None or any('..' in Path(x).parts for x in arc.namelist()):
                raise ValueError('bad baseline')
            arc.extractall(stage)
            original = {n: arc.read(n) for n in arc.namelist() if not n.endswith('/')}
        tree = stage / ADDON
        path = tree / 'resources/lib/trakt.py'
        source = path.read_text()
        source = replace_once(source,
            '''    if resp.status_code in (400, 401, 403):
        clear_tokens()
        return False
''',
            '''    if resp.status_code in (400, 401, 403):
        # A failed refresh is not user consent to disconnect. Retain the
        # original access/refresh pair so transient errors or OAuth client
        # configuration changes never silently erase a working login.
        # Explicit disconnect remains the only path to clear_tokens().
        _log("Trakt refresh rejected; stored authorization preserved", xbmc.LOGWARNING)
        return False
''')
        path.write_text(source)
        route = tree / 'resources/lib/tmdb_routes.py'
        source = route.read_text()
        source = replace_once(source,
            '''            if not data["results"]:
                xbmcplugin.setContent(c("addon_handle"), content)
                xbmcplugin.endOfDirectory(c("addon_handle"), succeeded=True,
                                          updateListing=False, cacheToDisc=False)
                return
''',
            '''            if not data["results"]:
                # An empty provider intersection must not make the entire
                # recommendations widget disappear. Never show unmatched
                # titles as playable IPTV items.
                _add_items([_folder_item("Sin recomendaciones disponibles en tu catálogo",
                                         {"mode": "xstream_tmdb_trakt_menu"}, "recommended")], "videos")
                return
''')
        source = replace_once(source,
            '''        if section == "recommendations":
            c("_log")("Trakt recommendations unavailable: {0}".format(type(exc).__name__))
            xbmcplugin.endOfDirectory(c("addon_handle"), succeeded=True,
                                      updateListing=False, cacheToDisc=False)
            return
''',
            '''        if section == "recommendations":
            c("_log")("Trakt recommendations unavailable: {0}".format(type(exc).__name__))
            _add_items([_folder_item("Recomendaciones temporalmente no disponibles",
                                     {"mode": "xstream_tmdb_trakt_menu"}, "recommended")], "videos")
            return
''')
        route.write_text(source)
        manifest = tree/'addon.xml'
        old = manifest.read_text()
        manifest.write_text(replace_once(old, f'version="{BASE}"', f'version="{BETA}"'))
        note = f'changelog-{BETA}.txt'
        (tree/note).write_text('Trakt: preservar credenciales ante errores de renovación; conservar fila de recomendaciones con estado explicativo cuando no hay coincidencias o falla la API. No altera el filtro de disponibilidad ni los perfiles.\n')
        for py in tree.rglob('*.py'):
            compile(py.read_bytes(),str(py),'exec')
        zip_tree(tree,output,ADDON)
    with zipfile.ZipFile(output) as arc:
        assert arc.testzip() is None
        addon = ET.fromstring(arc.read(f'{ADDON}/addon.xml'))
        assert addon.get('version') == BETA
        changed = {n for n in original if arc.read(n)!=original[n]}
        expected = {ADDON+'/addon.xml',ADDON+'/resources/lib/trakt.py',ADDON+'/resources/lib/tmdb_routes.py'}
        assert changed == expected, (changed, expected)
    return {'version': BETA, 'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'changed':sorted(changed)}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    print(json.dumps(build(p.parse_args().output),indent=2))
