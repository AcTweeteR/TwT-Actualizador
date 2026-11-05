"""Build the setup stabilization candidate over the immutable Stable package."""
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
VERSION = '0.4.99~beta1'
FILES = ('setup.py', 'resources/lib/first_run.py', 'resources/lib/trakt_integration.py')
BASE_SHA = '8ec1ede1db5286b3f77f9a424d08db519c75f69757bda24021b27f42269564b9'


def build(output):
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    baseline = ROOT / 'repo' / ADDON / (ADDON + '-0.4.98.zip')
    if hashlib.sha256(baseline.read_bytes()).hexdigest() != BASE_SHA:
        raise ValueError('Stable baseline mismatch')
    with tempfile.TemporaryDirectory() as directory:
        stage = Path(directory)
        with zipfile.ZipFile(baseline) as archive:
            if archive.testzip() or any('..' in Path(n).parts or not n.startswith(ADDON + '/')
                                       for n in archive.namelist()):
                raise ValueError('Invalid baseline ZIP')
            archive.extractall(stage)
            before = {n: archive.read(n) for n in archive.namelist() if not n.endswith('/')}
        tree = stage / ADDON
        for relative in FILES:
            (tree / relative).write_bytes((ROOT / 'source/0.4.32/addons' / ADDON / relative).read_bytes())
        manifest = ET.parse(tree / 'addon.xml')
        manifest.getroot().set('version', VERSION)
        manifest.write(tree / 'addon.xml', encoding='utf-8', xml_declaration=True)
        for path in tree.rglob('*.py'):
            compile(path.read_bytes(), str(path), 'exec')
        for path in tree.rglob('*.xml'):
            ET.parse(path)
        zip_tree(tree, output, ADDON)
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert ET.fromstring(archive.read(ADDON + '/addon.xml')).get('version') == VERSION
        changed = {n for n in before if archive.read(n) != before[n]}
        assert changed == {ADDON + '/' + p for p in FILES + ('addon.xml',)}, changed
    return {'version': VERSION, 'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
            'changed': sorted(changed)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(build(parser.parse_args().output), indent=2))
