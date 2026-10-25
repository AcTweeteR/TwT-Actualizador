#!/usr/bin/env python3
"""Build a separate Kodi test channel under docs/testing; never touches stable."""
from __future__ import annotations

import argparse
import ctypes
import errno
import sys
import hashlib
import os
import tempfile
import shutil
import stat
import re
import zipfile
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
TEST_REPOSITORY_ID = "repository.actweeter.testing"
TEST_REPOSITORY_VERSION = "1.0.2"
SERVICE_ID = "service.actweeter"
SERVICE_VERSION = "0.4.94~beta3"
XSTREAM_ID = "plugin.video.xstream-pro"
RIVULET_REPOSITORY_ID = "repository.rivulet"
RIVULET_REPOSITORY_VERSION = "1.0.2"
RIVULET_REPOSITORY_SHA256 = "e4aabb495d6b49f39b8ec0c828ad9fa4562c387547739e0f38351ddabac9a815"
RIVULET_REQUIRED_FROM_SERVICE_VERSION = (0, 4, 82)
IAGL_REPOSITORY_ID = "repository.zachmorris"
IAGL_REPOSITORY_VERSION = "1.0.4"
IAGL_REPOSITORY_SHA256 = "3dde8f37dcd64f122cf1e897e139e5b8b7a3cd0ec15db6a1f5c7b59852cb661b"
IAGL_REQUIRED_FROM_SERVICE_VERSION = (0, 4, 84)
FIXED_TIME = (2026, 10, 3, 0, 0, 0)


def publish_directory_no_replace(stage: Path, output: Path) -> None:
    """Atomically publish a completed directory without replacing an existing path.

    Darwin renamex_np(RENAME_EXCL) is required for the macOS release builder.
    Other platforms fail closed until an equivalent primitive is implemented.
    """
    if sys.platform != "darwin":
        raise RuntimeError("atomic no-replace directory publication requires macOS")
    libc = ctypes.CDLL(None, use_errno=True)
    rename = libc.renamex_np
    rename.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint)
    rename.restype = ctypes.c_int
    # RENAME_EXCL = 0x00000004 on macOS (sys/stdio.h).
    if rename(os.fsencode(stage), os.fsencode(output), 0x00000004) != 0:
        code = ctypes.get_errno()
        if code in (errno.EEXIST, errno.ENOTEMPTY):
            raise ValueError("refusing to overwrite an existing test channel")
        raise OSError(code, os.strerror(code), str(output))


