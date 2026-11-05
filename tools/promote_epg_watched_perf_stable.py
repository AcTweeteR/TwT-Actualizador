#!/usr/bin/env python3
"""Create-only release of 2026-11-05 EPG/watched/performance Testing Beta.

Stable version numbers increase. Existing Service, external add-ons, previous
Stable files, Kodi profiles and the moving Testing feed remain untouched.
Source inputs and previous Stable index are pinned to publication SHA256.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import promote_beta34_stable as common

ROOT = Path(__file__).resolve().parents[1]
BETA_MANIFEST = ROOT / "manifests/actweeter-epg-watched-performance-beta-20261105.json"
SOURCE_COMMIT = "d41512caf58c83888aa4d6bf00609221f92dc7ac"
PREVIOUS_INDEX = "1c09e8f65b829378a0cb4359b5424034c4c5073692d1b435efe9e531240ba7a5"
PROMOTED_INDEX = "ac4bffccee2d60b1bd05eeafb33c1e7b037c881c030b16b67e9faef4d206412a"
VERSIONS = {
    "skin.actweeter": ("1.2.41~beta4", "1.2.41"),
    "plugin.video.xstream-pro": ("1.1.2.40~beta2", "1.1.2.41"),
}
NOTES = {
    "skin.actweeter": (
        b"1.2.41 Stable - EPG event title visibility and existing touch-mode refinements.\n"
        b"AcTweeteR XStream 1.1.2.41 adds watched state refresh and faster Home widgets.\n"
    ),
}
RELEASE = "actweeter-stable-epg-watched-performance-20261105"
DATE = "2026-11-05"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checked_source_from_commit(relative: str, expected: str) -> bytes:
    data = subprocess.check_output(["git", "show", SOURCE_COMMIT + ":" + relative], cwd=ROOT)
    if sha(data) != expected:
        raise ValueError("pinned historical file differs: " + relative)
    return data


def strictly_higher(new: str, old: str) -> bool:
    values = lambda x: tuple(int(part) for part in x.split("."))
    return values(new) > values(old)


def build(output):
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError("refusing to overwrite Stable candidate")
    beta = json.loads(BETA_MANIFEST.read_text(encoding="utf-8"))
    if (beta.get("release") != "actweeter-epg-watched-performance-beta-20261105"
            or beta.get("channel") != "testing"):
        raise ValueError("unexpected Beta release")
    if set(beta["new_packages"]) != set(VERSIONS):
        raise ValueError("unexpected Beta package scope")
    beta_index = checked_source_from_commit(
        "docs/testing/repo/addons.xml", beta["testing_index_sha256"])
    live_beta_index = (ROOT / "docs/testing/repo/addons.xml").read_bytes()
    published_index = (ROOT / "repo/addons.xml").read_bytes()
    current_sha = sha(published_index)
    later_release = ROOT / "manifests/actweeter-stable-stabilization-20261105.json"
    later_matches = False
    if later_release.is_file():
        later = json.loads(later_release.read_text(encoding="utf-8"))
        archive = ROOT / "manifests/archive/epg-watched-perf-stable-addons-20261105.xml"
        later_matches = (later.get("previous_index_sha256") == PROMOTED_INDEX
                         and later.get("index_sha256") == current_sha
                         and archive.is_file() and sha(archive.read_bytes()) == PROMOTED_INDEX)
    if live_beta_index != beta_index and current_sha != PROMOTED_INDEX and not later_matches:
        raise ValueError("Testing source changed after publication")
    if hashlib.md5(beta_index).hexdigest() != beta["testing_index_md5"]:
        raise ValueError("Testing checksum differs from manifest")

    previous = checked_source_from_commit("repo/addons.xml", PREVIOUS_INDEX)
    if current_sha not in (PREVIOUS_INDEX, PROMOTED_INDEX) and not later_matches:
        raise ValueError("Stable changed outside expected promotion history")
    # Once promoted, the historical source stays pinned; never rebuild
    # a new release from a moving index or overwrite an older release.
    if ((ROOT / "repo/addons.xml.md5").read_text().strip()
            != hashlib.md5(published_index).hexdigest()):
        raise ValueError("predecessor index md5 mismatch")
    old_index = ET.fromstring(previous)
    if tuple(a.get("id") for a in old_index) != common.EXPECTED_IDS:
        raise ValueError("unexpected Stable identities")
    if any(a.get("id") not in VERSIONS and a.get("id") != "service.actweeter"
           and a.get("id") not in ("repository.actweeter", "repository.rivulet",
                                   "repository.zachmorris") for a in old_index):
        raise ValueError("unexpected non-released Stable add-on")

    for addon, (beta_version, _) in VERSIONS.items():
        row = beta["new_packages"][addon]
        if row["version"] != beta_version:
            raise ValueError("unexpected Beta version for " + addon)
        relative = "docs/testing/repo/" + addon + "/" + addon + "-" + beta_version + ".zip"
        disk = ROOT / relative
        if sha(disk.read_bytes()) != row["sha256"]:
            raise ValueError("Beta ZIP hash mismatch " + addon)
        checked_source_from_commit(relative, row["sha256"])
        common.addon_from_zip(disk, addon, beta_version)

    output.mkdir(parents=True)
    stage_index = ET.Element("addons")
    entries, assets = [], []
    for current in old_index:
        addon = current.get("id")
        old_version = current.get("version")
        if addon in VERSIONS:
            beta_version, stable_version = VERSIONS[addon]
            if not strictly_higher(stable_version, old_version):
                raise ValueError("Stable version must increase: " + addon)
            candidate = output / "repo" / addon / (addon + "-" + stable_version + ".zip")
            candidate.parent.mkdir(parents=True, exist_ok=True)
            source = ROOT / "docs/testing/repo" / addon / (addon + "-" + beta_version + ".zip")
            common.promote(source, candidate, addon, beta_version, stable_version,
                           (beta_version, stable_version), NOTES)
            published = ROOT / "repo" / addon / candidate.name
            if published.is_symlink() or (published.exists() and (
                    not published.is_file() or
                    published.read_bytes() != candidate.read_bytes())):
                raise FileExistsError("existing Stable ZIP differs; refusing overwrite: " + str(published))
            promoted = common.addon_from_zip(candidate, addon, stable_version)
            assets += common.publish_metadata(candidate, promoted, output)
            relative = Path("repo") / addon / candidate.name
        else:
            relative = Path("repo") / addon / (addon + "-" + old_version + ".zip")
            candidate = ROOT / relative
            promoted = common.addon_from_zip(candidate, addon, old_version)
        for dep in promoted.findall("requires/import"):
            if "~beta" in str(dep.get("version", "")).lower():
                raise ValueError("Stable must not require Beta: " + addon)
        stage_index.append(promoted)
        entries.append({"id": addon, "version": promoted.get("version"),
                        "path": str(relative), "sha256": sha(candidate.read_bytes())})

    service = stage_index.find("addon[@id='service.actweeter']")
    dep = service.find("requires/import[@addon='plugin.video.xstream-pro']")
    trakt = service.find("requires/import[@addon='script.trakt']")
    if dep is None or not dep.get("version") or not strictly_higher(
            VERSIONS["plugin.video.xstream-pro"][1], dep.get("version")):
        raise ValueError("existing Service minimum XStream dependency not satisfied")
    if trakt is None or trakt.get("optional") == "true":
        raise ValueError("required Trakt dependency lost")
    if service.get("version") != "0.4.98":
        raise ValueError("unexpected Service change")

    data = ET.tostring(stage_index, encoding="utf-8", xml_declaration=True) + b"\n"
    (output / "repo/addons.xml").write_bytes(data)
    (output / "repo/addons.xml.md5").write_text(hashlib.md5(data).hexdigest() + "\n")
    result = {
        "release": RELEASE, "channel": "stable", "release_date": DATE,
        "source_commit": SOURCE_COMMIT,
        "beta_manifest": str(BETA_MANIFEST.relative_to(ROOT)),
        "beta_index_sha256": beta["testing_index_sha256"],
        "previous_index_sha256": PREVIOUS_INDEX,
        "index_sha256": sha(data), "index_md5": hashlib.md5(data).hexdigest(),
        "addons": entries, "assets": assets,
        "runtime_lenovo_verified": False, "runtime_epg_validated": False,
        "compatibility_note": "EPG display fix does not supply programs for channels without XMLTV IDs",
    }
    (output / "manifest.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.output_dir)
    print(json.dumps({
        "release": result["release"], "index_sha256": result["index_sha256"],
        "versions": {x["id"]: x["version"] for x in result["addons"]},
        "assets": [x["path"] for x in result["assets"]]
    }, indent=2))
