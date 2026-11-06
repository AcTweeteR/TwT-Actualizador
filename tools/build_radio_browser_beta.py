#!/usr/bin/env python3
"""Create-only AcTweeteR Beta integration of official, UNMODIFIED Radio Browser."""
from __future__ import annotations
import hashlib
import io
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from build_test_channel import zip_tree

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'source/0.4.32/addons'
FEED = ROOT / 'docs/testing/repo'
RELEASES = {
    'service.actweeter': ('0.4.103~beta1', '0.4.104~beta1',
        ('resources/lib/interface_layout.py', 'resources/lib/module_catalog.py')),
    'skin.actweeter': ('1.2.43~beta3', '1.2.44~beta1',
        ('1080i/IncludesBingie.xml', 'shortcuts/mainmenu.DATA.xml')),
}
NEW_FILES = {'skin.actweeter': ('shortcuts/radio.DATA.xml',)}


def checked_archive(source: Path, addon_id: str):
    with zipfile.ZipFile(source) as archive:
        names = archive.namelist()
        if archive.testzip() or len(names) != len(set(names)) or any(
                not name.startswith(addon_id + '/') or
                '..' in Path(name).parts or Path(name).is_absolute()
                for name in names):
            raise ValueError('invalid original archive')
        return {name: archive.read(name) for name in names if not name.endswith('/')}


def make_candidate(addon_id, old_version, new_version, patches, output, *, service_version):
    source = FEED / addon_id / f'{addon_id}-{old_version}.zip'
    original = checked_archive(source, addon_id)
    if ET.fromstring(original[f'{addon_id}/addon.xml']).get('version') != old_version:
        raise ValueError('source version drift')
    with tempfile.TemporaryDirectory() as temp:
        tree = Path(temp) / addon_id
        for entry, contents in original.items():
            dest = Path(temp) / entry
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(contents)
        for relative in patches + NEW_FILES.get(addon_id, ()):
            dest = tree / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SRC / addon_id / relative, dest)
        metadata = ET.parse(tree / 'addon.xml')
        metadata.getroot().set('version', new_version)
        news = metadata.find("./extension[@point='xbmc.addon.metadata']/news")
        if news is None:
            raise ValueError('missing changelog node')
        changelog = 'changelog-' + new_version + '.txt'
        news.text = changelog
        requires = metadata.find('./requires')
        if addon_id == 'service.actweeter':
            if requires.find("import[@addon='plugin.audio.radiobrowser']") is not None:
                raise ValueError('duplicate Radio Browser dependency')
            ET.SubElement(requires, 'import', {'addon':'plugin.audio.radiobrowser', 'version':'2.0.0'})
            note = ('Radio Browser official via Kodi dependencies; native Spain/country/favorites routes; '
                    'versioned, backed-up menu migration. No changes to provider or Radio Browser code.\n')
        else:
            service = requires.find("import[@addon='service.actweeter']")
            if service is None:
                raise ValueError('missing service dependency')
            service.set('version', service_version)
            note = ('RADIO below TV, Spain first, native countries/favorites/search submenu. '
                    'Input mode remains under Skin Settings > General; 9 menu items fit above power.\n')
        metadata.write(tree/'addon.xml', encoding='utf-8', xml_declaration=True)
        (tree/changelog).write_text(note, encoding='utf-8')
        for file in tree.rglob('*.py'):
            compile(file.read_bytes(), str(file), 'exec')
        for file in tree.rglob('*.xml'):
            ET.parse(file)
        zip_tree(tree, output, addon_id)
    updated = checked_archive(output, addon_id)
    expected_changes = {f'{addon_id}/addon.xml'} | {f'{addon_id}/{part}' for part in patches}
    expected_additions = {f'{addon_id}/{changelog}'} | {
        f'{addon_id}/{part}' for part in NEW_FILES.get(addon_id, ())}
    changes = {name for name in original if updated.get(name) != original[name]}
    additions = set(updated).difference(original)
    if changes != expected_changes or additions != expected_additions:
        raise ValueError(f'unexpected delta: changed={changes ^ expected_changes}, added={additions ^ expected_additions}')
    if ET.fromstring(updated[f'{addon_id}/addon.xml']).get('version') != new_version:
        raise ValueError('invalid new version')
    return {'id':addon_id, 'version':new_version,
            'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
            'changed':sorted(changes), 'added':sorted(additions)}


def build():
    root = ET.parse(FEED/'addons.xml').getroot()
    nodes = {addon.get('id'): addon for addon in root}
    for addon_id, (old, new, _) in RELEASES.items():
        if nodes[addon_id].get('version') != old:
            raise ValueError(f'Testing feed advanced: {addon_id}')
        if (FEED/addon_id/f'{addon_id}-{new}.zip').exists():
            raise FileExistsError(f'candidate exists: {addon_id}-{new}')
    output = []
    with tempfile.TemporaryDirectory() as temp:
        for addon_id, (old, new, patches) in RELEASES.items():
            target = Path(temp) / f'{addon_id}-{new}.zip'
            result = make_candidate(addon_id, old, new, patches, target,
                                  service_version=RELEASES['service.actweeter'][1])
            output.append((addon_id, result, target.read_bytes()))
    # Atomic preflight: both candidates validated BEFORE any feed mutation.
    for addon_id, result, payload in output:
        version = result['version']
        destination = FEED / addon_id / f'{addon_id}-{version}.zip'
        with destination.open('xb') as file:
            file.write(payload)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            record = ET.fromstring(archive.read(f'{addon_id}/addon.xml'))
            changelog = f'changelog-{version}.txt'
            (FEED/addon_id/changelog).write_bytes(archive.read(f'{addon_id}/{changelog}'))
        original = nodes[addon_id]
        index = list(root).index(original)
        root.remove(original)
        root.insert(index, record)
    serialized = ET.tostring(root, encoding='utf-8', xml_declaration=True) + b'\n'
    serialized = b'\n'.join(line.rstrip() for line in serialized.split(b'\n'))
    (FEED/'addons.xml').write_bytes(serialized)
    (FEED/'addons.xml.md5').write_text(hashlib.md5(serialized).hexdigest()+'\n')
    print(json.dumps([result for _, result, _ in output], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    build()
