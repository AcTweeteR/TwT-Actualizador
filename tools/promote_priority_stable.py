#!/usr/bin/env python3
"""Deterministic, create-only promotion of the published 2026-11-04 priority Beta."""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from xml.etree import ElementTree as ET

import promote_beta34_stable as common

ROOT = Path(__file__).resolve().parents[1]
BETA_MANIFEST = ROOT / "manifests/actweeter-priority-beta-20261104.json"
PREVIOUS_INDEX = 'fe432d1002bf279dceae29d675ec5432448acb03198377b6fe6fedf8a9b872cd'
SOURCE_COMMIT = "092587c54d578c422851058fd766a3c6082dba5f"
VERSIONS = {
    "skin.actweeter": ("1.2.40~beta1", "1.2.40"),
    "service.actweeter": ("0.4.98~beta1", "0.4.98"),
    "plugin.video.xstream-pro": ("1.1.2.40~beta1", "1.1.2.40"),
}
NOTES = {
    "skin.actweeter": b"1.2.40 Stable - trailer previews, widgets and metadata fixes.\n",
    "service.actweeter": b"0.4.98 Stable - trailer preview handling.\n",
}

def build(output):
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError("refusing to overwrite candidate")
    beta = json.loads(BETA_MANIFEST.read_text())
    if beta.get("release") != "actweeter-priority-beta-20261104" or beta["channel"] != "testing":
        raise ValueError("unexpected Beta manifest")
    if set(beta["packages"]) != set(VERSIONS):
        raise ValueError("unexpected Beta components")
    # Newer Testing Betas update the live index. Verify the historical index
    # against its immutable publication commit instead of the moving live feed.
    historical_index = subprocess.check_output(
        ["git", "show", SOURCE_COMMIT + ":" + beta["index"]["path"]], cwd=ROOT)
    if common.sha(historical_index) != beta["index"]["sha256"]:
        raise ValueError("historical published Beta index mismatch")
    for rel in [row["path"] for row in beta["packages"].values()]:
        if subprocess.check_output(["git", "show", SOURCE_COMMIT + ":" + rel], cwd=ROOT) != (ROOT / rel).read_bytes():
            raise ValueError("published Beta source differs: " + rel)
    predecessor = subprocess.check_output(["git", "show", SOURCE_COMMIT + ":repo/addons.xml"], cwd=ROOT)
    if common.sha(predecessor) != PREVIOUS_INDEX:
        raise ValueError("unexpected Stable predecessor")
    old_index = ET.fromstring(predecessor)
    if tuple(node.get("id") for node in old_index) != common.EXPECTED_IDS:
        raise ValueError("unexpected Stable add-ons")
    output.mkdir(parents=True)
    index = ET.Element("addons")
    entries, assets = [], []
    for old in old_index:
        addon_id = old.get("id")
        if addon_id in VERSIONS:
            beta_version, stable_version = VERSIONS[addon_id]
            row = beta["packages"][addon_id]
            if row["version"] != beta_version:
                raise ValueError("unexpected published version: " + addon_id)
            if tuple(map(int, stable_version.split("."))) <= tuple(map(int, old.get("version").split("."))):
                raise ValueError("Stable version must increase: " + addon_id)
            source = ROOT / row["path"]
            if common.sha(source.read_bytes()) != row["sha256"]:
                raise ValueError("Beta package changed: " + addon_id)
            relative = Path("repo") / addon_id / f"{addon_id}-{stable_version}.zip"
            target = output / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            common.promote(source, target, addon_id, beta_version, stable_version,
                           ("1.1.2.39", "1.1.2.40"), NOTES)
            existing = ROOT / relative
            if existing.is_symlink() or (existing.exists() and existing.read_bytes() != target.read_bytes()):
                raise ValueError("existing Stable package has different bytes: " + str(relative))
            addon = common.addon_from_zip(target, addon_id, stable_version)
            assets.extend(common.publish_metadata(target, addon, output))
        else:
            relative = Path("repo") / addon_id / f"{addon_id}-{old.get('version')}.zip"
            target = ROOT / relative
            addon = common.addon_from_zip(target, addon_id, old.get("version"))
        if any("~beta" in dep.get("version", "").lower() for dep in addon.findall("requires/import")):
            raise ValueError("Stable dependency points to Beta: " + addon_id)
        index.append(addon)
        entries.append({"id": addon_id, "version": addon.get("version"),
                        "path": str(relative), "sha256": common.sha(target.read_bytes())})
    service = index.find("addon[@id='service.actweeter']")
    dep = service.find("requires/import[@addon='plugin.video.xstream-pro']")
    trakt = service.find("requires/import[@addon='script.trakt']")
    if dep is None or dep.get("version") != "1.1.2.40":
        raise ValueError("new XStream dependency not required")
    if trakt is None or trakt.get("optional") == "true":
        raise ValueError("Trakt dependency missing")
    data = ET.tostring(index, encoding="utf-8", xml_declaration=True) + b"\n"
    (output / "repo/addons.xml").write_bytes(data)
    (output / "repo/addons.xml.md5").write_text(hashlib.md5(data).hexdigest() + "\n")
    result = {"release": "actweeter-stable-priority-20261104", "channel": "stable",
              "release_date": "2026-11-04", "source_commit": SOURCE_COMMIT,
              "beta_manifest": str(BETA_MANIFEST.relative_to(ROOT)),
              "previous_index_sha256": PREVIOUS_INDEX,
              "beta_index_sha256": beta["index"]["sha256"],
              "index_sha256": common.sha(data), "index_md5": hashlib.md5(data).hexdigest(),
              "addons": entries, "assets": assets, "runtime_apple_tv_verified": False}
    (output / "manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.output_dir), indent=2))