def zip_tree(source: Path, output: Path, root_name: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    for entry in source.rglob("*"):
        if entry.is_symlink():
            raise ValueError("test repository source contains a symlink")
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as archive:
        for path in sorted(p for p in source.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo((Path(root_name) / path.relative_to(source)).as_posix(), FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED,
                             compresslevel=9)


def addon_from_zip(path: Path, addon_id: str, version: str) -> ET.Element:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if (len(names) != len(set(names))
                or any(not name.startswith(addon_id + "/")
                       or ".." in Path(name).parts for name in names)
                or any((member.external_attr >> 16) & 0o170000
                       not in (0, stat.S_IFREG, stat.S_IFDIR)
                       for member in archive.infolist())):
            raise ValueError(f"unsafe ZIP paths: {path.name}")
        if archive.testzip() is not None:
            raise ValueError(f"bad ZIP CRC: {path.name}")
        expected = f"{addon_id}/addon.xml"
        if expected not in archive.namelist():
            raise ValueError(f"missing {expected}")
        addon = ET.fromstring(archive.read(expected))
    if addon.get("id") != addon_id or addon.get("version") != version:
        raise ValueError(f"unexpected package identity: {path.name}")
    return addon


def build(repository_source: Path, service_zip: Path, output: Path,
          skin_zip: Path | None = None,
          xstream_zip: Path | None = None,
          rivulet_repository_zip: Path | None = None,
          iagl_repository_zip: Path | None = None) -> tuple[Path, Path, Path]:
    # Never overwrite an existing feed or expose half-copied artifacts.
    if output.exists() or output.is_symlink():
        raise ValueError("refusing to overwrite an existing test channel")
    if not re.fullmatch(r"service\.actweeter-\d+\.\d+\.\d+(?:~beta\d+)?\.zip", service_zip.name):
        raise ValueError("candidate service ZIP filename does not match its Kodi identity/version")
    repo_addon = ET.parse(repository_source / "addon.xml").getroot()
    if repo_addon.get("id") != TEST_REPOSITORY_ID or repo_addon.get("version") != TEST_REPOSITORY_VERSION:
        raise ValueError("test repository identity/version mismatch")
    dirs = repo_addon.findall("./extension[@point='xbmc.addon.repository']/dir")
    if len(dirs) != 3:
        raise ValueError("test repository must expose only its Beta feed and external dependency feeds")
    info_urls = [node.findtext("info", "") for node in dirs]
    if info_urls != [
        "https://actweeter.github.io/TwT-Actualizador/testing/repo/addons.xml",
        "https://raw.githubusercontent.com/matke-84/repository.bingie/main/omega/addons.xml",
        "https://slyguy.uk/.repo/repository.slyguy/addons.xml",
    ]:
        raise ValueError("test repository feed endpoints are not isolated as expected")

    service = addon_from_zip(service_zip, SERVICE_ID, service_zip.name[len(SERVICE_ID) + 1:-4])
    service_version = tuple(int(part) for part in re.match(r"^(\d+)\.(\d+)\.(\d+)", service.get("version", "")).groups())
    if service_version >= RIVULET_REQUIRED_FROM_SERVICE_VERSION and rivulet_repository_zip is None:
        raise ValueError("service requires the pinned Rivulet repository bootstrap package")
    if service_version >= IAGL_REQUIRED_FROM_SERVICE_VERSION and iagl_repository_zip is None:
        raise ValueError("service requires the pinned IAGL repository bootstrap package")
    rivulet_repository = None
    if rivulet_repository_zip is not None:
        if hashlib.sha256(rivulet_repository_zip.read_bytes()).hexdigest() != RIVULET_REPOSITORY_SHA256:
            raise ValueError("Rivulet repository ZIP does not match the pinned upstream SHA-256")
        if rivulet_repository_zip.name != f"{RIVULET_REPOSITORY_ID}-{RIVULET_REPOSITORY_VERSION}.zip":
            raise ValueError("unexpected Rivulet repository ZIP filename")
        rivulet_repository = addon_from_zip(
            rivulet_repository_zip, RIVULET_REPOSITORY_ID, RIVULET_REPOSITORY_VERSION)
    iagl_repository = None
    if iagl_repository_zip is not None:
        if hashlib.sha256(iagl_repository_zip.read_bytes()).hexdigest() != IAGL_REPOSITORY_SHA256:
            raise ValueError("IAGL repository ZIP does not match the pinned upstream SHA-256")
        if iagl_repository_zip.name != f"{IAGL_REPOSITORY_ID}-{IAGL_REPOSITORY_VERSION}.zip":
            raise ValueError("unexpected IAGL repository ZIP filename")
        iagl_repository = addon_from_zip(
            iagl_repository_zip, IAGL_REPOSITORY_ID, IAGL_REPOSITORY_VERSION)
    skin = None
    if skin_zip is not None:
        with zipfile.ZipFile(skin_zip) as archive:
            skin = ET.fromstring(archive.read("skin.actweeter/addon.xml"))
        skin_version = skin.get("version", "")
        if "~beta" not in skin_version or skin_zip.name != f"skin.actweeter-{skin_version}.zip":
            raise ValueError("test skin must have a versioned Beta filename")
        skin = addon_from_zip(skin_zip, "skin.actweeter", skin_version)
    xstream = None
    if xstream_zip is not None:
        with zipfile.ZipFile(xstream_zip) as archive:
            xstream_xml = ET.fromstring(archive.read(f"{XSTREAM_ID}/addon.xml"))
        xstream_version = xstream_xml.get("version", "")
        if xstream_zip.name != f"{XSTREAM_ID}-{xstream_version}.zip":
            raise ValueError("XStream ZIP filename does not match its Kodi identity/version")
        xstream = addon_from_zip(xstream_zip, XSTREAM_ID, xstream_version)
    metadata = repo_addon.find("./extension[@point='xbmc.addon.metadata']")
    if metadata is None:
        raise ValueError("test repository metadata extension missing")
    repo_news = metadata.find("news")
    if repo_news is None:
        raise ValueError("test repository changelog declaration missing")
    repo_news_name = repo_news.text or ""
    if not (repository_source / repo_news_name).is_file():
        raise ValueError("test repository changelog missing")

    # All input validation has completed. Build into a private sibling tree.
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".actweeter-test-feed-", dir=output.parent) as temporary:
        stage = Path(temporary) / "feed"
        stage.mkdir()
        result = _write_test_channel(stage, repository_source, repo_addon,
                                     service_zip, service, skin_zip, skin,
                                     xstream_zip, xstream, rivulet_repository_zip,
                                     rivulet_repository, iagl_repository_zip,
                                     iagl_repository, repo_news_name)
        publish_directory_no_replace(stage, output)
    return tuple(output / path.relative_to(stage) for path in result)



def _copy_changelog(package: Path, addon: ET.Element, addon_id: str,
                    output: Path) -> None:
    news = addon.find("./extension[@point='xbmc.addon.metadata']/news")
    filename = (news.text or "").strip() if news is not None else ""
    if not filename:
        return
    if Path(filename).name != filename:
        raise ValueError("unsafe add-on changelog path")
    member = f"{addon_id}/{filename}"
    with zipfile.ZipFile(package) as archive:
        if member not in archive.namelist():
            raise ValueError(f"missing packaged changelog: {member}")
        content = archive.read(member)
    target = output / "repo" / addon_id / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)


