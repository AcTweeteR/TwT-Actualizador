"""Checksummed, stopped-Kodi transaction for XStream watched/resume stores."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid


def _sync_directory(directory):
    fd = os.open(str(directory), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _paths(active_movie, active_episode, active_resume=None):
    return tuple(Path(path) for path in (active_movie, active_episode, active_resume)
                 if path is not None)


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_original(original, target):
    temp = target.with_name(target.name + '.trakt-recover-' + uuid.uuid4().hex)
    with original.open('rb') as source, temp.open('xb') as output:
        os.chmod(temp, 0o600)
        shutil.copyfileobj(source, output)
        output.flush()
        os.fsync(output.fileno())
    os.replace(temp, target)
    _sync_directory(target.parent)


def recover_interrupted_restore(*, backup_directory, active_movie, active_episode,
                                active_resume=None, kodi_stopped):
    """Restore a pending transaction only when active files match known states."""
    if kodi_stopped is not True:
        raise PermissionError('Kodi must be stopped for restore recovery')
    backup = Path(backup_directory)
    marker = backup / 'transaction.pending'
    manifest_path = backup / 'transaction.json'
    if backup.is_symlink() or marker.is_symlink() or manifest_path.is_symlink():
        raise ValueError('unsafe restore transaction path')
    if not marker.exists():
        return False
    targets = _paths(active_movie, active_episode, active_resume)
    if any(path.is_symlink() or path.parent.is_symlink() or not path.parent.is_dir()
           for path in targets):
        raise ValueError('unsafe recovery target')
    if not manifest_path.exists():
        # Legacy two-store transactions predate checksummed manifests.
        if active_resume is not None:
            raise ValueError('legacy transaction cannot recover a resume store')
        originals = (backup / 'original_0.json', backup / 'original_1.json')
        if any(path.is_symlink() or not path.is_file() for path in originals):
            raise ValueError('missing legacy restore originals')
        for original, target in zip(originals, targets):
            _write_original(original, target)
    else:
        manifest = json.loads(manifest_path.read_text('utf-8'))
        count = len(targets)
        if (manifest.get('schema') != 1
                or manifest.get('targets') != [str(path) for path in targets]
                or any(len(manifest.get(key, [])) != count for key in
                       ('original_exists', 'original_sha256', 'staged_sha256'))):
            raise ValueError('restore manifest does not match targets')
        for i, (target, existed, original_hash, staged_hash) in enumerate(zip(
                targets, manifest['original_exists'], manifest['original_sha256'],
                manifest['staged_sha256'])):
            original = backup / ('original_%d.json' % i)
            if original.is_symlink():
                raise ValueError('unsafe restore backup')
            if target.exists():
                if not target.is_file() or _digest(target) not in tuple(
                        digest for digest in (original_hash, staged_hash) if digest):
                    raise RuntimeError('active store changed; refusing recovery overwrite')
            elif existed:
                raise RuntimeError('active store disappeared; refusing recovery overwrite')
            if existed:
                if (not original.is_file() or _digest(original) != original_hash):
                    raise ValueError('restore backup checksum mismatch')
                _write_original(original, target)
            elif target.exists():
                target.unlink()
                _sync_directory(target.parent)
    marker.unlink()
    _sync_directory(backup)
    return True


def commit_staged_restore(*, staged_movie, staged_episode, active_movie, active_episode,
                          backup_directory, kodi_stopped, staged_resume=None,
                          active_resume=None):
    if kodi_stopped is not True:
        raise PermissionError('Kodi must be stopped before committing stores')
    if (staged_resume is None) != (active_resume is None):
        raise ValueError('staged and active resume stores must be supplied together')
    sources = tuple(Path(path) for path in (staged_movie, staged_episode, staged_resume)
                    if path is not None)
    targets = _paths(active_movie, active_episode, active_resume)
    backup = Path(backup_directory)
    if backup.exists() or backup.is_symlink():
        raise FileExistsError('backup directory must not exist')
    if (len({path.resolve() for path in targets}) != len(targets)
            or len({path.resolve() for path in sources}) != len(sources)):
        raise ValueError('distinct stores required')
    if any(path.is_symlink() or not path.is_file() for path in sources):
        raise ValueError('staged stores must be regular files')
    if any(path.is_symlink() or (path.exists() and not path.is_file())
           or path.parent.is_symlink() or not path.parent.is_dir() for path in targets):
        raise ValueError('active stores must be regular files when present')
    if any(source.resolve() == target.resolve() for source in sources for target in targets):
        raise ValueError('staging cannot be active storage')
    if any(not isinstance(json.loads(path.read_text('utf-8')), dict)
           for path in sources + tuple(path for path in targets if path.exists())):
        raise ValueError('watched/resume stores must contain JSON objects')
    if any(backup == path or backup in path.parents for path in sources + targets):
        raise ValueError('backup cannot contain watched stores')
    if backup.parent.is_symlink() or not backup.parent.is_dir():
        raise ValueError('unsafe backup parent directory')

    backup.mkdir(mode=0o700, parents=False)
    originals = [backup / ('original_%d.json' % i) for i in range(len(targets))]
    existed = [path.exists() for path in targets]
    try:
        for target, original, was_present in zip(targets, originals, existed):
            if was_present:
                shutil.copy2(target, original)
                os.chmod(original, 0o600)
                with original.open('rb') as stream:
                    os.fsync(stream.fileno())
            else:
                marker = original.with_suffix('.missing')
                with marker.open('x', encoding='utf-8') as stream:
                    stream.flush()
                    os.fsync(stream.fileno())
    except BaseException:
        shutil.rmtree(backup)
        raise
    _sync_directory(backup)
    manifest = {'schema': 1, 'status': 'prepared',
        'targets': [str(path) for path in targets], 'original_exists': existed,
        'original_sha256': [_digest(path) if present else None
                            for path, present in zip(targets, existed)],
        'staged_sha256': [_digest(path) for path in sources]}
    manifest_path = backup / 'transaction.json'
    with manifest_path.open('x', encoding='utf-8') as stream:
        os.chmod(manifest_path, 0o600)
        json.dump(manifest, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    _sync_directory(backup)
    pending = backup / 'transaction.pending'
    with pending.open('x', encoding='utf-8') as stream:
        stream.write('rollback-required')
        stream.flush()
        os.fsync(stream.fileno())
    _sync_directory(backup)

    temps, replaced = [], []
    try:
        for source, target in zip(sources, targets):
            temp = target.with_name(target.name + '.trakt-' + uuid.uuid4().hex + '.tmp')
            with source.open('rb') as inp, temp.open('xb') as out:
                os.chmod(temp, 0o600)
                shutil.copyfileobj(inp, out)
                out.flush()
                os.fsync(out.fileno())
            temps.append(temp)
        for temp, target in zip(temps, targets):
            os.replace(temp, target)
            replaced.append(target)
            _sync_directory(target.parent)
        if any(_digest(source) != _digest(target) for source, target in zip(sources, targets)):
            raise OSError('restore verification failed')
    except BaseException:
        if replaced:
            recover_interrupted_restore(backup_directory=backup, active_movie=targets[0],
                active_episode=targets[1], active_resume=targets[2] if len(targets) == 3 else None,
                kodi_stopped=True)
        raise
    finally:
        for temp in temps:
            if temp.exists():
                temp.unlink()
    manifest['status'] = 'committed'
    with manifest_path.open('w', encoding='utf-8') as stream:
        json.dump(manifest, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    _sync_directory(backup)
    pending.unlink()
    _sync_directory(backup)
    return {'committed': True, 'backups': [str(path) for path in originals]}


def rollback_committed_restore(*, backup_directory, active_movie, active_episode,
                               active_resume=None, kodi_stopped):
    if kodi_stopped is not True:
        raise PermissionError('Kodi must be stopped before rollback')
    backup = Path(backup_directory)
    manifest_path = backup / 'transaction.json'
    if backup.is_symlink() or manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError('invalid restore manifest')
    manifest = json.loads(manifest_path.read_text('utf-8'))
    targets = _paths(active_movie, active_episode, active_resume)
    count = len(targets)
    if (manifest.get('schema') != 1 or manifest.get('status') != 'committed'
            or manifest.get('targets') != [str(path) for path in targets]
            or any(len(manifest.get(key, [])) != count for key in
                   ('staged_sha256', 'original_sha256', 'original_exists'))):
        raise ValueError('restore transaction does not match active stores')
    for target, digest in zip(targets, manifest['staged_sha256']):
        if target.is_symlink() or not target.is_file() or _digest(target) != digest:
            raise RuntimeError('active store changed; refusing rollback')
    for i, (exists, digest) in enumerate(zip(manifest['original_exists'], manifest['original_sha256'])):
        original = backup / ('original_%d.json' % i)
        if exists and (original.is_symlink() or not original.is_file() or _digest(original) != digest):
            raise ValueError('restore backup checksum mismatch')
        missing = original.with_suffix('.missing')
        if not exists and (original.exists() or original.is_symlink()
                           or missing.is_symlink() or not missing.is_file()):
            raise ValueError('restore backup is incomplete')
    marker = backup / 'transaction.pending'
    with marker.open('x', encoding='utf-8') as stream:
        stream.write('rollback-required')
        stream.flush()
        os.fsync(stream.fileno())
    _sync_directory(backup)
    return recover_interrupted_restore(backup_directory=backup,
        active_movie=targets[0], active_episode=targets[1],
        active_resume=targets[2] if count == 3 else None, kodi_stopped=True)
