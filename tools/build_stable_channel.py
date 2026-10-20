#!/usr/bin/env python3
"""Create-only, deterministic promotion of a validated AcTweeteR Testing candidate.

Keep the full Beta feature payload identical; only change skin release metadata.
Stable's repository installer is unchanged, and archived ZIPs are never replaced.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source/0.4.32/tools"))
from build_distribution_index import addon_from_zip  # noqa: E402

BETA_VERSION = "1.2.30~beta2"
STABLE_VERSION = "1.2.30"
SKIN_ID = "skin.actweeter"
STABLE_NEWS = (
    "1.2.30 — Unified stable release\n\n"
    "- Consolidates the Mac Master and Android Beta navigation, including guarded autoplay and manual film/series trailers.\n"
    "- Preserves user-generated Skin Shortcuts menus on existing installations.\n"
    "- Compatible with AcTweeteR Service 0.4.45 and XStream Pro 1.1.2.10.\n"
    "- First-run on configured profiles respects an explicit 'Ahora no' without falsifying setup verification.\n"
    "- SlyGuy provider HTTP 429 remains external to AcTweeteR.\n"
).encode("utf-8")
EXPECTED_INPUT_SHA256 = {
    "repository": "74620e81ff9a161bb7b0650f01e94406ccc9fa9366210ebb36e58872bb4995e8",
    "skin": "752dffebc825702bbb613dec3939e77c5bb8f57cbd12dd12b7fcc169f677f349",
    "service": "6157eb988f0972c22d5ab665b48e90837f607af728684ec7e4a0bd6d7f5cec81",
    "xstream": "0824403e46d3d7ac1b8e4949e8d89f78e51727fec60680b015291bbff489bbf7",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_input(kind: str, archive: Path, addon_id: str, version: str) -> ET.Element:
    if _sha(archive) != EXPECTED_INPUT_SHA256[kind]:
        raise ValueError(f"unverified {kind} release input")
    return addon_from_zip(archive, addon_id, version)


def promote_skin(beta_zip: Path, stable_zip: Path) -> None:
    if stable_zip.exists() or stable_zip.is_symlink():
        raise ValueError("refusing to overwrite existing stable skin ZIP")
    verify_input("skin", beta_zip, SKIN_ID, BETA_VERSION)
    with zipfile.ZipFile(beta_zip, "r") as original:
        entries = original.infolist()
        root = SKIN_ID + "/"
        manifest_name = root + "addon.xml"
        new_news = root + f"changelog-{STABLE_VERSION}.txt"
        if new_news in original.namelist():
            raise ValueError("stable changelog already exists")
        with zipfile.ZipFile(stable_zip, "x", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=9) as output:
            for info in entries:
                content = original.read(info)
                if info.filename == manifest_name:
                    before = f'version="{BETA_VERSION}"'.encode()
                    news_before = f"<news>changelog-{BETA_VERSION}.txt</news>".encode()
                    if content.count(before) != 1 or content.count(news_before) != 1:
                        raise ValueError("unrecognized skin metadata")
                    content = content.replace(before, f'version="{STABLE_VERSION}"'.encode())
                    content = content.replace(news_before,
                                              f"<news>changelog-{STABLE_VERSION}.txt</news>".encode())
                output.writestr(info, content, compress_type=zipfile.ZIP_DEFLATED,
                                compresslevel=9)
            import stat
            stable_note = zipfile.ZipInfo(new_news, entries[0].date_time)
            stable_note.compress_type = zipfile.ZIP_DEFLATED
            stable_note.external_attr = (stat.S_IFREG | 0o644) << 16
            output.writestr(stable_note, STABLE_NEWS, compress_type=zipfile.ZIP_DEFLATED,
                            compresslevel=9)
    addon_from_zip(stable_zip, SKIN_ID, STABLE_VERSION)


def build(output: Path) -> tuple[Path, Path, Path]:
    if output.exists() or output.is_symlink():
        raise ValueError("refusing to overwrite existing Stable release directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Only immutable already-published packages can become Stable.
    repo_zip = ROOT / "repo/repository.actweeter/repository.actweeter-1.0.3.zip"
    beta_zip = ROOT / "docs/testing/repo/skin.actweeter/skin.actweeter-1.2.30~beta2.zip"
    service_zip = ROOT / "docs/testing/repo/service.actweeter/service.actweeter-0.4.45.zip"
    xstream_zip = ROOT / "docs/testing/repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.10.zip"
    addon_repo = verify_input("repository", repo_zip, "repository.actweeter", "1.0.3")
    addon_service = verify_input("service", service_zip, "service.actweeter", "0.4.45")
    addon_xstream = verify_input("xstream", xstream_zip, "plugin.video.xstream-pro", "1.1.2.10")
    import tempfile
    import os
    with tempfile.TemporaryDirectory(prefix=".actweeter-stable-", dir=output.parent) as tmp:
        stage = Path(tmp) / "release"
        stage.mkdir()
        stable_zip = stage / "skin.actweeter-1.2.30.zip"
        promote_skin(beta_zip, stable_zip)
        addon_skin = addon_from_zip(stable_zip, SKIN_ID, STABLE_VERSION)
        for addon in (addon_repo, addon_skin, addon_service, addon_xstream):
            metadata = addon.find("extension[@point='xbmc.addon.metadata']")
            if metadata is None:
                raise ValueError(f"missing metadata {addon.get('id')}")
            news = metadata.find("news")
            if news is not None and news.text:
                # Avoid dangling release notes.
                name = addon.get("id") + "/" + news.text
                with zipfile.ZipFile(
                    {"repository.actweeter": repo_zip, "skin.actweeter": stable_zip,
                     "service.actweeter": service_zip,
                     "plugin.video.xstream-pro": xstream_zip}[addon.get("id")]
                ) as z:
                    if name not in z.namelist():
                        raise ValueError("missing release notes: " + name)
        index = ET.Element("addons")
        for addon in (addon_repo, addon_skin, addon_service, addon_xstream):
            index.append(addon)
        data = ET.tostring(index, encoding="utf-8", xml_declaration=True) + b"\n"
        (stage / "addons.xml").write_bytes(data)
        (stage / "addons.xml.md5").write_text(hashlib.md5(data).hexdigest() + "\n")
        # Output is a new directory; no source or repository files are edited.
        stage.rename(output)
    return output / "skin.actweeter-1.2.30.zip", output / "addons.xml", output / "addons.xml.md5"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    for artifact in build(args.output_dir.expanduser().resolve()):
        print(str(artifact), _sha(artifact))


if __name__ == "__main__":
    main()
