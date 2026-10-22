"""Reversible, stopped-Kodi watched-store commit with rollback on failure.

The caller must stop Kodi before invoking this function. No network activity.
"""
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


def recover_interrupted_restore(*, backup_directory, active_movie, active_episode, kodi_stopped):
    """Recover a durable pending transaction after a process or power failure."""
    if kodi_stopped is not True:
        raise PermissionError("Kodi must be stopped for recovery")
    backup = Path(backup_directory)
    if backup.is_symlink():
        raise ValueError("unsafe backup directory")
    marker = backup / "transaction.pending"
    if marker.is_symlink():
        raise ValueError("unsafe transaction marker")
    if not marker.exists():
        return False
    targets = (Path(active_movie), Path(active_episode))
    originals = (backup / "original_0.json", backup / "original_1.json")
    if any(p.is_symlink() or not p.is_file() for p in originals) or any(p.is_symlink() for p in targets):
        raise ValueError("unsafe recovery files")
    for original, target in zip(originals, targets):
        temp = target.with_name(target.name + ".trakt-recover-" + uuid.uuid4().hex)
        with original.open("rb") as src, temp.open("xb") as out:
            shutil.copyfileobj(src, out)
            out.flush(); os.fsync(out.fileno())
        os.replace(temp, target)
        _sync_directory(target.parent)
    marker.unlink()
    _sync_directory(backup)
    return True


def commit_staged_restore(*, staged_movie, staged_episode, active_movie, active_episode,
                          backup_directory, kodi_stopped):
    if kodi_stopped is not True:
        raise PermissionError('Kodi must be stopped before committing watched stores')
    sources = (Path(staged_movie), Path(staged_episode))
    targets = (Path(active_movie), Path(active_episode))
    backup = Path(backup_directory)
    if backup.exists() or backup.is_symlink():
        raise FileExistsError('backup directory must not exist')
    if targets[0].resolve() == targets[1].resolve() or sources[0].resolve() == sources[1].resolve():
        raise ValueError('distinct watched stores required')
    if any(p.is_symlink() or not p.is_file() for p in sources + targets):
        raise ValueError('watched stores must be regular files')
    if any(s.resolve() == t.resolve() for s in sources for t in targets):
        raise ValueError('staging cannot be active storage')
    for path in sources + targets:
        if not isinstance(json.loads(path.read_text('utf-8')), dict):
            raise ValueError('watched store must contain an object')
    if any(backup == p or backup in p.parents for p in sources + targets):
        raise ValueError("backup cannot contain watched stores")
    backup.mkdir(mode=0o700, parents=False)
    backups = [backup / ('original_%d.json' % i) for i in range(2)]
    try:
        for original, dest in zip(targets, backups):
            shutil.copy2(original, dest)
            with dest.open('rb') as f:
                os.fsync(f.fileno())
    except BaseException:
        shutil.rmtree(backup)
        raise
    _sync_directory(backup)
    marker = backup / "transaction.pending"
    marker.write_text("rollback-required", encoding="utf-8")
    with marker.open("rb") as f:
        os.fsync(f.fileno())
    _sync_directory(backup)
    pending = []
    replaced = []
    try:
        for source, target in zip(sources, targets):
            tmp = target.with_name(target.name + '.trakt-' + uuid.uuid4().hex + '.tmp')
            with source.open('rb') as inp, tmp.open('xb') as out:
                os.chmod(tmp, 0o600)
                shutil.copyfileobj(inp, out)
                out.flush()
                os.fsync(out.fileno())
            pending.append(tmp)
        for tmp, target in zip(pending, targets):
            os.replace(tmp, target)
            replaced.append(target)
            _sync_directory(target.parent)
    except BaseException:
        if replaced:
            recover_interrupted_restore(backup_directory=backup, active_movie=targets[0],
                                        active_episode=targets[1], kodi_stopped=True)
        raise
    else:
        marker.unlink()
        _sync_directory(backup)
    finally:
        for tmp in pending:
            if tmp.exists():
                tmp.unlink()
    return {'committed': True, 'backups': [str(p) for p in backups]}