def _copy_metadata_assets(package: Path, addon: ET.Element, addon_id: str,
                          output: Path) -> None:
    metadata = addon.find("./extension[@point='xbmc.addon.metadata']")
    assets = metadata.find("assets") if metadata is not None else None
    if assets is None:
        return
    with zipfile.ZipFile(package) as archive:
        for asset in assets:
            reference = (asset.text or "").strip()
            if not reference or urlsplit(reference).scheme or reference.startswith("//"):
                continue
            if "\\" in reference:
                raise ValueError("unsafe add-on metadata asset path")
            relative = Path(reference)
            if (relative.is_absolute() or not relative.parts
                    or any(part in ("", ".", "..") for part in relative.parts)):
                raise ValueError("unsafe add-on metadata asset path")
            member = f"{addon_id}/{relative.as_posix()}"
            try:
                content = archive.read(member)
            except KeyError as error:
                raise ValueError(f"missing packaged metadata asset: {member}") from error
            target = output / "repo" / addon_id / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)


def bootstrap_index_html(current_zip_name: str) -> str:
    """Kodi-compatible browse page: current installer and archived versions only."""
    if not re.fullmatch(r"repository[.]actweeter[.]testing-[0-9]+[.][0-9]+[.][0-9]+[.]zip",
                        current_zip_name):
        raise ValueError("invalid testing bootstrap ZIP name")
    return chr(10).join([
        '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">',
        '<html><head><title>Index of /TwT-Actualizador/testing/bootstrap/</title></head>',
        '<body><h1>Index of /TwT-Actualizador/testing/bootstrap/</h1><hr><pre>',
        f'<a href="{current_zip_name}">{current_zip_name}</a>',
        '<a href="archive/">archive/</a>',
        '</pre><hr></body></html>'
    ]) + chr(10)


