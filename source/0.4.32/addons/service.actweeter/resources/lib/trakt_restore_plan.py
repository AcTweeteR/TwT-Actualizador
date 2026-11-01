"""Persist a confirmed restore and reject stale data before an offline commit."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from .trakt_restore_commit import commit_staged_restore


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(directory, *, staged, active, expected_active_sha256, account, profile, confirmed):
    if confirmed is not True:
        raise PermissionError('explicit restore confirmation required')
    if not account or not str(profile).isdigit() or int(profile) < 1:
        raise ValueError('account and profile required')
    directory = Path(directory)
    if directory.exists() or directory.is_symlink() or directory.parent.is_symlink():
        raise ValueError('restore plan must be a new private directory')
    if len(staged) != 3 or len(active) != 3 or len(expected_active_sha256) != 3:
        raise ValueError('movie, episode and resume stores required')
    sources, targets = [Path(p) for p in staged], [Path(p) for p in active]
    if len({p.resolve() for p in targets}) != 3:
        raise ValueError('distinct active stores required')
    for path in sources + targets:
        if path.is_symlink() or path.parent.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError('unsafe restore store')
        if path.exists() and not isinstance(json.loads(path.read_text('utf-8')), dict):
            raise ValueError('invalid restore store')
    if any(not path.is_file() for path in sources):
        raise ValueError('staged stores must exist')
    if [_digest(p) if p.exists() else None for p in targets] != list(expected_active_sha256):
        raise RuntimeError('active store changed during preview')
    temporary = Path(tempfile.mkdtemp(prefix='.restore-plan-', dir=str(directory.parent)))
    os.chmod(temporary, 0o700)
    try:
        for index, source in enumerate(sources):
            target = temporary / ('staged_%d.json' % index)
            with source.open('rb') as reader, target.open('xb') as writer:
                os.chmod(target, 0o600)
                shutil.copyfileobj(reader, writer)
                writer.flush()
                os.fsync(writer.fileno())
        if [_digest(p) if p.exists() else None for p in targets] != list(expected_active_sha256):
            raise RuntimeError('active store changed while staging')
        manifest = {'schema': 1, 'account': account, 'profile': str(profile),
                    'active': [str(p.resolve()) for p in targets],
                    'active_sha256': list(expected_active_sha256),
                    'staged_sha256': [_digest(temporary / ('staged_%d.json' % i)) for i in range(3)]}
        with (temporary / 'plan.json').open('x', encoding='utf-8') as stream:
            os.chmod(temporary / 'plan.json', 0o600)
            json.dump(manifest, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        fd = os.open(str(temporary), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        os.rename(temporary, directory)
        fd = os.open(str(directory.parent), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return manifest


def apply(directory, *, active, backup_directory, account, profile, kodi_stopped):
    if kodi_stopped is not True:
        raise PermissionError('Kodi must be stopped before committing stores')
    directory = Path(directory)
    plan = directory / 'plan.json'
    if directory.is_symlink() or plan.is_symlink() or not plan.is_file():
        raise ValueError('unsafe restore plan')
    manifest = json.loads(plan.read_text('utf-8'))
    if (manifest.get('schema') != 1 or manifest.get('account') != account
            or manifest.get('profile') != str(profile)):
        raise PermissionError('restore account or profile changed')
    if any(len(manifest.get(key, [])) != 3 for key in ('active', 'active_sha256', 'staged_sha256')):
        raise ValueError('invalid restore plan')
    staged = [directory / ('staged_%d.json' % i) for i in range(3)]
    active = [Path(value) for value in active]
    if len(active) != 3 or [str(p.resolve()) for p in active] != manifest['active']:
        raise ValueError('restore targets differ from confirmed plan')
    for path, expected in zip(staged, manifest['staged_sha256']):
        if path.is_symlink() or not path.is_file() or _digest(path) != expected:
            raise ValueError('staged restore changed')
    for path, expected in zip(active, manifest['active_sha256']):
        if path.is_symlink() or path.parent.is_symlink():
            raise ValueError('unsafe active store')
        actual = _digest(path) if path.is_file() else None
        if actual != expected or (path.exists() and not path.is_file()):
            raise RuntimeError('active store changed after preview')
    # A caller's flag cannot prevent Kodi from reopening the stores during commit.
    raise PermissionError('restore application disabled until store exclusion is verified')
