"""Deterministic, create-only Beta packages for native Trakt Favorites/Watchlist."""
import hashlib
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from build_test_channel import zip_tree
from enable_native_collections_patch import patch

ROOT=Path(__file__).resolve().parents[1]
VERSIONS={
    'service.actweeter':('0.4.104~beta1','0.4.104~beta2'),
    'plugin.video.xstream-pro':('1.1.2.44~beta8','1.1.2.44~beta9'),
}


def build(aid, output):
    if aid not in VERSIONS:raise ValueError('not an approved candidate')
    old,new=VERSIONS[aid]
    output=Path(output)
    if output.exists() or output.is_symlink():raise FileExistsError('create-only release')
    baseline=ROOT/'docs/testing/repo'/aid/(aid+'-'+old+'.zip')
    with zipfile.ZipFile(baseline) as oldzip:
        if oldzip.testzip() is not None:raise ValueError('corrupt parent ZIP')
        original={name:oldzip.read(name) for name in oldzip.namelist() if not name.endswith('/')}
        if len(original)!=sum(not n.endswith('/') for n in oldzip.namelist()):raise ValueError('duplicate ZIP entries')
        if any(not n.startswith(aid+'/') or '..' in Path(n).parts for n in original):raise ValueError('unsafe ZIP member')
    relative=('resources/lib/collection_catalog.py' if aid=='service.actweeter'
              else 'resources/lib/trakt_auto_routes.py')
    with tempfile.TemporaryDirectory() as tmp:
        for member,data in original.items():
            path=Path(tmp)/member;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        tree=Path(tmp)/aid
        payload=tree/relative
        if aid=='service.actweeter':
            payload.write_bytes((ROOT/'source/0.4.32/addons/service.actweeter'/relative).read_bytes())
        else:
            payload.write_text(patch(payload.read_text(encoding='utf-8')),encoding='utf-8')
        manifest=tree/'addon.xml'
        xml=ET.parse(manifest)
        if xml.getroot().get('id')!=aid or xml.getroot().get('version')!=old:
            raise ValueError('parent manifest mismatch')
        xml.getroot().set('version',new)
        if aid=='service.actweeter':
            news=xml.find("./extension[@point='xbmc.addon.metadata']/news")
            if news is None or news.text!='changelog-'+old+'.txt':raise ValueError('missing service changelog')
            news.text='changelog-'+new+'.txt'
            (tree/news.text).write_text(
                'Beta: sincronización Trakt bidireccional de Favoritos y Pendientes. '
                'Vinculación automática solo con importación y exportación autorizadas. '
                'Primera sincronización sin borrados: solo identidades TMDb verificadas.\n',encoding='utf-8')
        xml.write(manifest,encoding='utf-8',xml_declaration=True)
        for f in tree.rglob('*.py'):compile(f.read_bytes(),str(f),'exec')
        for f in tree.rglob('*.xml'):ET.parse(f)
        zip_tree(tree,output,aid)
    with zipfile.ZipFile(output) as result:
        if result.testzip() is not None:raise ValueError('bad CRC')
        newer={n:result.read(n) for n in result.namelist() if not n.endswith('/')}
        changed={n for n in original if original[n]!=newer.get(n)}
        added=set(newer)-set(original)
        expected={aid+'/addon.xml',aid+'/'+relative}
        if changed!=expected or added!=({aid+'/changelog-'+new+'.txt'} if aid=='service.actweeter' else set()):
            raise ValueError('unexpected package delta '+str((changed,added)))
        if ET.fromstring(newer[aid+'/addon.xml']).get('version')!=new:
            raise ValueError('version not embedded')
    return {'addon':aid,'version':new,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
            'bytes':output.stat().st_size,'changed':sorted(changed),'added':sorted(added)}

if __name__=='__main__':
    target=Path(sys.argv[1])
    target.mkdir(exist_ok=True,parents=True)
    if any((target/a/(a+'-'+new+'.zip')).exists() for a,(old,new) in VERSIONS.items()):
        raise FileExistsError('candidate already exists')
    for aid,(old,new) in VERSIONS.items():
        path=target/aid/(aid+'-'+new+'.zip');path.parent.mkdir(exist_ok=True,parents=True)
        print(json.dumps(build(aid,path),sort_keys=True))
