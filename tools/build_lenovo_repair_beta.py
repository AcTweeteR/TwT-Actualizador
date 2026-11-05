"""Build scoped Beta repairs from immutable Stable packages; preserve profiles."""
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from build_test_channel import zip_tree

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = {'service.actweeter': ('0.4.100', '0.4.101~beta1'),
            'plugin.video.xstream-pro': ('1.1.2.43', '1.1.2.44~beta1')}


def replace_once(src, old, new):
    if src.count(old) != 1:
        raise ValueError('ambiguous source fragment')
    return src.replace(old, new, 1)


def build(directory):
    output = Path(directory)
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    result = {}
    for aid, (stable, beta) in VERSIONS.items():
        source = ROOT / 'repo' / aid / (aid + '-' + stable + '.zip')
        target = output / (aid + '-' + beta + '.zip')
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            with zipfile.ZipFile(source) as archive:
                if archive.testzip() is not None:
                    raise ValueError('corrupt previous Stable')
                for member in archive.infolist():
                    if '..' in Path(member.filename).parts or not member.filename.startswith(aid + '/'):
                        raise ValueError('unsafe archive entry')
                    if member.is_dir():
                        continue
                    path = stage / member.filename
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(archive.read(member))
            tree = stage / aid
            if aid == 'service.actweeter':
                (tree / 'resources/lib/interface_layout.py').write_bytes((
                    ROOT / 'source/0.4.32/addons/service.actweeter/resources/lib/interface_layout.py').read_bytes())
            else:
                # XStream provider recommendations stay unchanged until a
                # runtime trace proves why the tablet filters them out.
                p = tree / 'resources/lib/premium_routes.py'
                s = p.read_text()
                old = """            # Require the stored identity to still belong to this provider.
            title = entry.get('title') or entry.get('name', '')
            candidates = [s for s in items if s.get('name') in (title, entry.get('name'))
                          or entry.get('name', '').startswith(s.get('name', '') + ' - ')]
            if not candidates:
                continue
"""
                new = """            # Match exact provider movie IDs from the saved URI first. A
            # title is not reliable after metadata/language changes.
            title = entry.get('title') or entry.get('name', '')
            candidates = [s for s in items if s.get('name') in (title, entry.get('name'))
                          or entry.get('name', '').startswith(s.get('name', '') + ' - ')]
            provider_match = re.search(r'/([0-9]+)\\.[A-Za-z0-9]+$',
                                       urlparse(entry.get('url', '')).path)
            if provider_match and kind == 'movie':
                exact = [s for s in items if provider_id(s, kind) == provider_match.group(1)]
                if len(exact) == 1:
                    candidates = exact
                elif len(exact) > 1:
                    continue
            if len(candidates) != 1:
                continue
"""
                s = replace_once(s, old, new)
                p.write_text(s)
            manifest = tree / 'addon.xml'
            addon = ET.parse(manifest).getroot()
            if addon.get('version') != stable:
                raise ValueError('unexpected base version')
            addon.set('version', beta)
            if aid == 'service.actweeter':
                dependency = addon.find("requires/import[@addon='plugin.video.xstream-pro']")
                if dependency is not None:
                    dependency.set('version', '1.1.2.43')
            ET.ElementTree(addon).write(manifest, encoding='utf-8', xml_declaration=True)
            for py in tree.rglob('*.py'):
                compile(py.read_bytes(), str(py), 'exec')
            zip_tree(tree, target, aid)
        with zipfile.ZipFile(target) as z:
            if z.testzip() is not None:
                raise ValueError('bad candidate')
        result[aid] = {'version': beta, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
    return result

if __name__ == '__main__':
    import sys
    print(json.dumps(build(sys.argv[1]), indent=2))
