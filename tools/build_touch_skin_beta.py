#!/usr/bin/env python3
"""Build an isolated, reproducible AcTweeteR touch skin Beta from public Stable.

The packaging scope is exactly skin.actweeter. No service or XStream build is
performed and no profiles, provider data or public Stable indexes are written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import stat
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source/0.4.32/addons/skin.actweeter"
# Previous Beta1 is immutable. Newly edited skin sources are for Beta2.
SOURCE_COMMIT = "9e79068"
ADDON = "skin.actweeter"
BASE = "1.2.40"
BETA = "1.2.41~beta1"
BASE_DIGEST = "3edfdacd277d0cc2ab4045c1f1acc3285bb677444e24312a5767b8cbceb09a67"
TIME = (2026, 11, 4, 0, 0, 0)
OVERLAY = (
    "1080i/IncludesTouchMode.xml",
    "1080i/Includes.xml",
    "1080i/IncludesSkinSettings.xml",
    "1080i/IncludesBingie.xml",
    "1080i/IncludesHomeBingie.xml",
    "1080i/IncludesHomeWidgets.xml",
    "1080i/IncludesBingieSearch.xml",
    "1080i/DialogVideoInfo.xml",
    "language/resource.language.es_es/strings.po",
    "language/resource.language.en_gb/strings.po",
)
NOTE = ("AcTweeteR 1.2.41~beta1 - touch interface only.\n"
        "Selector in sidebar and skin settings; large Menu, Search, Home, "
        "up/down, Spotlight arrow and Info Close touch targets. "
        "Remote mode remains the default. No add-on integrations changed.\n")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build(path: Path) -> dict:
    path = Path(path)
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to overwrite {path}")
    base_path = ROOT / "repo" / ADDON / f"{ADDON}-{BASE}.zip"
    if sha(base_path.read_bytes()) != BASE_DIGEST:
        raise ValueError("unexpected Stable skin baseline")
    with zipfile.ZipFile(base_path) as archive:
        if archive.testzip():
            raise ValueError("Stable skin archive CRC failed")
        content = {name: archive.read(name) for name in archive.namelist()
                   if name and not name.endswith("/")}
    before = dict(content)
    for relative in OVERLAY:
        # Reconstruct the original published overlay, not mutable HEAD.
        data = subprocess.check_output(
            ["git", "show", SOURCE_COMMIT + ":source/0.4.32/addons/skin.actweeter/" + relative],
            cwd=ROOT)
        content[f"{ADDON}/{relative}"] = data
    manifest_name = f"{ADDON}/addon.xml"
    addon = ET.fromstring(content[manifest_name])
    if addon.get("id") != ADDON or addon.get("version") != BASE:
        raise ValueError("invalid input skin version")
    addon.set("version", BETA)
    news = addon.find("./extension[@point='xbmc.addon.metadata']/news")
    if news is None or news.text != f"changelog-{BASE}.txt":
        raise ValueError("unexpected stable release note")
    note_name = f"changelog-{BETA}.txt"
    news.text = note_name
    content[manifest_name] = ET.tostring(addon, encoding="utf-8",
                                         xml_declaration=True) + b"\n"
    content[f"{ADDON}/{note_name}"] = NOTE.encode()
    expected = {f"{ADDON}/{i}" for i in OVERLAY} | {manifest_name, f"{ADDON}/{note_name}"}
    changed = {name for name in content if content[name] != before.get(name)}
    if changed != expected:
        raise ValueError("unexpected payload modifications: " + str(changed ^ expected))
    # Kodi XML and translation files must parse without altering unrelated UI.
    for relative in OVERLAY:
        if relative.endswith(".xml"):
            ET.fromstring(content[f"{ADDON}/{relative}"])
    for language in ("es_es", "en_gb"):
        text = content[f"{ADDON}/language/resource.language.{language}/strings.po"].decode()
        for key in range(32019, 32026):
            if text.count(f'msgctxt "#{key}"') != 1:
                raise ValueError(f"duplicate or missing localization {language}:{key}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as archive:
        for name, payload in sorted(content.items()):
            if not name.startswith(ADDON + "/") or ".." in Path(name).parts:
                raise ValueError("unsafe skin ZIP member")
            info = zipfile.ZipInfo(name, TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, payload, compress_type=zipfile.ZIP_DEFLATED,
                             compresslevel=9)
    with zipfile.ZipFile(path) as archive:
        if archive.testzip():
            raise ValueError("candidate ZIP failed CRC")
        final = ET.fromstring(archive.read(manifest_name))
        if final.get("version") != BETA:
            raise ValueError("final Beta version mismatch")
    return {"version": BETA, "sha256": sha(path.read_bytes()),
            "bytes": path.stat().st_size,
            "changed_paths": sorted(changed), "member_count": len(content)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path,
                        default=ROOT / "build/touch-skin-beta/skin.actweeter-1.2.41~beta1.zip")
    args = parser.parse_args()
    print(json.dumps(build(args.output), indent=2))
