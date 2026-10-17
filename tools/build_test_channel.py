#!/usr/bin/env python3
"""Build a separate Kodi test channel under docs/testing; never touches stable."""
from __future__ import annotations

import argparse
import hashlib
import shutil
import stat
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
TEST_REPOSITORY_ID = "repository.actweeter.testing"
TEST_REPOSITORY_VERSION = "1.0.0"
SERVICE_ID = "service.actweeter"
SERVICE_VERSION = "0.4.33"
FIXED_TIME = (2026, 10, 3, 0, 0, 0)


def zip_tree(source: Path, output: Path, root_name: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
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
        if archive.testzip() is not None:
            raise ValueError(f"bad ZIP CRC: {path.name}")
        expected = f"{addon_id}/addon.xml"
        if expected not in archive.namelist():
            raise ValueError(f"missing {expected}")
        addon = ET.fromstring(archive.read(expected))
    if addon.get("id") != addon_id or addon.get("version") != version:
        raise ValueError(f"unexpected package identity: {path.name}")
    return addon


def build(repository_source: Path, service_zip: Path, output: Path) -> tuple[Path, Path, Path]:
    if service_zip.name != f"{SERVICE_ID}-{SERVICE_VERSION}.zip":
        raise ValueError("candidate service ZIP filename does not match its Kodi identity/version")
    repo_addon = ET.parse(repository_source / "addon.xml").getroot()
    if repo_addon.get("id") != TEST_REPOSITORY_ID or repo_addon.get("version") != TEST_REPOSITORY_VERSION:
        raise ValueError("test repository identity/version mismatch")
    dirs = repo_addon.findall("./extension[@point='xbmc.addon.repository']/dir")
    if len(dirs) != 2:
        raise ValueError("test repository must expose only its candidate and the official stable feed")
    info_urls = [node.findtext("info", "") for node in dirs]
    if info_urls != [
        "https://actweeter.github.io/TwT-Actualizador/testing/repo/addons.xml",
        "https://raw.githubusercontent.com/AcTweeteR/TwT-Actualizador/main/repo/addons.xml",
    ]:
        raise ValueError("test repository feed endpoints are not isolated as expected")

    service = addon_from_zip(service_zip, SERVICE_ID, SERVICE_VERSION)
    metadata = repo_addon.find("./extension[@point='xbmc.addon.metadata']")
    if metadata is None:
        raise ValueError("test repository metadata extension missing")
    repo_news = metadata.find("news")
    if repo_news is None:
        raise ValueError("test repository changelog declaration missing")
    repo_news_name = repo_news.text or ""
    if not (repository_source / repo_news_name).is_file():
        raise ValueError("test repository changelog missing")

    repo_zip = output / "bootstrap" / f"{TEST_REPOSITORY_ID}-{TEST_REPOSITORY_VERSION}.zip"
    zip_tree(repository_source, repo_zip, TEST_REPOSITORY_ID)
    with zipfile.ZipFile(repo_zip) as archive:
        if archive.testzip() is not None:
            raise ValueError("test repository bootstrap ZIP CRC failed")

    repo_package = output / "repo" / TEST_REPOSITORY_ID / repo_zip.name
    repo_package.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(repo_zip, repo_package)
    service_package = output / "repo" / SERVICE_ID / service_zip.name
    service_package.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(service_zip, service_package)

    index_root = ET.Element("addons")
    index_root.extend((repo_addon, service))
    payload = ET.tostring(index_root, encoding="utf-8", xml_declaration=True) + b"\n"
    index = output / "repo" / "addons.xml"
    checksum = output / "repo" / "addons.xml.md5"
    index.write_bytes(payload)
    checksum.write_text(hashlib.md5(payload).hexdigest() + "\n", encoding="ascii")

    (output / "bootstrap" / "index.html").write_text(
        "<!doctype html><html lang=\"en\"><meta charset=\"utf-8\"><title>AcTweeteR test bootstrap</title>"
        f"<p>Install this test-only Kodi repository: <a href=\"{repo_zip.name}\">{repo_zip.name}</a></p>"
        "</html>\n", encoding="utf-8")
    (output / "README.md").write_text(
        "# AcTweeteR Kodi test channel\n\n"
        "Explicit prerelease channel. The stable index at `/repo/` is not modified. "
        "The test repository also aggregates the official stable feed for dependencies and rollback.\n",
        encoding="utf-8")
    return repo_zip, index, checksum


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-source", type=Path,
                        default=ROOT / "testing" / TEST_REPOSITORY_ID)
    parser.add_argument("--service-zip", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "testing")
    args = parser.parse_args()
    repo_zip, index, checksum = build(args.repository_source, args.service_zip, args.output)
    print(f"test repository bootstrap: {repo_zip}")
    print(f"test feed: {index}")
    print(f"test feed md5: {checksum}")
    for path in (repo_zip, index, checksum, args.output / "repo" / SERVICE_ID / args.service_zip.name):
        print(f"SHA-256 {hashlib.sha256(path.read_bytes()).hexdigest()}  {path}")


if __name__ == "__main__":
    main()
