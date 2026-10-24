"""Fail-closed gate for interrupted watched-store transactions."""
from pathlib import Path


def pending_restores(profile_directory):
    root = Path(profile_directory)
    backup_root = root / 'trakt_restore_backups'
    if root.is_symlink() or backup_root.is_symlink():
        raise ValueError('unsafe restore directory')
    if not backup_root.exists():
        return []
    if not backup_root.is_dir():
        raise ValueError('invalid restore directory')
    result = []
    for folder in backup_root.iterdir():
        if folder.is_symlink():
            raise ValueError('unsafe transaction directory')
        if folder.is_dir():
            marker = folder / 'transaction.pending'
            if marker.is_symlink():
                raise ValueError('unsafe transaction marker')
            if marker.is_file():
                result.append(folder)
    return sorted(result)


def assert_restore_ready(profile_directory):
    pending = pending_restores(profile_directory)
    if pending:
        raise RuntimeError('interrupted restore must be recovered with Kodi stopped')
    return True
