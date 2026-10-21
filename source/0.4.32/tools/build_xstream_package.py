#!/usr/bin/env python3
"""Build the locally patched XStream 1.1.2 Kodi package from its verified ZIP.

The source ZIP is fetched from the upstream release by the caller. This tool
checks its locked SHA-256, applies only the tracked AcTweeteR patch set, keeps
the upstream license and adds an explicit modification notice. It never writes
the third-party source into the repository.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import stat
import subprocess
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "third_party" / "xstream" / "upstream.json"
PATCHES = (
    ("patch", ROOT / "third_party/xstream/patches/1.1.2/actweeter-runtime.patch"),
    ("integration_patch", ROOT / "third_party/xstream/patches/1.1.2/actweeter-setup-refresh.patch"),
    ("recommendations_patch", ROOT / "third_party/xstream/patches/1.1.2/actweeter-trakt-recommendations.patch"),
    ("playback_metadata_patch", ROOT / "third_party/xstream/patches/1.1.2/actweeter-script-trakt.patch"),
    ("search_index_patch", ROOT / "third_party/xstream/patches/1.1.2/actweeter-search-index-bulk.patch"),
    ("prefetch_patch", ROOT / "third_party/xstream/patches/1.1.2/actweeter-widget-prefetch.patch"),
    ("performance_patch", ROOT / "third_party/xstream/patches/1.1.2/actweeter-performance-diagnostics.patch"),
    ("catalog_index_patch", ROOT / "third_party/xstream/patches/1.1.2/actweeter-catalog-index.patch"),
    ("collections_patch", ROOT / "third_party/xstream/patches/1.1.2/actweeter-collections.patch"),
)
DIAGNOSTICS_SOURCE = ROOT / "third_party/xstream/performance_diagnostics.py"
CATALOG_INDEX_SOURCE = ROOT / "third_party/xstream/provider_catalog_index.py"
FIXED_TIME = (2026, 10, 11, 0, 0, 0)
UPSTREAM_ROOT = "plugin.video.xstream-pro"
EXCLUDED_SUFFIXES = {".orig", ".pyc", ".pyo"}


def should_package(path: Path) -> bool:
    """Exclude local/editor and interpreter artifacts from Kodi's add-on ZIP."""
    return ("__pycache__" not in path.parts
            and path.suffix.lower() not in EXCLUDED_SUFFIXES)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_python_sources(root: Path) -> int:
    """Parse every packaged Python file without importing or executing it."""
    files = sorted(path for path in root.rglob("*.py")
                   if should_package(path.relative_to(root)))
    for path in files:
        try:
            ast.parse(path.read_bytes(), filename=str(path.relative_to(root)))
        except (SyntaxError, UnicodeDecodeError) as exc:
            raise ValueError(
                "invalid Python syntax in {0}: {1}".format(
                    path.relative_to(root), exc
                )
            ) from exc
    return len(files)


def validate_python_archive(archive: zipfile.ZipFile) -> int:
    """Validate the Python sources as they were actually written to the ZIP."""
    members = sorted(name for name in archive.namelist()
                     if name.endswith(".py") and "__pycache__" not in name.split("/"))
    for name in members:
        try:
            ast.parse(archive.read(name), filename=name)
        except (SyntaxError, UnicodeDecodeError) as exc:
            raise ValueError("invalid Python syntax in packaged {0}: {1}".format(
                name, exc
            )) from exc
    return len(members)


def normalize_recommendation_patch_targets(root: Path) -> None:
    """Normalize CRLF upstream files so context-anchored patches match."""
    for relative in ("resources/lib/addon.py", "resources/lib/tmdb_routes.py"):
        path = root / relative
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))


