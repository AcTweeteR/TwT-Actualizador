"""Reproducible, create-only service hotfix for inactive Skin Shortcuts branches."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from build_test_channel import zip_tree

ROOT = Path(__file__).resolve().parents[1]
ADDON = 'service.actweeter'
OLD = '0.4.101~beta5'
NEW = '0.4.101~beta6'
PATCHES = ('service.py',)
CHANGELOG = 'changelog-' + NEW + '.txt'


def build(output: Path) -> dict:
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError('refusing to overwrite Beta candidate')
    baseline = ROOT / 'docs/testing/repo' / ADDON / f'{ADDON}-{OLD}.zip'
    with zipfile.ZipFile(baseline) as archive:
        names = archive.namelist()
        if (archive.testzip() is not None or len(names) != len(set(names))
                or any(not n.startswith(ADDON + '/') or '..' in Path(n).parts for n in names)):
            raise ValueError('unsafe baseline ZIP')
        original = {n: archive.read(n) for n in names if not n.endswith('/')}
    with tempfile.TemporaryDirectory() as tmp:
        tree = Path(tmp) / ADDON
        for name, data in original.items():
            path = Path(tmp) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        for relative in PATCHES:
            replacement = (ROOT / 'source/0.4.32/addons' / ADDON / relative).read_bytes()
            (tree / relative).write_bytes(replacement)
        addon_file = tree / 'addon.xml'
        addon = ET.parse(addon_file)
        if addon.getroot().get('version') != OLD:
            raise ValueError('baseline service version changed')
        metadata = addon.find("./extension[@point='xbmc.addon.metadata']/news")
        if metadata is None or metadata.text != 'changelog-' + OLD + '.txt':
            raise ValueError('baseline changelog changed')
        addon.getroot().set('version', NEW)
        metadata.text = CHANGELOG
        addon.write(addon_file, encoding='utf-8', xml_declaration=True)
        (tree / CHANGELOG).write_text(
            'Beta: actualiza automáticamente el historial de TV al volver a Inicio '
            'sin necesitar RECARGAR; refresco limitado al widget activo.\n',
            encoding='utf-8')
        for file in tree.rglob('*.py'):
            compile(file.read_bytes(), str(file), 'exec')
        for file in tree.rglob('*.xml'):
            ET.parse(file)
        zip_tree(tree, output, ADDON)
    with zipfile.ZipFile(output) as candidate:
        if candidate.testzip() is not None:
            raise ValueError('candidate CRC failed')
        current = {n: candidate.read(n) for n in candidate.namelist() if not n.endswith('/')}
        changed = {n for n in original if original[n] != current.get(n)}
        added = set(current) - set(original)
        expected = {f'{ADDON}/addon.xml'} | {f'{ADDON}/{name}' for name in PATCHES}
        if changed != expected or added != {f'{ADDON}/{CHANGELOG}'}:
            raise ValueError('unexpected package delta %s %s' % (sorted(changed), sorted(added)))
        if ET.fromstring(current[f'{ADDON}/addon.xml']).get('version') != NEW:
            raise ValueError('candidate version mismatch')
    return {'package': output.name, 'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
            'changed': sorted(changed), 'added': sorted(added)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(build(parser.parse_args().output), indent=2))
