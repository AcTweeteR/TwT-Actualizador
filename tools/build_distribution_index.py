#!/usr/bin/env python3
"""Build the Kodi add-on index for a manual AcTweeteR distribution release.

Add-on ZIPs are built from this private repository. The unchanged repository
add-on ZIP is supplied from the current public distribution checkout.
"""
from __future__ import annotations

import argparse
import hashlib
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


EXPECTED = {
    "repository": ("repository.actweeter", "1.0.1"),
    "skin": ("skin.actweeter", "1.1.3"),
    "service": ("service.actweeter", "0.1.0"),
}


def addon_from_zip(path: Path, expected_id: str, expected_version: str) -> ET.Element:
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("invalid ZIP CRC")
        matches = [name for name in archive.namelist()
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


def build(repository_zip: Path, skin_zip: Path, service_zip: Path,
          output_dir: Path) -> tuple[Path, Path]:
    repository = addon_from_zip(repository_zip, *EXPECTED["repository"])
    skin = addon_from_zip(skin_zip, *EXPECTED["skin"])
    service = addon_from_zip(service_zip, *EXPECTED["service"])
    set_news(skin, "changelog-1.1.3.txt")
    set_news(service, "changelog-0.1.0.txt")
    root = ET.Element("addons")
    for addon in (repository, skin, service):
        root.append(addon)
    payload = ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"
    output_dir.mkdir(parents=True, exist_ok=True)
    index = output_dir / "addons.xml"
    checksum = output_dir / "addons.xml.md5"
    index.write_bytes(payload)
    checksum.write_text(hashlib.md5(payload).hexdigest() + "\n", encoding="ascii")
    return index, checksum


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-zip", required=True, type=Path)
    parser.add_argument("--skin-zip", required=True, type=Path)
    parser.add_argument("--service-zip", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    index, checksum = build(args.repository_zip, args.skin_zip, args.service_zip,
                            args.output_dir)
    print(f"Kodi repository index: {index}")
    print(f"Kodi repository index checksum: {checksum}")


if __name__ == "__main__":
    main()
