#!/usr/bin/env python3
"""Build/validate the manually published Kodi repository; never uploads."""
from __future__ import annotations

import hashlib
import json
import re
import stat
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SKIN_ID = "skin.actweeter"
SKIN_VERSION = "1.1.1"
REPOSITORY_ID = "repository.actweeter"
REPOSITORY_VERSION = "1.0.1"
SKIN_ZIP = ROOT / "repo" / SKIN_ID / f"{SKIN_ID}-{SKIN_VERSION}.zip"
REPOSITORY_DIR = ROOT / REPOSITORY_ID
REPOSITORY_ZIP = REPOSITORY_DIR / f"{REPOSITORY_ID}-{REPOSITORY_VERSION}.zip"
REPOSITORY_PUBLISHED_ZIP = ROOT / "repo" / REPOSITORY_ID / f"{REPOSITORY_ID}-{REPOSITORY_VERSION}.zip"
BOOTSTRAP_ZIP = ROOT / "docs" / "bootstrap" / f"{REPOSITORY_ID}-{REPOSITORY_VERSION}.zip"
INDEX = ROOT / "repo" / "addons.xml"
MD5 = ROOT / "repo" / "addons.xml.md5"
UPSTREAM_INDEX = ROOT / "repo" / "upstream-bingie" / "addons.xml"
UPSTREAM_MD5 = ROOT / "repo" / "upstream-bingie" / "addons.xml.md5"
MANIFEST = ROOT / "manifests" / f"{SKIN_VERSION}.json"
CHECKSUMS = ROOT / "checksums" / "SHA256SUMS"
REPOSITORY_CHANGELOG = REPOSITORY_DIR / f"changelog-{REPOSITORY_VERSION}.txt"
UPSTREAM_ADDONS = {
    "script.bingie.helper", "script.bingie.toolbox", "script.bingie.widgets",
    "resource.images.studios.coloured", "plugin.video.tmdb.bingie.helper",
    "plugin.program.autocompletion", "script.module.bingie",
}
SENSITIVE = [
    re.compile(rb"/Users/[^/\s]+/Library/Application Support/Kodi", re.I),
    re.compile(rb"(?i)(?:password|client_secret|access_token|api_key)\s*[=:]\s*[\"']?[^\s\"']{6,}"),
    re.compile(rb"(?i)https?://[^\s\"']*(?:xtream|m3u|xmltv)[^\s\"']*"),
    re.compile(rb"(?i)(?:username|user)\s*[=:]\s*[\"'][^\"']{2,}[\"']"),
]
FORBIDDEN_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".log", ".m3u", ".m3u8", ".epg", ".xmltv"}
FIXED_TIME = (2026, 10, 3, 0, 0, 0)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def scan_zip(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        require(archive.testzip() is None, f"ZIP CRC failed: {path.name}")
        names = archive.namelist()
        require(names and all(name.startswith(f"{SKIN_ID}/") for name in names), "unexpected ZIP root")
        require(not any("netflix-sans" in name.lower() or name.lower().endswith("/impact.ttf") for name in names),
                "non-cleared font binary remains")
        require(not any("userdata" in name.lower() or "addon_data" in name.lower() for name in names),
                "personal Kodi state path in package")
        for info in archive.infolist():
            require(Path(info.filename).suffix.lower() not in FORBIDDEN_SUFFIXES,
                    f"personal-state file type in package: {info.filename}")
            if info.is_dir():
                continue
            data = archive.read(info)
            if b"\x00" not in data[:4096]:
                for pattern in SENSITIVE:
                    require(pattern.search(data) is None,
                            f"sensitive-pattern match in {info.filename}; inspect privately")
        addon = ET.fromstring(archive.read(f"{SKIN_ID}/addon.xml"))
        require(addon.get("id") == SKIN_ID and addon.get("version") == SKIN_VERSION,
                "skin id/version mismatch")


def zip_tree(source: Path, output: Path, root_name: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(p for p in source.rglob("*") if p.is_file() and p != output and p.suffix.lower() != ".zip"):
            relative = Path(root_name) / path.relative_to(source)
            info = zipfile.ZipInfo(relative.as_posix(), FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def build() -> None:
    require(SKIN_ZIP.is_file(), f"missing {SKIN_ZIP.relative_to(ROOT)}")
    scan_zip(SKIN_ZIP)
    require((ROOT / "repo" / SKIN_ID / "resources" / "icon.png").is_file(), "missing skin icon asset")
    require((ROOT / "repo" / SKIN_ID / "fanart.jpg").is_file(), "missing skin fanart asset")
    require((ROOT / "repo" / SKIN_ID / f"changelog-{SKIN_VERSION}.txt").is_file(), "missing skin changelog")
    repository_xml = ET.parse(REPOSITORY_DIR / "addon.xml").getroot()
    require(repository_xml.get("id") == REPOSITORY_ID and repository_xml.get("version") == REPOSITORY_VERSION,
            "repository id/version mismatch")
    zip_tree(REPOSITORY_DIR, REPOSITORY_ZIP, REPOSITORY_ID)
    require(zipfile.ZipFile(REPOSITORY_ZIP).testzip() is None, "repository ZIP CRC failed")
    REPOSITORY_PUBLISHED_ZIP.parent.mkdir(parents=True, exist_ok=True)
    REPOSITORY_PUBLISHED_ZIP.write_bytes(REPOSITORY_ZIP.read_bytes())
    BOOTSTRAP_ZIP.parent.mkdir(parents=True, exist_ok=True)
    BOOTSTRAP_ZIP.write_bytes(REPOSITORY_ZIP.read_bytes())
    require(REPOSITORY_CHANGELOG.is_file(), "missing repository changelog")

    skin_xml = ET.fromstring(zipfile.ZipFile(SKIN_ZIP).read(f"{SKIN_ID}/addon.xml"))
    upstream_root = ET.parse(UPSTREAM_INDEX).getroot()
    upstream_by_id = {addon.get("id"): addon for addon in upstream_root.findall("addon")}
    require(UPSTREAM_ADDONS <= upstream_by_id.keys(), "upstream dependency metadata missing")
    upstream_payload = UPSTREAM_INDEX.read_bytes()
    require(UPSTREAM_MD5.read_text(encoding="ascii").strip() == hashlib.md5(upstream_payload).hexdigest(),
            "upstream metadata checksum mismatch")
    for addon_id in UPSTREAM_ADDONS:
        require(upstream_by_id[addon_id].find("extension") is not None, f"invalid upstream metadata: {addon_id}")

    repository_zip = zipfile.ZipFile(REPOSITORY_ZIP)
    repository_entry = ET.fromstring(repository_zip.read(f"{REPOSITORY_ID}/addon.xml"))
    addons = ET.Element("addons")
    addons.append(repository_entry)
    addons.append(skin_xml)
    payload = ET.tostring(addons, encoding="utf-8", xml_declaration=True) + b"\n"
    INDEX.write_bytes(payload)
    MD5.write_text(hashlib.md5(payload).hexdigest() + "\n", encoding="ascii")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["artifacts"] = {
        "skin_zip_sha256": sha256(SKIN_ZIP),
        "repository_zip_sha256": sha256(REPOSITORY_ZIP),
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    artifact_paths = [SKIN_ZIP, REPOSITORY_ZIP, REPOSITORY_PUBLISHED_ZIP, BOOTSTRAP_ZIP]
    existing = {}
    if CHECKSUMS.exists():
        for line in CHECKSUMS.read_text(encoding="ascii").splitlines():
            digest, path = line.split(maxsplit=1)
            existing[path] = digest
    for old_path in (REPOSITORY_DIR / f"{REPOSITORY_ID}-1.0.0.zip",):
        if old_path.is_file():
            existing[old_path.relative_to(ROOT).as_posix()] = sha256(old_path)
    for path in artifact_paths:
        existing[path.relative_to(ROOT).as_posix()] = sha256(path)
    CHECKSUMS.write_text("".join(f"{digest}  {path}\n" for path, digest in sorted(existing.items())),
                         encoding="ascii")

    ET.parse(INDEX)
    require(MD5.read_text(encoding="ascii").strip() == hashlib.md5(INDEX.read_bytes()).hexdigest(),
            "addons.xml checksum mismatch")
    require(manifest["version"] == SKIN_VERSION and manifest["channel"] == "dev", "manifest mismatch")
    print(f"Kodi index valid: {INDEX.relative_to(ROOT)}")
    print(f"Skin ZIP SHA-256: {sha256(SKIN_ZIP)}")
    print(f"Repository ZIP SHA-256: {sha256(REPOSITORY_ZIP)}")
    print(f"Kodi-published repository ZIP SHA-256: {sha256(REPOSITORY_PUBLISHED_ZIP)}")
    print(f"Upstream dependency metadata entries: {len(UPSTREAM_ADDONS)}")
    print("Sensitive pattern scan: PASS (no match values emitted)")


if __name__ == "__main__":
    build()