def apply_contextual_unified_patch(root: Path, patch_path: Path) -> int:
    """Apply a unified patch by exact, unique source context, never line offsets.

    This avoids relying on line offsets or the platform's `patch` handling of
    CRLF files. Every old hunk must match exactly once or the build fails.
    """
    patch_bytes = patch_path.read_bytes()
    sections = patch_bytes.split(b"diff --git ")[1:]
    applied = 0
    for section in sections:
        target = None
        pending = None
        hunks = []
        for line in section.splitlines(keepends=True):
            if line.startswith(b"+++ b/"):
                target = line[6:].strip().decode("utf-8")
            elif line.startswith(b"@@"):
                if pending is not None:
                    hunks.append(pending)
                match = re.match(rb"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
                if not match:
                    raise ValueError("invalid unified patch hunk header")
                pending = {"old_count": int(match.group(2) or 1),
                           "new_count": int(match.group(4) or 1), "lines": []}
            elif pending is not None:
                if line.startswith((b" ", b"+", b"-")):
                    pending["lines"].append(line)
                elif line.startswith(b"\\"):
                    continue
                else:
                    hunks.append(pending)
                    pending = None
        if pending is not None:
            hunks.append(pending)
        if not target or not hunks:
            raise ValueError("unified patch target or hunks missing")
        target_path = root / target
        if not target_path.is_file() or ".." in Path(target).parts:
            raise ValueError("unsafe or missing unified patch target")
        for hunk in hunks:
            old_lines = [line[1:] for line in hunk["lines"]
                         if line.startswith((b" ", b"-"))]
            new_lines = [line[1:] for line in hunk["lines"]
                         if line.startswith((b" ", b"+"))]
            if len(old_lines) != hunk["old_count"] or len(new_lines) != hunk["new_count"]:
                raise ValueError("unified patch hunk line counts are inconsistent")
            old = b"".join(old_lines)
            new = b"".join(new_lines)
            source = target_path.read_bytes()
            if not old or source.count(old) != 1:
                raise ValueError("unified patch context is missing or ambiguous: {0}".format(target))
            if old == new:
                raise ValueError("unified patch hunk does not change its context")
            target_path.write_bytes(source.replace(old, new, 1))
            applied += 1
    return applied


def build(source_zip: Path, output: Path) -> dict[str, str]:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    expected = data["upstream_release_zip_sha256"]
    actual = sha256(source_zip)
    if actual != expected:
        raise ValueError("upstream XStream ZIP SHA-256 mismatch")

    with tempfile.TemporaryDirectory(prefix="actweeter-xstream-") as temp:
        root = Path(temp) / UPSTREAM_ROOT
        root.mkdir()
        with zipfile.ZipFile(source_zip) as archive:
            if archive.testzip() is not None:
                raise ValueError("upstream XStream ZIP CRC failed")
            names = [n for n in archive.namelist()
                     if n.startswith(UPSTREAM_ROOT + "/")]
            if not names or any(Path(n).is_absolute() or ".." in Path(n).parts
                                for n in names):
                raise ValueError("unexpected XStream ZIP paths")
            for name in names:
                info = archive.getinfo(name)
                if info.is_dir():
                    continue
                destination = root / Path(name).relative_to(UPSTREAM_ROOT)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.read(name))

        addon_xml = ET.parse(root / "addon.xml").getroot()
        if (addon_xml.get("id"), addon_xml.get("version")) != (
                "plugin.video.xstream-pro", data["upstream_version"]):
            raise ValueError("XStream add-on ID/version differs from the lock")
        license_path = root / "LICENCE.txt"
        if not license_path.is_file() or "CC BY-NC 4.0" not in license_path.read_text(
                encoding="utf-8"):
            raise ValueError("XStream upstream license missing or unexpected")

        for manifest_key, patch_path in PATCHES:
            if manifest_key in ("recommendations_patch", "search_index_patch", "prefetch_patch", "catalog_index_patch", "collections_patch"):
                # The pinned upstream archive uses CRLF in these files while
                # earlier tracked patches add LF. Normalize only these two
                # already-patched files before applying semantic context.
                normalize_recommendation_patch_targets(root)
            expected_patch_hash = data[manifest_key + "_sha256"]
            if sha256(patch_path) != expected_patch_hash:
                raise ValueError(f"patch hash mismatch: {patch_path.name}")
            if manifest_key in ("recommendations_patch", "search_index_patch", "prefetch_patch", "catalog_index_patch", "collections_patch"):
                apply_contextual_unified_patch(root, patch_path)
                continue
            result = subprocess.run(
                ["patch", "--batch", "--forward", "--ignore-whitespace",
                 "-p1", "-i", str(patch_path)],
                cwd=root, capture_output=True, text=True,
            )
            if result.returncode:
                detail = (result.stdout + result.stderr).strip()
                raise ValueError(f"patch application failed for {patch_path.name}: {detail}")

        if sha256(DIAGNOSTICS_SOURCE) != data["performance_diagnostics_sha256"]:
            raise ValueError("performance diagnostics source SHA-256 mismatch")
        diagnostics_target = root / "resources/lib/performance_diagnostics.py"
        diagnostics_target.write_bytes(DIAGNOSTICS_SOURCE.read_bytes())
        if sha256(CATALOG_INDEX_SOURCE) != data["catalog_index_source_sha256"]:
            raise ValueError("catalog index source SHA-256 mismatch")
        (root / "resources/lib/provider_catalog_index.py").write_bytes(
            CATALOG_INDEX_SOURCE.read_bytes())

        validate_python_sources(root)

        distribution_version = data["distribution_version"]
        notice = (
            "XStream Pro 1.1.2 by PesicP\n"
            "Upstream: https://github.com/Pesicp/XStreamPro/tree/1.1.2\n"
            "Upstream commit: 1aa3e67da7c03c6acc3ec7e1ca579a7f645220f4\n"
            "License: CC BY-NC 4.0; https://creativecommons.org/licenses/by-nc/4.0/\n"
            "The complete upstream license is retained as LICENCE.txt.\n"
            "Tabler Icons retain their upstream MIT notice.\n"
            "Modifications: AcTweeteR-specific search/runtime and watched-state\n"
            "integration, a profile-specific refresh route with an AcTweeteR\n"
            "result callback, and PVR sync after successful profile refresh.\n"
            "The AcTweeteR provider runtime also exposes typed collections,\n"
            "bounded provider-backed expansion rows, and persistent series-change\n"
            "status properties; these remain derived from the active provider\n"
            "profile and stable provider IDs.\n"
            "The distributed ListItem metadata bridge is limited to Kodi's\n"
            "playback tags and script.trakt's supported ID window property;\n"
            "it adds no OAuth, scrobbler or XStream resume database.\n"
            "The exact patch set is tracked in\n"
            "AcTweeteR's private source repository. No upstream license or\n"
            "copyright notice has been removed. This is not an upstream-endorsed\n"
            "build. Sharing/adaptation is limited by the non-commercial license.\n"
            "Strict Trakt recommendation filtering requires exact provider TMDb IDs; "
            "unmatched results are omitted. The recommendation integration is "
            "context-patched and syntax-validated before distribution.\n"
            "The local search index reconciliation uses one prior-row scan per "
            "content type instead of a SELECT per provider item; transaction and "
            "provider-ID semantics are retained.\n"
            "Beta 11 corrects the unified-diff line count for the series-change "
            "provider so the series_recent route is included in the distributed "
            "runtime package.\n"
            "AcTweeteR 1.1.2.11 skips background VOD-info threads and their "
            "per-batch delays when provider metadata is off or already cached, "
            "but preserves cold-cache prefetch and full provider art.\n"
            f"AcTweeteR distribution revision: {distribution_version}; upstream remains 1.1.2.\n"
            "The Kodi add-on version is advanced solely to deliver these documented\n"
            "changes through the native repository updater.\n"
            "Testing-only build 1.1.2.14 adds deferred idle-service construction of a\n"
            "rebuildable SQLite byte-offset index for movie catalog, recent and\n"
            "cached-ranked widgets; missing indexes immediately use the legacy route.\n"
            "The privacy-safe performance trace is opt-in and disabled by default.\n"
            "The index change leaves provider, artwork, playback and menu behavior\n"
            "unchanged.\n"
        )
        (root / "ACTWEETER_MODIFICATIONS.txt").write_text(notice, encoding="utf-8")
        # A changed payload must not replace the same published Kodi version.
        # Preserve source provenance while allowing a native repository update.
        manifest = ET.parse(root / "addon.xml").getroot()
        manifest.set("version", distribution_version)
        (root / "addon.xml").write_bytes(ET.tostring(
            manifest, encoding="utf-8", xml_declaration=True) + b"\n")

        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=9) as archive:
            for path in sorted(item for item in root.rglob("*")
                                if item.is_file() and should_package(item)):
                relative = path.relative_to(root).as_posix()
                info = zipfile.ZipInfo(f"{UPSTREAM_ROOT}/{relative}", FIXED_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                archive.writestr(info, path.read_bytes(),
                                 compress_type=zipfile.ZIP_DEFLATED,
                                 compresslevel=9)

    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError("built XStream ZIP CRC failed")
        for relative, expected_hash in data.get("local_runtime_sha256", {}).items():
            member = f"{UPSTREAM_ROOT}/{relative}"
            if member not in archive.namelist():
                raise ValueError(f"patched runtime file missing from ZIP: {relative}")
            actual_hash = hashlib.sha256(archive.read(member)).hexdigest()
            if actual_hash != expected_hash:
                raise ValueError(f"patched runtime hash mismatch: {relative}")
        validate_python_archive(archive)
        if f"{UPSTREAM_ROOT}/ACTWEETER_MODIFICATIONS.txt" not in archive.namelist():
            raise ValueError("modification attribution missing")
        diagnostics_member = f"{UPSTREAM_ROOT}/resources/lib/performance_diagnostics.py"
        if diagnostics_member not in archive.namelist():
            raise ValueError("performance diagnostics module missing")
        catalog_index_member = f"{UPSTREAM_ROOT}/resources/lib/provider_catalog_index.py"
        if catalog_index_member not in archive.namelist():
            raise ValueError("provider catalog index module missing")
        settings = ET.fromstring(archive.read(f"{UPSTREAM_ROOT}/resources/settings.xml"))
        diagnostic_setting = settings.find(".//setting[@id='performance_diagnostics_enabled']")
        if diagnostic_setting is None or diagnostic_setting.get("default") != "false":
            raise ValueError("diagnostics must be disabled by default")
        patched = archive.read(f"{UPSTREAM_ROOT}/resources/lib/addon.py")
        if b"actweeter_refresh_profile" not in patched:
            raise ValueError("AcTweeteR profile refresh route was not applied")
        routes = archive.read(f"{UPSTREAM_ROOT}/resources/lib/tmdb_routes.py")
        if (b"_filter_provider_trakt_recommendations" not in routes
                or b"filter_provider=False" not in routes):
            raise ValueError("strict provider-filtered Trakt recommendation route missing")
        premium_routes = archive.read(f"{UPSTREAM_ROOT}/resources/lib/premium_routes.py")
        if (b"g['series_changes'].record_catalog" not in premium_routes
                or b"if stype == 'series' and items and host and user and password:" not in premium_routes):
            raise ValueError("premium series catalog baseline hook missing")
        if (b"indexed_movie_page" not in premium_routes
                or b"index.query.duration" not in premium_routes):
            raise ValueError("indexed movie catalog routes missing")
        playback_metadata = f"{UPSTREAM_ROOT}/resources/lib/trakt_playback_metadata.py"
        if playback_metadata not in archive.namelist():
            raise ValueError("script.trakt playback metadata bridge missing")
        metadata_source = archive.read(playback_metadata)
        if (b"script.trakt.ids" not in metadata_source
                or b"setMediaType(\"movie\"" not in metadata_source
                or b"setTvShowTitle" not in metadata_source
                or b"setUniqueIDs" not in metadata_source):
            raise ValueError("Kodi playback metadata bridge is incomplete")
        series_changes = f"{UPSTREAM_ROOT}/resources/lib/series_changes.py"
        series_tree = ast.parse(archive.read(series_changes), filename=series_changes)
        if not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and node.name == "recent" for node in series_tree.body):
            raise ValueError("series_changes.recent route provider is missing")
    return {"upstream_sha256": actual, "candidate_sha256": sha256(output),
            "version": str(data["distribution_version"]), "file": output.name}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.upstream_zip, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
