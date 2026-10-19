#!/usr/bin/env python3
"""Guarded, in-place AcTweeteR upgrade of the existing Kodi Master profile.

No QA profile, no published repository changes, no provider credentials read.
Run only with Kodi stopped and an already-verified full Master profile backup.
Use --check before --apply; --rollback restores the original add-on directories.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "source/0.4.32/addons"
ZIP_PATH = ROOT / "docs/testing/repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.8.zip"
KODI = Path.home() / "Library/Application Support/Kodi"
ADDONS = ("plugin.video.xstream-pro", "service.actweeter", "skin.actweeter")
EXPECTED = {
    "plugin.video.xstream-pro": "1.1.2.8",
    "service.actweeter": "0.4.39",
    "skin.actweeter": "1.2.29~beta10",
}
GENERATED = "skin.actweeter/1080i/script-skinshortcuts-includes.xml"
TRAILER_ANCHORS = (
    "RunScript(service.actweeter,preview_spotlight)",
    "RunScript(slyguy.trailers,",
    "SetProperty(SLYGUY_TRAILER_RETURN_ID",
    "SetProperty(SLYGUY_TRAILER_RETURN_PENDING,1,Home)",
    "SetProperty(KeepPlayingPreview,1,Home)",
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def kodi_running():
    result = subprocess.run(
        ["/usr/bin/pgrep", "-fx", "/Applications/Kodi.app/Contents/MacOS/Kodi"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    return result.returncode == 0


def version(xml):
    return ET.fromstring(xml).get("version")


def inventory():
    files = {}
    for addon in ("service.actweeter", "skin.actweeter"):
        base = CANDIDATES / addon
        for path in sorted(base.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            rel = str(path.relative_to(CANDIDATES))
            if rel == GENERATED:
                continue
            files[rel] = path.read_bytes()
    with ZipFile(ZIP_PATH) as archive:
        corrupt = archive.testzip()
        if corrupt:
            raise RuntimeError("XStream archive checksum failed: " + corrupt)
        for item in archive.namelist():
            if not item.startswith("plugin.video.xstream-pro/") or item.endswith("/"):
                continue
            if ".." in Path(item).parts:
                raise RuntimeError("unsafe archive path")
            files[item] = archive.read(item)
    for addon in ADDONS:
        manifest = files.get(addon + "/addon.xml")
        if not manifest or version(manifest) != EXPECTED[addon]:
            raise RuntimeError("unexpected addon version: " + addon)
    return files


def protected_fingerprints(root):
    paths = (
        "addons/skin.actweeter/1080i/script-skinshortcuts-includes.xml",
        "userdata/guisettings.xml",
    )
    fingerprints = {}
    for name in paths:
        path = root / name
        if not path.is_file():
            continue
        if name.endswith("/guisettings.xml"):
            # Kodi legitimately updates its total-uptime counter at shutdown;
            # compare all actual settings and XML attributes, excluding only
            # that volatile counter. Never print configuration values.
            xml = ET.parse(path).getroot()
            semantic = [
                (node.tag, sorted(node.attrib.items()), (node.text or "").strip())
                for node in xml.iter() if node.tag != "systemtotaluptime"
            ]
            fingerprints[name] = sha(json.dumps(
                semantic, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        else:
            fingerprints[name] = sha(path.read_bytes())
    return fingerprints


def check_master_trailers(files, installed):
    relative = "1080i/IncludesBingie.xml"
    before = (installed / "skin.actweeter" / relative).read_text()
    after = files["skin.actweeter/" + relative].decode()
    for snippet in TRAILER_ANCHORS:
        old = sorted(line.strip() for line in before.splitlines() if snippet in line)
        new = sorted(line.strip() for line in after.splitlines() if snippet in line)
        if not old or old != new:
            raise RuntimeError("Master trailer action contract differs: " + snippet)


def require_backup(backup, installed):
    if not (backup / "addons/skin.actweeter/addon.xml").is_file():
        raise RuntimeError("missing full-profile backup: skin")
    for addon in ADDONS:
        actual = installed / addon / "addon.xml"
        prior = backup / "addons" / addon / "addon.xml"
        if not actual.is_file() or not prior.is_file():
            raise RuntimeError("missing add-on or backup: " + addon)
        if sha(actual.read_bytes()) != sha(prior.read_bytes()):
            raise RuntimeError("Master changed since backup: " + addon)
    for name, digest in protected_fingerprints(KODI).items():
        if protected_fingerprints(backup).get(name) != digest:
            raise RuntimeError("protected profile state differs from backup: " + name)


def restore_addons(backup, installed):
    for addon in ADDONS:
        prior = backup / "addons" / addon
        target = installed / addon
        if not prior.is_dir():
            raise RuntimeError("missing backup for " + addon)
        stage = target.with_name(target.name + ".master-restore-tmp")
        if stage.exists():
            raise RuntimeError("stale restoration directory: " + str(stage))
        shutil.copytree(prior, stage, copy_function=shutil.copy2)
        if target.exists():
            shutil.rmtree(target)
        os.replace(stage, target)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("check", "apply", "verify", "rollback"))
    parser.add_argument("--backup", required=True, type=Path)
    args = parser.parse_args()
    backup = args.backup.expanduser().resolve()
    installed = KODI / "addons"
    if args.operation != "verify" and kodi_running():
        raise RuntimeError("stop Kodi gracefully before modifying add-ons")
    if args.operation == "rollback":
        restore_addons(backup, installed)
        print("ROLLBACK_ADDONS_RESTORED; userdata profile unchanged")
        return
    if args.operation in ("check", "apply"):
        require_backup(backup, installed)
    files = inventory()
    check_master_trailers(files, installed)
    before = protected_fingerprints(KODI)
    counts = {addon: sum(k.startswith(addon + "/") for k in files) for addon in ADDONS}
    print("SOURCE_VERIFIED", json.dumps(counts, sort_keys=True))
    print("PRESERVE_GENERATED_INCLUDES", GENERATED)
    if args.operation == "verify":
        failures = [rel for rel, data in files.items()
                    if not (installed / rel).is_file()
                    or sha((installed / rel).read_bytes()) != sha(data)]
        if failures:
            raise RuntimeError("source/runtime divergence: " + ", ".join(failures[:8]))
        original = protected_fingerprints(backup)
        if any(before.get(name) != digest for name, digest in original.items()):
            raise RuntimeError("protected Master-generated UI or GUI preferences changed")
        print("POST_INSTALL_VERIFIED", len(files), "files; original UI/preferences intact")
        return
    if args.operation == "check":
        print("CHECK_ONLY_NO_CHANGES")
        return
    # In-place on the *same* Kodi Master, protecting generated XML and all
    # userdata/addon_data. No new player profile and no Beta channel update.
    try:
        for relative, data in files.items():
            target = installed / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and sha(target.read_bytes()) == sha(data):
                continue
            fd, tmp_name = tempfile.mkstemp(prefix=".actweeter-upgrade-", dir=target.parent)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.chmod(tmp_name, target.stat().st_mode & 0o777 if target.exists() else 0o644)
                os.replace(tmp_name, target)
            finally:
                if os.path.exists(tmp_name):
                    os.unlink(tmp_name)
        for rel, data in files.items():
            if sha((installed / rel).read_bytes()) != sha(data):
                raise RuntimeError("post-install file verification failed: " + rel)
        if protected_fingerprints(KODI) != before:
            raise RuntimeError("protected Master configuration mutated")
    except Exception:
        restore_addons(backup, installed)
        raise
    print("APPLIED_AND_HASH_VERIFIED", json.dumps(counts, sort_keys=True))
    print("PROTECTED_CONFIG_UNCHANGED")
    print("NOTE: Kodi runtime and provider playback are NOT YET validated")


if __name__ == "__main__":
    main()
