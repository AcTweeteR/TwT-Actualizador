#!/usr/bin/env python3
"""Reproducible skin-only touch navigation refinement, Beta2 from signed Beta1."""
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
SRC = ROOT / "source/0.4.32/addons/skin.actweeter"
# Keep already-published Beta2 reproducible as the source skin changes.
SOURCE_COMMIT = "c7eaed3"
ADDON = "skin.actweeter"
PARENT = "1.2.41~beta1"
VERSION = "1.2.41~beta2"
EXPECTED_PARENT_SHA = "19bde76b808942b1b287ca032219d0ee494afdfe2a58ba054f6ddebf5ec5c516"
TIME = (2026, 11, 5, 0, 0, 0)
OVERLAY = (
    "1080i/IncludesTouchInfoActions.xml",
    "1080i/IncludesTouchVideoNavigation.xml",
    "1080i/Includes.xml",
    "1080i/DialogVideoInfo.xml",
    "1080i/DialogTextViewer.xml",
    "1080i/MyVideoNav.xml",
    "1080i/IncludesTouchMode.xml",
    "language/resource.language.es_es/strings.po",
    "language/resource.language.en_gb/strings.po",
)
NOTES = (
    "AcTweeteR 1.2.41~beta2: correct touch access to movie and series actions.\n"
    "Large primary-action strip; native-action drawer forwards click by control ID,\n"
    "touch-native scroll on Info / native video views / synopsis.\n"
    "Remote mode untouched. Service, XStream, providers, Trakt and PVR unchanged.\n"
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build(output: Path) -> dict:
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"refusing to replace existing Beta: {output}")
    base = ROOT / "docs/testing/repo/skin.actweeter" / f"{ADDON}-{PARENT}.zip"
    if sha(base.read_bytes()) != EXPECTED_PARENT_SHA:
        raise ValueError("immutable Beta1 skin archive changed")
    with zipfile.ZipFile(base) as z:
        if z.testzip() is not None:
            raise ValueError("Beta1 CRC failed")
        content = {name: z.read(name) for name in z.namelist() if name and not name.endswith("/")}
    original = dict(content)
    for rel in OVERLAY:
        content[f"{ADDON}/{rel}"] = subprocess.check_output(
            ["git", "show", SOURCE_COMMIT + ":source/0.4.32/addons/skin.actweeter/" + rel],
            cwd=ROOT)
        if rel.endswith(".xml"):
            ET.fromstring(content[f"{ADDON}/{rel}"])
    for locale in ("es_es", "en_gb"):
        text = content[f"{ADDON}/language/resource.language.{locale}/strings.po"].decode()
        for ident in list(range(32019,32037)) + list(range(32100,32132)):
            if text.count(f'msgctxt "#{ident}"') != 1:
                raise ValueError(f"invalid {locale} translation {ident}")
    manifest = ADDON + "/addon.xml"
    element = ET.fromstring(content[manifest])
    if element.get("id") != ADDON or element.get("version") != PARENT:
        raise ValueError("unexpected original Beta1 skin")
    news = element.find("./extension[@point='xbmc.addon.metadata']/news")
    if news is None or news.text != f"changelog-{PARENT}.txt":
        raise ValueError("unexpected original Beta1 changelog reference")
    news.text = f"changelog-{VERSION}.txt"
    element.set("version", VERSION)
    content[manifest] = ET.tostring(element, encoding="utf-8", xml_declaration=True) + b"\n"
    content[f"{ADDON}/{news.text}"] = NOTES.encode()
    modified = {name for name, data in content.items() if original.get(name) != data}
    expected = {f"{ADDON}/{rel}" for rel in OVERLAY}
    expected.update({manifest, f"{ADDON}/changelog-{VERSION}.txt"})
    if modified != expected:
        raise ValueError("out-of-scope skin payload changes: " + str(modified ^ expected))
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output,"x",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for member,data in sorted(content.items()):
            if not member.startswith(ADDON + "/") or ".." in Path(member).parts:
                raise ValueError("unsafe ZIP member")
            info = zipfile.ZipInfo(member,TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            z.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    with zipfile.ZipFile(output) as z:
        if z.testzip() is not None:
            raise ValueError("Beta2 ZIP CRC failed")
        if ET.fromstring(z.read(manifest)).get("version")!=VERSION:
            raise ValueError("Beta2 version incorrect")
    return {"version": VERSION, "sha256": sha(output.read_bytes()), "bytes":output.stat().st_size,
            "members":len(content), "changed_paths": sorted(modified)}


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=ROOT/"build/touch-refinement/skin.actweeter-1.2.41~beta2.zip")
    print(json.dumps(build(parser.parse_args().output),indent=2,ensure_ascii=False))
