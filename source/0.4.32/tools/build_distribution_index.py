#!/usr/bin/env python3
"""Build the Kodi add-on index for a private AcTweeteR beta candidate.

All three add-on ZIPs are built from this private repository. This tool only
creates local artifacts; it never uploads or publishes them.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import stat
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


EXPECTED = {
    "repository": ("repository.actweeter.testing", "1.0.2"),
    "skin": ("skin.actweeter", "1.2.32~beta9"),
    "service": ("service.actweeter", "0.4.85"),
    "xstream": ("plugin.video.xstream-pro", "1.1.2.28~beta20"),
    "rivulet_repository": ("repository.rivulet", "1.0.2"),
    "iagl_repository": ("repository.zachmorris", "1.0.4"),
}
RIVULET_REPOSITORY_SHA256 = "e4aabb495d6b49f39b8ec0c828ad9fa4562c387547739e0f38351ddabac9a815"
IAGL_REPOSITORY_SHA256 = "3dde8f37dcd64f122cf1e897e139e5b8b7a3cd0ec15db6a1f5c7b59852cb661b"


def addon_from_zip(path: Path, expected_id: str, expected_version: str) -> ET.Element:
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("invalid ZIP CRC")
        names = archive.namelist()
        if (len(names) != len(set(names))
                or any(not name.startswith(expected_id + "/")
                       or "\\" in name or any(part in ("", ".", "..")
                           for part in name.rstrip("/").split("/"))
                       for name in names)
                or any(((entry.external_attr >> 16) & 0o170000)
                       not in (0, stat.S_IFREG, stat.S_IFDIR)
                       for entry in archive.infolist())
                or any(entry.file_size > 128 * 1024 * 1024
                       for entry in archive.infolist())):
            raise ValueError("unsafe add-on ZIP entries")
        matches = [name for name in names
                   if name.count("/") == 1 and name.endswith("/addon.xml")]
        if len(matches) != 1 or matches[0] != f"{expected_id}/addon.xml":
            raise ValueError("unexpected add-on ZIP root")
        addon = ET.fromstring(archive.read(matches[0]))
    if addon.get("id") != expected_id or addon.get("version") != expected_version:
        raise ValueError("add-on ID/version mismatch")
    return addon


def set_news(addon: ET.Element, filename: str) -> None:
    metadata = addon.find("extension[@point='xbmc.addon.metadata']")
    if metadata is None:
        raise ValueError("add-on metadata extension missing")
    news = metadata.find("news")
    if news is None:
        news = ET.SubElement(metadata, "news")
    news.text = filename


def validate_service_xstream_pair(service: ET.Element, xstream: ET.Element) -> None:
    dependency = service.find("requires/import[@addon='plugin.video.xstream-pro']")
    expected = EXPECTED["xstream"][1]
    if (dependency is None or dependency.get("version") != expected
            or xstream.get("version") != expected):
        raise ValueError("Service/XStream Trakt sync protocol generation mismatch")


def build(repository_zip: Path, skin_zip: Path, service_zip: Path,
          xstream_zip: Path, output_dir: Path,
          rivulet_repository_zip: Path | None = None,
          iagl_repository_zip: Path | None = None) -> tuple[Path, Path]:
    repository = addon_from_zip(repository_zip, *EXPECTED["repository"])
    skin = addon_from_zip(skin_zip, *EXPECTED["skin"])
    service = addon_from_zip(service_zip, *EXPECTED["service"])
    xstream = addon_from_zip(xstream_zip, *EXPECTED["xstream"])
    validate_service_xstream_pair(service, xstream)
    if rivulet_repository_zip is None:
        raise ValueError("Rivulet repository seed ZIP is required for this candidate")
    if hashlib.sha256(rivulet_repository_zip.read_bytes()).hexdigest() != RIVULET_REPOSITORY_SHA256:
        raise ValueError("Rivulet repository ZIP does not match the pinned upstream SHA-256")
    rivulet = addon_from_zip(rivulet_repository_zip, *EXPECTED["rivulet_repository"])
    if iagl_repository_zip is None:
        raise ValueError("IAGL repository seed ZIP is required for this candidate")
    if hashlib.sha256(iagl_repository_zip.read_bytes()).hexdigest() != IAGL_REPOSITORY_SHA256:
        raise ValueError("IAGL repository ZIP does not match the pinned upstream SHA-256")
    iagl = addon_from_zip(iagl_repository_zip, *EXPECTED["iagl_repository"])
    set_news(skin, "changelog-1.2.32~beta9.txt")
    set_news(service, "changelog-0.4.85.txt")
    root = ET.Element("addons")
    for addon in (repository, skin, service, xstream, rivulet, iagl):
        root.append(addon)
    payload = ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"
    # This builder is intentionally create-only: never replace a live index,
    # and never leave only one of the two repository metadata files.
    if output_dir.exists() or output_dir.is_symlink():
        raise ValueError("refusing to overwrite an existing distribution index")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".actweeter-index-", dir=output_dir.parent) as tmp:
        staged = Path(tmp) / "index"
        staged.mkdir()
        (staged / "addons.xml").write_bytes(payload)
        (staged / "addons.xml.md5").write_text(
            hashlib.md5(payload).hexdigest() + "\n", encoding="ascii")
        # Darwin RENAME_EXCL: atomic no-replace directory publication.
        import ctypes
        import errno
        import sys
        if sys.platform != "darwin":
            raise RuntimeError("atomic distribution index publication requires macOS")
        libc = ctypes.CDLL(None, use_errno=True)
        rename = libc.renamex_np
        rename.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint)
        rename.restype = ctypes.c_int
        if rename(os.fsencode(staged), os.fsencode(output_dir), 0x00000004):
            code = ctypes.get_errno()
            if code in (errno.EEXIST, errno.ENOTEMPTY):
                raise ValueError("refusing to overwrite an existing distribution index")
            raise OSError(code, os.strerror(code), str(output_dir))
    return output_dir / "addons.xml", output_dir / "addons.xml.md5"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-zip", required=True, type=Path)
    parser.add_argument("--skin-zip", required=True, type=Path)
    parser.add_argument("--service-zip", required=True, type=Path)
    parser.add_argument("--xstream-zip", required=True, type=Path)
    parser.add_argument("--rivulet-repository-zip", required=True, type=Path)
    parser.add_argument("--iagl-repository-zip", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    index, checksum = build(args.repository_zip, args.skin_zip, args.service_zip,
                            args.xstream_zip, args.output_dir,
                            args.rivulet_repository_zip,
                            args.iagl_repository_zip)
    print(f"Kodi repository index: {index}")
    print(f"Kodi repository index checksum: {checksum}")


if __name__ == "__main__":
    main()
