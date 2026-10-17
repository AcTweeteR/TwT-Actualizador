"""Kodi 21 offline bridge that enables AcTweeteR's first Consumer service.

Kodi must be fully stopped. This narrowly versioned adapter changes only the
profile-local installed.enabled bit for service.actweeter; Kodi APIs handle
all later add-on activation once the service is running in that profile.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from profile_policy import parse_profiles
from profile_sync import profile_sync_targets


KODI_ADDONS_DB_VERSION = 33
BOOTSTRAP_ADDON = "service.actweeter"


def bootstrap_service(userdata: str | Path, profile_name: str, backup_path: str | Path) -> str:
    """Enable the bootstrap service in one existing non-Master profile.

    The caller is responsible for confirming Kodi is stopped. The DB version,
    tables, profile identity, and exact installed row are verified before the
    transaction; a SQLite backup is written before any mutation.
    """
    root = Path(userdata).resolve()
    profiles_path = root / "profiles.xml"
    profiles = parse_profiles(profiles_path.read_bytes())
    targets = profile_sync_targets(profiles_path.read_bytes(), root)
    matches = [(p, t) for p, t in zip(profiles, targets)
               if str(p["name"]).casefold() == profile_name.casefold()]
    if len(matches) != 1:
        raise ValueError("target profile must resolve uniquely")
    record, target = matches[0]
    if record["is_master"] or not target.get("root"):
        raise ValueError("bootstrap target must be a contained non-Master profile")

    db_path = Path(str(target["root"])) / "Database" / "Addons33.db"
    if not db_path.is_file():
        raise FileNotFoundError("profile-local Kodi 21 Add-ons DB is absent")
    backup = Path(backup_path)
    backup.parent.mkdir(parents=True, exist_ok=True)
    if backup.resolve() == db_path.resolve():
        raise ValueError("backup must not overwrite the profile Add-ons DB")

    conn = sqlite3.connect(str(db_path), timeout=5)
    try:
        version = conn.execute("SELECT idVersion FROM version").fetchone()
        if not version or int(version[0]) != KODI_ADDONS_DB_VERSION:
            raise ValueError("unsupported Kodi Add-ons DB schema version")
        installed_cols = {row[1] for row in conn.execute("PRAGMA table_info(installed)")}
        required_cols = {"addonID", "enabled", "disabledReason"}
        if not required_cols.issubset(installed_cols):
            raise ValueError("unexpected Kodi installed-addons schema")
        row = conn.execute(
            "SELECT enabled FROM installed WHERE addonID=?", (BOOTSTRAP_ADDON,)
        ).fetchone()
        if row is None:
            raise ValueError("AcTweeteR bootstrap service is not installed in Kodi")
        if bool(row[0]):
            return "already_enabled"
        if backup.exists():
            raise FileExistsError("refusing to overwrite bootstrap DB backup")

        backup_conn = sqlite3.connect(str(backup))
        try:
            conn.backup(backup_conn)
        finally:
            backup_conn.close()
        with conn:
            changed = conn.execute(
                "UPDATE installed SET enabled=1, disabledReason=0 WHERE addonID=? AND enabled=0",
                (BOOTSTRAP_ADDON,),
            ).rowcount
        if changed != 1:
            raise RuntimeError("bootstrap update did not affect exactly one add-on")
        return "enabled"
    finally:
        conn.close()
