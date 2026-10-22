"""Private, read-only Trakt exports using XStream's own OAuth transport.

No tokens, account settings or provider URLs enter the export. This is not an
automatic restore: remote writes always require a separate reviewed plan.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile

from trakt_sync import IncompleteSnapshot, fetch_snapshot


def export_snapshot(get, directory, profile, *, cancelled=lambda: False):
    if not str(profile).isdigit() or int(profile) < 1:
        raise ValueError('invalid provider profile')
    pages = []

    def read(path, params):
        payload, count = get(path, params)
        # Preserve complete history/playback responses for a reviewed recovery.
        # Account settings can contain email/preferences and are not exported.
        if path.startswith('/sync/'):
            pages.append({'path': path, 'params': dict(params), 'pages': count, 'data': payload})
        return payload, count

    snapshot = fetch_snapshot(read, cancelled=cancelled)
    if cancelled():
        raise ValueError('export cancelled or provider profile changed')
    data = {'schema_version': 1, 'profile': str(profile), 'snapshot': snapshot, 'responses': pages}
    encoded = json.dumps(data, ensure_ascii=False, sort_keys=True, allow_nan=False).encode('utf-8')
    base = Path(directory)
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    if base.is_symlink() or base.stat().st_mode & 0o077:
        raise ValueError('private export directory required')
    target = Path(tempfile.mkdtemp(prefix='snapshot-', dir=str(base)))
    destination = target / 'snapshot.json'
    with destination.open('xb') as stream:
        os.chmod(destination, 0o600)
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    digest = hashlib.sha256(encoded).hexdigest()
    if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
        raise OSError('export integrity verification failed')
    summary = {'status': 'READ_ONLY_EXPORT_VERIFIED', 'sha256': digest,
               'records': len(snapshot['records']), 'history': len(snapshot['history']),
               'unidentified': snapshot['unidentified'], 'responses': len(pages)}
    with (target / 'manifest.json').open('x', encoding='utf-8') as stream:
        os.chmod(stream.name, 0o600)
        json.dump(summary, stream, sort_keys=True)
    return summary
