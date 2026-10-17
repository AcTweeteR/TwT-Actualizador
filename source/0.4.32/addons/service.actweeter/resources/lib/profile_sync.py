"""Safe, manifest-driven profile structure propagation.

Only AcTweeteR/Skin Shortcuts DATA XML is eligible. State databases, settings,
secrets, caches, playback state, and arbitrary userdata paths are never copied.
"""

from __future__ import annotations

import os
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from profile_policy import parse_profiles


SENSITIVE = re.compile(
    r"(?:password|passwd|username|token|client[_-]?secret|api[_-]?key|"
    r"authorization|/Users/|/Volumes/|\\Users\\|\b[A-Za-z]:[\\/]"
    r"|(?:smb|file)://)", re.IGNORECASE,
)


def _safe_relative(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ValueError("manifest paths must be relative and contained")
    return path


def _validate_data_file(path: Path, content: bytes) -> None:
    if path.suffix.lower() != ".xml" or not path.name.endswith(".DATA.xml"):
        raise ValueError("only Skin Shortcuts DATA XML is eligible for sync")
    if not re.fullmatch(r"skin\.(?:actweeter|bingie)-[A-Za-z0-9_-]+\.DATA\.xml", path.name):
        raise ValueError("file name is not an approved AcTweeteR structural document")
    text = content.decode("utf-8")
    if SENSITIVE.search(text):
        raise ValueError("sensitive value or non-portable path detected")
    ET.fromstring(content)


def profile_sync_targets(profiles_xml: bytes, master_root: str | Path) -> list[dict[str, object]]:
    """Resolve Kodi's native profile records to contained local roots.

    Kodi stores ``<name>``, ``<id>`` and ``<directory>`` as child elements;
    non-master directory values are relative to the master userdata root.
    Unsafe or non-local custom directories fail closed with an empty root.
    """
    base = Path(master_root).resolve()
    targets: list[dict[str, object]] = []
    for record in parse_profiles(profiles_xml):
        result: dict[str, object] = {
            "name": record["name"],
            "directory": record["directory"],
            "is_master": record["is_master"],
        }
        if record["is_master"]:
            result["root"] = str(base)
            targets.append(result)
            continue
        raw_directory = str(record["directory"] or "")
        relative = Path(raw_directory)
        if (not raw_directory or relative.is_absolute() or ".." in relative.parts
                or "\\" in raw_directory or ":" in raw_directory
                or raw_directory.casefold().startswith("special://")):
            result["root"] = ""
        else:
            candidate = (base / relative).resolve()
            result["root"] = str(candidate) if candidate.is_relative_to(base) else ""
        targets.append(result)
    return targets


def sync_entry(master_root: str | Path, consumer_root: str | Path,
               entry: dict[str, str], *, managed_sha256: str | None = None) -> tuple[bool, str]:
    """Safely reconcile one structural document.

    A consumer file is seeded only when absent. Later updates are allowed only
    while its bytes still match the last version AcTweeteR wrote. Local edits
    are treated as consumer-owned and are never overwritten.
    """
    source_rel = _safe_relative(entry["source"])
    target_rel = _safe_relative(entry["target"])
    master = Path(master_root).resolve()
    consumer = Path(consumer_root).resolve()
    source = (master / source_rel).resolve()
    target = consumer / target_rel
    if not source.is_relative_to(master) or not target.resolve().is_relative_to(consumer):
        raise ValueError("manifest path escapes its profile root")
    if source_rel.parts[:2] != ("addon_data", "script.skinshortcuts"):
        raise ValueError("source must be a Skin Shortcuts profile DATA document")
    if target_rel.parts[:2] != ("addon_data", "script.skinshortcuts"):
        raise ValueError("target must be a Skin Shortcuts profile DATA document")

    content = source.read_bytes()
    _validate_data_file(source, content)
    source_hash = hashlib.sha256(content).hexdigest()
    if target.is_file() and target.read_bytes() == content:
        return False, source_hash
    if target.exists():
        current_hash = hashlib.sha256(target.read_bytes()).hexdigest()
        if managed_sha256 is None or current_hash != managed_sha256:
            return False, ""

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".actweeter-tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return True, source_hash


def sync_profiles(master_root: str | Path, profiles: list[dict[str, str]],
                  entries: list[dict[str, str]], *, state_path: str | Path) -> dict[str, int]:
    """Reconcile allowlisted files without overwriting consumer-owned edits."""
    result = {"profiles": 0, "files_updated": 0, "conflicts": 0, "errors": 0}
    state_file = Path(state_path)
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
        if not isinstance(state, dict) or state.get("schema_version") != 1:
            state = {"schema_version": 1, "managed": {}}
    except (OSError, ValueError, TypeError):
        state = {"schema_version": 1, "managed": {}}
    if not isinstance(state.get("managed"), dict):
        state["managed"] = {}
    dirty = False
    conflicts = state.get("conflicts")
    if not isinstance(conflicts, dict):
        conflicts = {}
        state["conflicts"] = conflicts
    for profile in profiles:
        if profile.get("is_master"):
            continue
        result["profiles"] += 1
        root = profile.get("root")
        if not root:
            result["errors"] += len(entries) or 1
            continue
        for entry in entries:
            target_key = "/".join((str(profile.get("directory", "")), entry.get("target", "")))
            try:
                managed_hash = state["managed"].get(target_key)
                updated, source_hash = sync_entry(
                    master_root, root, entry, managed_sha256=managed_hash
                )
                result["files_updated"] += int(updated)
                if source_hash:
                    if state["managed"].get(target_key) != source_hash:
                        state["managed"][target_key] = source_hash
                        dirty = True
                    if target_key in conflicts:
                        del conflicts[target_key]
                        dirty = True
                elif Path(root, entry["target"]).exists():
                    result["conflicts"] += 1
                    target_path = Path(root, entry["target"])
                    conflict = {
                        "master_sha256": hashlib.sha256(
                            (Path(master_root) / entry["source"]).read_bytes()
                        ).hexdigest(),
                        "consumer_sha256": hashlib.sha256(target_path.read_bytes()).hexdigest(),
                    }
                    if conflicts.get(target_key) != conflict:
                        conflicts[target_key] = conflict
                        dirty = True
                elif target_key in conflicts:
                    del conflicts[target_key]
                    dirty = True
            except (OSError, ValueError, KeyError, ET.ParseError):
                result["errors"] += 1
    if dirty:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = state_file.with_name(state_file.name + ".actweeter-tmp")
        try:
            with temporary.open("w", encoding="utf-8") as stream:
                json.dump(state, stream, sort_keys=True, separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, state_file)
        finally:
            if temporary.exists():
                temporary.unlink()
    return result
