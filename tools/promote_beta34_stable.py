#!/usr/bin/env python3
"""Create-only, reproducible Stable promotion from the published Beta34 ZIPs."""
from __future__ import annotations

import argparse
import hashlib
import json
import stat
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source/0.4.32/tools"))
from build_distribution_index import addon_from_zip  # noqa: E402

BETA_MANIFEST = ROOT / "manifests/actweeter-beta34-20261027.json"
VERSIONS = {
    "skin.actweeter": ("1.2.36~beta4", "1.2.36"),
    "service.actweeter": ("0.4.94~beta8", "0.4.94"),
    "plugin.video.xstream-pro": ("1.1.2.36~beta3", "1.1.2.36"),
}
EXPECTED_IDS = (
    "repository.actweeter", "skin.actweeter", "service.actweeter",
    "plugin.video.xstream-pro", "repository.rivulet", "repository.zachmorris",
)
NOTES = {
    "skin.actweeter": b"1.2.36 Stable - identical Beta34 functionality.\n",
    "service.actweeter": b"0.4.94 Stable - identical Beta34 functionality; required add-ons remain required.\n",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def promote(archive: Path, target: Path, addon_id: str, beta: str, stable: str,
            xstream_versions=VERSIONS["plugin.video.xstream-pro"], notes=NOTES) -> None:
    if target.exists() or target.is_symlink():
        raise ValueError("refusing to overwrite Stable ZIP: " + str(target))
    addon_from_zip(archive, addon_id, beta)
    with zipfile.ZipFile(archive) as source, zipfile.ZipFile(target, "x") as output:
        names = source.namelist()
        manifest_name = f"{addon_id}/addon.xml"
        note_name = f"{addon_id}/changelog-{stable}.txt"
        if note_name in names:
            raise ValueError("Stable release note already exists")
        for info in source.infolist():
            data = source.read(info)
            if info.filename == manifest_name:
                old = f'version="{beta}"'.encode()
                if data.count(old) != 1:
                    raise ValueError("unexpected Beta version metadata")
                data = data.replace(old, f'version="{stable}"'.encode())
                if addon_id == "service.actweeter":
                    dependency = f'<import addon="plugin.video.xstream-pro" version="{xstream_versions[0]}" />'.encode()
                    if data.count(dependency) != 1:
                        raise ValueError("unexpected XStream dependency metadata")
                    data = data.replace(dependency, f'<import addon="plugin.video.xstream-pro" version="{xstream_versions[1]}" />'.encode())
                if addon_id in notes:
                    old_news = f"<news>changelog-{beta}.txt</news>".encode()
                    if data.count(old_news) != 1:
                        raise ValueError("unexpected Beta release note metadata")
                    data = data.replace(old_news, f"<news>changelog-{stable}.txt</news>".encode())
                ET.fromstring(data)
            output.writestr(info, data)
        if addon_id in notes:
            note = zipfile.ZipInfo(note_name, source.infolist()[0].date_time)
            note.compress_type = zipfile.ZIP_DEFLATED
            note.external_attr = (stat.S_IFREG | 0o644) << 16
            output.writestr(note, notes[addon_id], compress_type=zipfile.ZIP_DEFLATED,
                            compresslevel=9)
    addon_from_zip(target, addon_id, stable)


def publish_metadata(package: Path, addon: ET.Element, output: Path) -> list[dict]:
    addon_id = addon.get("id")
    metadata = addon.find("extension[@point='xbmc.addon.metadata']")
    if metadata is None:
        raise ValueError("missing add-on metadata: " + addon_id)
    assets = metadata.find("assets")
    references = [node.text for node in assets] if assets is not None else []
    news = metadata.findtext("news")
    if news:
        references.append(news)
    result = []
    with zipfile.ZipFile(package) as archive:
        for reference in references:
            if not reference or reference.startswith("/") or any(
                    part in ("", ".", "..") for part in reference.split("/")):
                raise ValueError("unsafe add-on metadata path: " + addon_id)
            rel = Path("repo") / addon_id / reference
            data = archive.read(f"{addon_id}/{reference}")
            destination = output / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                raise ValueError("duplicate add-on metadata path: " + str(rel))
            destination.write_bytes(data)
            result.append(dict(path=str(rel), sha256=sha(data)))
    return result


def build(output: Path, *, beta_manifest=BETA_MANIFEST, versions=VERSIONS,
          testing_index_path=ROOT / "manifests/archive/beta34-testing-addons.xml",
          stable_index_path=ROOT / "manifests/archive/beta34-stable-addons.xml",
          notes=NOTES, previous_index_sha256="7ce09e4d820d8c52ec697d7a2bac5451a1076eec5d89e2234072be490efe54ee",
          release="actweeter-stable-beta34-20261027",
          beta_release="actweeter-beta34-20261027") -> dict:
    if output.exists() or output.is_symlink():
        raise ValueError("refusing to overwrite Stable candidate")
    beta = json.loads(beta_manifest.read_text())
    if beta.get("release") != beta_release or beta.get("channel") != "testing":
        raise ValueError("unexpected Beta manifest")
    testing_index = testing_index_path.read_bytes()
    if sha(testing_index) != beta["index_sha256"]:
        raise ValueError("Testing index differs from Beta34 manifest")
    sources = {row["id"]: row for row in beta["addons"]}
    if set(sources) != {"repository.actweeter.testing", *versions,
                        "repository.rivulet", "repository.zachmorris"}:
        raise ValueError("unexpected Beta34 package set")
    for addon_id, row in sources.items():
        version = row["version"]
        expected = Path("docs/testing/repo") / addon_id / f"{addon_id}-{version}.zip"
        if Path(row["path"]) != expected:
            raise ValueError("unexpected Beta34 package path or version")
        package = ROOT / expected
        if sha(package.read_bytes()) != row["sha256"]:
            raise ValueError("Beta34 ZIP hash differs: " + addon_id)
        addon = addon_from_zip(package, addon_id, version)
        dependencies = [dict(id=dep.get("addon"), version=dep.get("version"),
                             optional=dep.get("optional") == "true")
                        for dep in addon.findall("requires/import")]
        if dependencies != row["dependencies"]:
            raise ValueError("Beta34 dependency manifest differs: " + addon_id)
    current = ET.fromstring(stable_index_path.read_bytes())
    if tuple(node.get("id") for node in current) != EXPECTED_IDS:
        raise ValueError("unexpected current Stable index")
    output.mkdir(parents=True)
    entries = []
    assets = []
    index = ET.Element("addons")
    for old in current:
        addon_id = old.get("id")
        if addon_id in versions:
            beta_version, stable_version = versions[addon_id]
            old_version = old.get("version")
            if tuple(map(int, old_version.split("."))) > tuple(map(int, stable_version.split("."))):
                raise ValueError("Stable version would downgrade " + addon_id)
            source = ROOT / sources[addon_id]["path"]
            rel = Path("repo") / addon_id / f"{addon_id}-{stable_version}.zip"
            target = output / rel
            target.parent.mkdir(parents=True)
            promote(source, target, addon_id, beta_version, stable_version,
                    versions["plugin.video.xstream-pro"], notes)
            published = ROOT / rel
            if published.exists() or published.is_symlink():
                if not published.is_file() or published.read_bytes() != target.read_bytes():
                    raise ValueError("published Stable version has different bytes: " + addon_id)
            elif old_version == stable_version:
                raise ValueError("indexed Stable version has no matching ZIP: " + addon_id)
            addon = addon_from_zip(target, addon_id, stable_version)
            assets.extend(publish_metadata(target, addon, output))
        else:
            version = old.get("version")
            rel = Path("repo") / addon_id / f"{addon_id}-{version}.zip"
            target = ROOT / rel
            addon = addon_from_zip(target, addon_id, version)
            if addon_id in sources and sha(target.read_bytes()) != sources[addon_id]["sha256"]:
                raise ValueError("unchanged repository ZIP differs from Beta34: " + addon_id)
        for dep in addon.findall("requires/import"):
            if "~beta" in dep.get("version", ""):
                raise ValueError("Stable dependency points to Beta: " + addon_id)
        index.append(addon)
        entries.append(dict(id=addon_id, version=addon.get("version"), path=str(rel),
                            sha256=sha(target.read_bytes())))
    service_dep = index.find("addon[@id='service.actweeter']/requires/import[@addon='plugin.video.xstream-pro']")
    if service_dep is None or service_dep.get("version") != versions["plugin.video.xstream-pro"][1]:
        raise ValueError("Stable Service/XStream pair differs")
    service = index.find("addon[@id='service.actweeter']")
    if service.find("requires/import[@addon='script.trakt']") is None:
        raise ValueError("Stable Service lost mandatory script.trakt")
    data = ET.tostring(index, encoding="utf-8", xml_declaration=True) + b"\n"
    (output / "repo/addons.xml").write_bytes(data)
    md5 = hashlib.md5(data).hexdigest()
    (output / "repo/addons.xml.md5").write_text(md5 + "\n")
    manifest = dict(release=release, channel="stable",
                    release_date="2026-10-27",
                    beta_manifest=str(beta_manifest.relative_to(ROOT)),
                    source_commit=beta["source_commit"],
                    beta_index_sha256=beta["index_sha256"],
                    previous_index_sha256=previous_index_sha256,
                    index_sha256=sha(data),
                    index_md5=md5, addons=entries, assets=assets)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    output = args.output_dir.expanduser().resolve()
    if output.exists() or output.is_symlink():
        raise ValueError("refusing to overwrite Stable candidate")
    with tempfile.TemporaryDirectory(prefix=".actweeter-promotion-", dir=output.parent) as tmp:
        stage = Path(tmp) / "candidate"
        manifest = build(stage)
        stage.rename(output)
    print(json.dumps({"output": str(output), "index_sha256": manifest["index_sha256"]}))


if __name__ == "__main__":
    main()