def _write_test_channel(output: Path, repository_source: Path, repo_addon: ET.Element,
                        service_zip: Path, service: ET.Element, skin_zip: Path | None,
                        skin: ET.Element | None, xstream_zip: Path | None,
                        xstream: ET.Element | None, rivulet_repository_zip: Path | None,
                        rivulet_repository: ET.Element | None,
                        iagl_repository_zip: Path | None,
                        iagl_repository: ET.Element | None,
                        repo_news_name: str) -> tuple[Path, Path, Path]:
    repo_zip = output / "bootstrap" / f"{TEST_REPOSITORY_ID}-{TEST_REPOSITORY_VERSION}.zip"
    zip_tree(repository_source, repo_zip, TEST_REPOSITORY_ID)
    with zipfile.ZipFile(repo_zip) as archive:
        if archive.testzip() is not None:
            raise ValueError("test repository bootstrap ZIP CRC failed")

    repo_package = output / "repo" / TEST_REPOSITORY_ID / repo_zip.name
    repo_package.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(repo_zip, repo_package)
    _copy_metadata_assets(repo_zip, repo_addon, TEST_REPOSITORY_ID, output)
    service_package = output / "repo" / SERVICE_ID / service_zip.name
    service_package.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(service_zip, service_package)
    _copy_changelog(service_zip, service, SERVICE_ID, output)
    _copy_metadata_assets(service_zip, service, SERVICE_ID, output)
    if skin is not None:
        skin_package = output / "repo" / "skin.actweeter" / skin_zip.name
        skin_package.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(skin_zip, skin_package)
        _copy_changelog(skin_zip, skin, "skin.actweeter", output)
        _copy_metadata_assets(skin_zip, skin, "skin.actweeter", output)
    if xstream is not None:
        xstream_package = output / "repo" / XSTREAM_ID / xstream_zip.name
        xstream_package.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(xstream_zip, xstream_package)
        _copy_metadata_assets(xstream_zip, xstream, XSTREAM_ID, output)
    if rivulet_repository is not None:
        rivulet_package = (output / "repo" / RIVULET_REPOSITORY_ID /
                           rivulet_repository_zip.name)
        rivulet_package.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(rivulet_repository_zip, rivulet_package)
        _copy_metadata_assets(rivulet_repository_zip, rivulet_repository,
                              RIVULET_REPOSITORY_ID, output)
    if iagl_repository is not None:
        package = output / "repo" / IAGL_REPOSITORY_ID / iagl_repository_zip.name
        package.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(iagl_repository_zip, package)
        _copy_metadata_assets(iagl_repository_zip, iagl_repository,
                              IAGL_REPOSITORY_ID, output)

    index_root = ET.Element("addons")
    index_root.append(repo_addon)
    if skin is not None:
        index_root.append(skin)
    index_root.append(service)
    if xstream is not None:
        index_root.append(xstream)
    if rivulet_repository is not None:
        index_root.append(rivulet_repository)
    if iagl_repository is not None:
        index_root.append(iagl_repository)
    payload = ET.tostring(index_root, encoding="utf-8", xml_declaration=True) + b"\n"
    index = output / "repo" / "addons.xml"
    checksum = output / "repo" / "addons.xml.md5"
    index.write_bytes(payload)
    checksum.write_text(hashlib.md5(payload).hexdigest() + "\n", encoding="ascii")

    (output / "bootstrap" / "index.html").write_text(
        bootstrap_index_html(repo_zip.name), encoding="utf-8")
    (output / "README.md").write_text(
        "# AcTweeteR Kodi test channel\n\n"
        "Explicit prerelease channel. AcTweeteR add-ons are read only from the Testing feed. "
        "BINGIE and SlyGuy feeds remain available for external dependencies; the Stable feed is not aggregated.\n",
        encoding="utf-8")
    return repo_zip, index, checksum


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-source", type=Path,
                        default=ROOT / "testing" / TEST_REPOSITORY_ID)
    parser.add_argument("--service-zip", required=True, type=Path)
    parser.add_argument("--skin-zip", type=Path)
    parser.add_argument("--xstream-zip", type=Path)
    parser.add_argument("--rivulet-repository-zip", type=Path)
    parser.set_defaults(rivulet_repository_zip=(
        ROOT / "source/0.4.32/third_party/rivulet/repository.rivulet-1.0.2.zip"))
    parser.add_argument("--iagl-repository-zip", type=Path)
    parser.set_defaults(iagl_repository_zip=(
        ROOT / "source/0.4.32/third_party/iagl/repository.zachmorris-1.0.4.zip"))
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "testing")
    args = parser.parse_args()
    repo_zip, index, checksum = build(args.repository_source, args.service_zip, args.output,
                                     args.skin_zip, args.xstream_zip,
                                     args.rivulet_repository_zip,
                                     args.iagl_repository_zip)
    print(f"test repository bootstrap: {repo_zip}")
    print(f"test feed: {index}")
    print(f"test feed md5: {checksum}")
    packages = [repo_zip, index, checksum,
                args.output / "repo" / SERVICE_ID / args.service_zip.name]
    if args.skin_zip is not None:
        packages.append(args.output / "repo" / "skin.actweeter" / args.skin_zip.name)
    if args.xstream_zip is not None:
        packages.append(args.output / "repo" / XSTREAM_ID / args.xstream_zip.name)
    if args.rivulet_repository_zip is not None:
        packages.append(args.output / "repo" / RIVULET_REPOSITORY_ID /
                        args.rivulet_repository_zip.name)
    if args.iagl_repository_zip is not None:
        packages.append(args.output / "repo" / IAGL_REPOSITORY_ID /
                        args.iagl_repository_zip.name)
    for path in packages:
        print(f"SHA-256 {hashlib.sha256(path.read_bytes()).hexdigest()}  {path}")


if __name__ == "__main__":
    main()
