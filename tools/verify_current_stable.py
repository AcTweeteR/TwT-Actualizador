#!/usr/bin/env python3
"""Verify the immutable Stable feed against its current release manifest."""

import hashlib
import json
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifests/actweeter-stable-beta35-20261027.json"


def verify(root=ROOT, manifest_path=MANIFEST):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    index = (root / "repo/addons.xml").read_bytes()
    if hashlib.sha256(index).hexdigest() != manifest["index_sha256"]:
        raise ValueError("Stable index differs from release manifest")
    if ((root / "repo/addons.xml.md5").read_text().strip() != manifest["index_md5"]
            or hashlib.md5(index).hexdigest() != manifest["index_md5"]):
        raise ValueError("Stable index checksum differs")
    entries = manifest["addons"]
    expected = [(entry["id"], entry["version"]) for entry in entries]
    actual = [(addon.get("id"), addon.get("version")) for addon in ET.fromstring(index)]
    if actual != expected or len(set(actual)) != len(actual):
        raise ValueError("Stable index add-ons differ from release manifest")
    for entry in entries:
        addon_id, version = entry["id"], entry["version"]
        path = Path(entry["path"])
        if path != Path("repo") / addon_id / f"{addon_id}-{version}.zip":
            raise ValueError("unexpected Stable package path")
        package = root / path
        if hashlib.sha256(package.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"Stable package hash differs: {addon_id}")
        with zipfile.ZipFile(package) as archive:
            if archive.testzip() is not None:
                raise ValueError(f"Stable package CRC failed: {addon_id}")
            names = archive.namelist()
            if len(names) != len(set(names)) or any(
                    not name.startswith(addon_id + "/") or ".." in Path(name).parts
                    for name in names):
                raise ValueError(f"unsafe Stable package entries: {addon_id}")
            addon = ET.fromstring(archive.read(f"{addon_id}/addon.xml"))
            if (addon.get("id"), addon.get("version")) != (addon_id, version):
                raise ValueError(f"Stable package metadata differs: {addon_id}")
    for asset in manifest.get("assets", []):
        path = Path(asset["path"])
        if path.parts[:1] != ("repo",) or ".." in path.parts:
            raise ValueError("unsafe Stable metadata asset path")
        if hashlib.sha256((root / path).read_bytes()).hexdigest() != asset["sha256"]:
            raise ValueError("Stable metadata asset differs: " + str(path))
    return manifest["index_sha256"]


if __name__ == "__main__":
    try:
        print("Stable verified:", verify())
    except (OSError, KeyError, ValueError, ET.ParseError, zipfile.BadZipFile) as exc:
        print(f"Stable verification failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
