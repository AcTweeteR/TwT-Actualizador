"""Atomic, create-only ZIP publication shared by Kodi addon builders."""
from __future__ import annotations

import hashlib
import os
import stat
import tempfile
import zipfile
from pathlib import Path
from typing import Callable


def publish_zip(source: Path, output: Path, addon_id: str, version: str,
                fixed_time: tuple[int, ...], payload_for: Callable[[Path], bytes],
                excluded: Callable[[Path], bool] | None = None) -> str:
    if output.exists() or output.is_symlink():
        raise ValueError("refusing to overwrite existing addon package")
    if source.is_symlink() or not source.is_dir():
        raise ValueError("addon source must be a real directory")
    files = []
    for path in source.rglob('*'):
        if path.is_symlink():
            raise ValueError("addon source contains a symlink")
        if not path.is_file() and not path.is_dir():
            raise ValueError("addon source contains a non-regular entry")
        if path.is_file() and not (excluded and excluded(path)):
            files.append(path)
    if not (source / 'addon.xml').is_file():
        raise ValueError("addon.xml missing from source")
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.actweeter-package-', suffix='.zip', dir=output.parent)
    os.close(fd)
    candidate = Path(tmp)
    try:
        with zipfile.ZipFile(candidate, 'w', compression=zipfile.ZIP_DEFLATED,
                             compresslevel=9) as archive:
            for path in sorted(files):
                if path.is_symlink() or not path.is_file():
                    raise ValueError("addon source changed during packaging")
                name = (Path(addon_id) / path.relative_to(source)).as_posix()
                info = zipfile.ZipInfo(name, fixed_time)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                archive.writestr(info, payload_for(path),
                                 compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        from xml.etree import ElementTree as ET
        with zipfile.ZipFile(candidate) as archive:
            if archive.testzip() is not None:
                raise ValueError('invalid package CRC')
            addon = ET.fromstring(archive.read(f'{addon_id}/addon.xml'))
            if (addon.get('id'), addon.get('version')) != (addon_id, version):
                raise ValueError('package identity mismatch')
        digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
        try:
            os.link(candidate, output, follow_symlinks=False)
        except FileExistsError as exc:
            raise ValueError('refusing to overwrite existing addon package') from exc
        return digest
    finally:
        candidate.unlink(missing_ok=True)
