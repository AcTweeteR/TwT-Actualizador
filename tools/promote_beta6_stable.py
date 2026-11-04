#!/usr/bin/env python3
"""Build a create-only Stable candidate from the immutable Beta6 commit."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from xml.etree import ElementTree as ET

import promote_beta34_stable as common

ROOT = common.ROOT
SOURCE = '45d432f239afb520b28ec360b2ba85efb7e4f385'
PREVIOUS = '3f0f219bad7736ada4c33386c1b7af00db2536d973b9e3d409a1f7550873c8cf'
VERSIONS = {'skin.actweeter': ('1.2.36~beta5', '1.2.39'),
            'service.actweeter': ('0.4.97~beta4', '0.4.97'),
            'plugin.video.xstream-pro': ('1.1.2.39~beta6', '1.1.2.39')}
NOTES = {'skin.actweeter': b'1.2.39 Stable - Beta6 functionality.\n',
         'service.actweeter': b'0.4.97 Stable - Beta6 functionality.\n'}


def source_bytes(path):
    return subprocess.check_output(['git', 'show', SOURCE + ':' + str(path)], cwd=ROOT)


def build(output):
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError('candidate already exists')
    manifest_path = Path('manifests/actweeter-beta6-20261104.json')
    manifest = json.loads((ROOT / manifest_path).read_text())
    if manifest.get("source_commit") != SOURCE:
        raise ValueError("unexpected Beta source commit")
    if manifest['channel'] != 'testing' or set(manifest['components']) != set(VERSIONS):
        raise ValueError('unexpected Beta6 manifest')
    testing_path = Path('docs/testing/repo/addons.xml')
    if common.sha(source_bytes(testing_path)) != manifest['testing_index_sha256']:
        raise ValueError('Beta6 index hash mismatch')
    previous_index = source_bytes(Path('repo/addons.xml'))
    if common.sha(previous_index) != PREVIOUS:
        raise ValueError('Stable predecessor differs from source commit')
    old_index = ET.fromstring(previous_index)
    if tuple(a.get('id') for a in old_index) != common.EXPECTED_IDS:
        raise ValueError('unexpected Stable repository contents')
    output.mkdir(parents=True)
    index = ET.Element('addons')
    entries, assets = [], []
    for old in old_index:
        addon_id = old.get('id')
        if addon_id in VERSIONS:
            beta, stable = VERSIONS[addon_id]
            row = manifest['components'][addon_id]
            if row['version'] != beta or tuple(map(int, stable.split('.'))) <= tuple(map(int, old.get('version').split('.'))):
                raise ValueError('version is not an upgrade: ' + addon_id)
            relative = Path('docs/testing/repo') / addon_id / (addon_id + '-' + beta + '.zip')
            source = ROOT / relative
            if source.read_bytes() != source_bytes(relative) or common.sha(source.read_bytes()) != row['sha256']:
                raise ValueError('source ZIP differs from immutable Beta6: ' + addon_id)
            target_rel = Path('repo') / addon_id / (addon_id + '-' + stable + '.zip')
            target = output / target_rel
            target.parent.mkdir(parents=True, exist_ok=True)
            common.promote(source, target, addon_id, beta, stable,
                           ('1.1.2.36~beta4', VERSIONS['plugin.video.xstream-pro'][1]), NOTES)
            published = ROOT / target_rel
            if published.is_symlink() or (published.exists() and published.read_bytes() != target.read_bytes()):
                raise ValueError('Stable version already contains different bytes: ' + addon_id)
            addon = common.addon_from_zip(target, addon_id, stable)
            assets.extend(common.publish_metadata(target, addon, output))
        else:
            target_rel = Path('repo') / addon_id / (addon_id + '-' + old.get('version') + '.zip')
            target = ROOT / target_rel
            if target.read_bytes() != source_bytes(target_rel):
                raise ValueError('Stable repository asset differs from source commit: ' + addon_id)
            addon = common.addon_from_zip(target, addon_id, old.get('version'))
        for dep in addon.findall('requires/import'):
            if '~beta' in dep.get('version', '').lower():
                raise ValueError('Stable dependency points to Beta: ' + addon_id)
        index.append(addon)
        entries.append({'id': addon_id, 'version': addon.get('version'),
                        'path': str(target_rel), 'sha256': common.sha(target.read_bytes())})
    service = index.find("addon[@id='service.actweeter']")
    trakt = service.find("requires/import[@addon='script.trakt']")
    dep = service.find("requires/import[@addon='plugin.video.xstream-pro']")
    if trakt is None or trakt.get('optional') == 'true' or dep is None or dep.get('version') != '1.1.2.39':
        raise ValueError('required Service dependencies are not satisfied')
    data = ET.tostring(index, encoding='utf-8', xml_declaration=True) + b'\n'
    # A historical release must be reproducible even after newer Stable releases.
    # Its exact predecessor and source Beta remain pinned by git source commit.
    (output / 'repo/addons.xml').write_bytes(data)
    (output / 'repo/addons.xml.md5').write_text(hashlib.md5(data).hexdigest() + '\n')
    result = {'release': 'actweeter-stable-beta6', 'channel': 'stable', 'source_commit': SOURCE,
              'previous_index_sha256': PREVIOUS, 'beta_index_sha256': manifest['testing_index_sha256'],
              'index_sha256': common.sha(data), 'index_md5': hashlib.md5(data).hexdigest(),
              'addons': entries, 'assets': assets}
    (output / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.output_dir), indent=2))
