"""Read-only recovery audit of local verified Trakt exports; no Kodi/Trakt writes."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

LIB = Path(__file__).resolve().parents[1] / 'source/0.4.32/addons/service.actweeter/resources/lib'
sys.path.insert(0, str(LIB))
from trakt_sync import import_plan


def load_export(folder):
    path = Path(folder)
    raw = (path / 'snapshot.json').read_bytes()
    manifest = json.loads((path / 'manifest.json').read_text('utf-8'))
    if hashlib.sha256(raw).hexdigest() != manifest['sha256']:
        raise ValueError('export checksum mismatch')
    data = json.loads(raw)
    snap = data['snapshot']
    if not isinstance(snap.get('records'), dict) or not isinstance(snap.get('history'), list):
        raise ValueError('incomplete export')
    if not isinstance(snap.get('account'), str) or not snap['account']:
        raise ValueError('missing account')
    return data


def resume_fingerprint(data):
    records = data['snapshot']['records']
    return {key: (item['paused_at'], item['progress']) for key, item in records.items()
            if isinstance(item, dict) and item.get('paused_at') is not None}


def audit(folders):
    exports = [load_export(path) for path in folders]
    accounts = {x['snapshot']['account'] for x in exports}
    profiles = {str(x['profile']) for x in exports}
    if len(accounts) != 1 or len(profiles) != 1:
        raise ValueError('account/profile mismatch across exports')
    fingerprints = [resume_fingerprint(x) for x in exports]
    baseline = fingerprints[0]
    # No identity or percentage is printed: private history stays on the Mac.
    if any(x != baseline for x in fingerprints[1:]):
        raise ValueError('resume states differ between exports')
    latest = exports[-1]['snapshot']
    plan = import_plan(latest, [], profile=exports[-1]['profile'],
                       account=latest['account'])
    if plan['items']:
        raise ValueError('unverified provider catalog produced importable items')
    return {'exports': len(exports), 'matching_resume_records': len(baseline),
            'account_profile_consistent': True, 'resume_exactly_preserved': True,
            'unverified_provider_imports': len(plan['items']), 'remote_writes': 0,
            'kodi_store_writes': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('folders', nargs='+')
    print(json.dumps(audit(parser.parse_args().folders), sort_keys=True))
