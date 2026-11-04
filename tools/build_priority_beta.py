#!/usr/bin/env python3
"""Build Beta from verified public Stable ZIPs and narrow readable overlays.

All three packages use their exact Stable archive as baseline. Kodi profile,
Trakt credentials, Apple TV installation and public Stable feed remain untouched.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import stat
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from priority_xstream_patch import patch_xstream

VERSIONS = {
    "skin.actweeter": ("1.2.39", "1.2.40~beta1",
                       "10810aa2ecc1ac7dfc0e9a5da024ea6e02b59d2b95c4b1aee9fac2f6c551cacd"),
    "service.actweeter": ("0.4.97", "0.4.98~beta1",
                          "97c97b99d505444537b3cd54a78ada619ead7c8b3e82b18a4545e8814049d428"),
    "plugin.video.xstream-pro": ("1.1.2.39", "1.1.2.40~beta1",
                                "2b69d236f1f64a3fe6898efdc3826e071bc9537021c2237735f3d37e15aabd02"),
}
FIXED_TIME = (2026, 11, 4, 0, 0, 0)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def build(output):
    output.mkdir(parents=True, exist_ok=True)
    sources = ROOT / "source/0.4.32/addons"
    result = {}
    for addon, (stable_version, beta_version, expected_sha) in VERSIONS.items():
        candidate = ROOT / "repo" / addon / f"{addon}-{stable_version}.zip"
        if digest(candidate.read_bytes()) != expected_sha:
            raise ValueError("Stable baseline digest mismatch: " + addon)
        with zipfile.ZipFile(candidate) as archive:
            if archive.testzip() is not None:
                raise ValueError("Stable baseline CRC mismatch")
            payloads = {name: archive.read(name) for name in archive.namelist()
                        if name and not name.endswith("/")}
        if addon == "skin.actweeter":
            for relative in [
                "1080i/IncludesFunctions.xml", "1080i/IncludesHomeWidgets.xml",
                "1080i/IncludesBingie.xml",
                "shortcuts/inicio-1.DATA.xml", "shortcuts/10000-1.DATA.xml",
                "shortcuts/moviehub.DATA.xml", "shortcuts/tvshowhub.DATA.xml",
            ]:
                payloads[addon + "/" + relative] = (sources / addon / relative).read_bytes()
        elif addon == "service.actweeter":
            for relative in ["setup.py", "resources/lib/kodi_auto_preview.py"]:
                payloads[addon + "/" + relative] = (sources / addon / relative).read_bytes()
        else:
            patch_xstream(payloads)

        name = addon + "/addon.xml"
        root = ET.fromstring(payloads[name])
        if root.get("id") != addon or root.get("version") != stable_version:
            raise ValueError("unexpected baseline add-on ID/version")
        root.set("version", beta_version)
        news_name = "changelog-" + beta_version + ".txt"
        metadata = root.find("./extension[@point='xbmc.addon.metadata']")
        if metadata is not None:
            news = metadata.find("news")
            if news is not None:
                news.text = news_name
        payloads[name] = ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"
        payloads[addon + "/" + news_name] = (
            (beta_version + "\n"
             "Priority Beta: automatic/manual trailers, series art and synopsis, "
             "monotonic episode progress, widget expansion, PVR XMLTV freshness.\n")
            .encode("utf-8"))
        # Name/version change deliberately stays above the published Stable.
        final = output / f"{addon}-{beta_version}.zip"
        if final.exists():
            raise FileExistsError("refusing to replace candidate ZIP: " + str(final))
        with zipfile.ZipFile(final, "w", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=9) as archive:
            for member, data in sorted(payloads.items()):
                if not member.startswith(addon + "/") or ".." in Path(member).parts:
                    raise ValueError("unsafe ZIP member")
                if member.endswith(".py"):
                    compile(data, member, "exec")
                if member.endswith(".xml"):
                    ET.fromstring(data)
                info = zipfile.ZipInfo(member, FIXED_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED,
                                 compresslevel=9)
        with zipfile.ZipFile(final) as archive:
            if archive.testzip():
                raise ValueError("broken candidate ZIP")
            actual = ET.fromstring(archive.read(name))
            if actual.get("version") != beta_version or actual.get("id") != addon:
                raise ValueError("candidate metadata mismatch")
        result[addon] = {"version": beta_version, "filename": str(final),
                         "sha256": digest(final.read_bytes()),
                         "members": len(payloads)}
        print(addon, beta_version, result[addon]["sha256"], len(payloads))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "build/priority-beta")
    args = parser.parse_args()
    build(args.output)
