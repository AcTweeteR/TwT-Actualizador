"""Reversible, stopped-Kodi watched-store commit with rollback on failure.

The caller must stop Kodi before invoking this function. No network activity.
"""
import json
import os
from pathlib import Path
import shutil
import uuid


def commit_staged_restore(*, staged_movie, staged_episode, active_movie, active_episode,
                          backup_directory, kodi_stopped):
    if kodi_stopped is not True:
        raise PermissionError('Kodi must be stopped before committing watched stores')
    sources = (Path(staged_movie), Path(staged_episode))
    targets = (Path(active_movie), Path(active_episode))
    backup = Path(backup_directory)
    if backup.exists() or backup.is_symlink():
        raise FileExistsError('backup directory must not exist')
    if targets[0] == targets[1] or sources[0] == sources[1]:
        raise ValueError('distinct watched stores required')
    if any(p.is_symlink() or not p.is_file() for p in sources + targets):
        raise ValueError('watched stores must be regular files')
    if any(s.resolve() == t.resolve() for s in sources for t in targets):
        raise ValueError('staging cannot be active storage')
    for path in sources + targets:
        if not isinstance(json.loads(path.read_text('utf-8')), dict):
            raise ValueError('watched store must contain an object')
    backup.mkdir(mode=0o700, parents=False)
    backups = [backup / ('original_%d.json' % i) for i in range(2)]
    for original, dest in zip(targets, backups):
        shutil.copy2(original, dest)
        with dest.open('rb') as f:
            os.fsync(f.fileno())
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
    except BaseException:
        for target, original in zip(targets, backups):
            if target in replaced:
                shutil.copy2(original, target)
        raise
    finally:
        for tmp in pending:
            if tmp.exists():
                tmp.unlink()
    return {'committed': True, 'backups': [str(p) for p in backups]}
