"""Kodi-native profile policy parsing; never reads or returns lock codes."""

from __future__ import annotations

import xml.etree.ElementTree as ET


LOCK_FLAGS = (
    "locksettings", "lockaddonmanager", "lockfiles", "lockmusic",
    "lockpictures", "lockprograms", "lockvideo",
)


def parse_profiles(xml_bytes: bytes) -> list[dict[str, object]]:
    """Return only non-secret profile identity and restriction fields."""
    root = ET.fromstring(xml_bytes)
    result = []
    for node in root.findall("profile"):
        # Kodi 21 stores profile fields as child elements (not attributes).
        # Attribute support remains for the small legacy fixtures used by
        # earlier AcTweeteR tests.
        name = node.findtext("name") or node.get("name")
        if name is None:
            continue
        def field_text(key: str, default: str = "false") -> str:
            return (node.findtext(key) or node.get(key) or default).strip().lower()

        fields = {}
        for key in LOCK_FLAGS:
            value = field_text(key)
            try:
                fields[key] = int(value) > 0
            except ValueError:
                fields[key] = value in ("true", "yes", "on")
        try:
            lockmode = int(field_text("lockmode", "0"))
        except ValueError:
            lockmode = 0
        directory = node.findtext("directory") or node.get("directory") or ""
        profile_id = node.findtext("id") or node.get("id") or ""
        result.append({
            "id": profile_id,
            "name": name,
            "directory": directory,
            "is_master": profile_id == "0" or not directory.strip() or
                         directory.strip().casefold() == "special://masterprofile/" or
                         name.casefold() in ("master user", "master"),
            "lockmode": lockmode,
            "locks": fields,
        })
    return result


def consumer_lock_status(profile: dict[str, object]) -> bool:
    """Kodi-native lock must exist and protect settings/add-on administration."""
    if profile.get("is_master") or int(profile.get("lockmode", 0)) == 0:
        return False
    locks = profile.get("locks") or {}
    return bool(locks.get("locksettings") and locks.get("lockaddonmanager"))
