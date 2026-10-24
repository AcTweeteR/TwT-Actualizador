"""Refresh stale Testing metadata and observe Kodi's native auto installer.

Only public Testing metadata is fetched here. Kodi owns package downloads,
dependency resolution, transactions, origin rules and installation progress.
"""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time
from urllib.parse import quote
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from addon_update_policy import COMPONENTS, _rpc, installation_state
from catalog_refresh import _operation_guard
from interface_layout import atomic_write, load_state

FEED = "https://actweeter.github.io/TwT-Actualizador/testing/repo/"
REPOSITORY = "repository.actweeter.testing"


def version_key(value):
    # Own release versions use numeric components plus an optional ~betaN.
    match = re.fullmatch(r"(\d+(?:\.\d+){1,7})(?:~beta(\d+))?", value)
    if not match:
        raise ValueError("unsupported AcTweeteR version")
    parts = tuple(int(part) for part in match[1].split("."))
    return parts + (0,) * (8 - len(parts)), match[2] is None, int(match[2] or 0)


def published():
    def read(url, limit):
        with urlopen(url, timeout=8) as response:
            value = response.read(limit + 1)
        if len(value) > limit:
            raise ValueError("Testing metadata too large")
        return value
    checksum = read(FEED + "addons.xml.md5", 128).decode("ascii").strip()
    data = read(FEED + "addons.xml", 1024 * 1024)
    if not re.fullmatch(r"[0-9a-f]{32}", checksum) or hashlib.md5(data).hexdigest() != checksum:
        raise ValueError("Testing checksum mismatch")
    root = ET.fromstring(data)
    rows = {node.get("id"): node for node in root if node.get("id") in COMPONENTS}
    if set(rows) != set(COMPONENTS):
        raise ValueError("Testing component missing")
    versions = {identity: node.get("version", "") for identity, node in rows.items()}
    for identity, version in versions.items():
        version_key(version)
        # A propagated index is insufficient when its package is still absent.
        with urlopen(Request(
                FEED + identity + "/" + identity + "-" + quote(version) + ".zip",
                method="HEAD"), timeout=8) as response:
            if response.status != 200:
                raise OSError("Testing package unavailable")
    return checksum, versions


def local_metadata(vfs):
    folder = Path(vfs.translatePath("special://database"))
    names = [path for path in folder.glob("Addons*.db") if re.fullmatch(r"Addons\d+\.db", path.name)]
    path = max(names, key=lambda path: int(path.stem[6:]))
    with closing(sqlite3.connect("file:" + quote(str(path), safe="/:") + "?mode=ro", uri=True)) as db:
        row = db.execute("SELECT checksum FROM repo WHERE addonID=?", (REPOSITORY,)).fetchone()
        versions = dict(db.execute(
            "SELECT a.addonID,a.version FROM addons a JOIN addonlinkrepo l ON l.idAddon=a.id "
            "JOIN repo r ON r.id=l.idRepo WHERE r.addonID=?", (REPOSITORY,)))
    return (row[0] if row else ""), versions


def check(kodi, addon, vfs, *, notify=None, fetch=published, timeout=120, clock=time.time):
    """One bounded operation, serialized across Kodi Python interpreters."""
    path = Path(vfs.translatePath(addon.getAddonInfo("profile"))) / "testing_updates.json"
    with _operation_guard(path):
        previous = load_state(path)
        if clock() - previous.get("started", 0) < timeout:
            return "BUSY"
        started = clock()
        state = {"started": started}

        def status(value):
            if state.get("status") == value:
                return value
            state.update(status=value, updated=clock())
            atomic_write(path, json.dumps(state, sort_keys=True).encode())
            kodi.log("[AcTweeteR] TESTING_UPDATE status=" + value, kodi.LOGINFO)
            if notify:
                notify(value)
            return value

        origins = installation_state(vfs)
        if not origins or any(origins.get(identity, {}).get("origin") != REPOSITORY for identity in COMPONENTS):
            return status("OTHER_CHANNEL")
        if kodi.getCondVisibility("Player.HasMedia"):
            return status("PLAYER_ACTIVE")
        try:
            status("CHECKING_FEED")
            for attempt in range(2):
                try:
                    checksum, expected = fetch()
                    break
                except (OSError, ValueError, ET.ParseError):
                    if attempt or kodi.Monitor().waitForAbort(2):
                        return status("FEED_UNAVAILABLE")
            state["expected"] = expected
            installed = lambda: {identity: _rpc(kodi, "Addons.GetAddonDetails", addonid=identity,
                properties=["version"]).get("addon", {}).get("version", "0.0") for identity in COMPONENTS}
            current = installed()
            needed = {identity: version for identity, version in expected.items()
                      if version_key(current[identity]) < version_key(version)}
            if not needed:
                return status("CURRENT")
            blocked = [identity for identity in needed if origins[identity]["blocked"]]
            if blocked:
                state["blocked"] = blocked
                return status("INDIVIDUAL_UPDATE_BLOCKED")
            if _rpc(kodi, "Settings.GetSettingValue", setting="general.addonupdates").get("value") != 0:
                return status("NATIVE_CONFIRMATION_REQUIRED")
            local_checksum, visible = local_metadata(vfs)
            if not local_checksum.startswith(checksum) or any(visible.get(k) != v for k, v in expected.items()):
                status("UPDATING_INDEX")
            else:
                status("REQUESTING_UPDATE")
            # Also request the native resolver when metadata is already current.
            # The supported builtin is asynchronous, even with wait=True.
            kodi.executebuiltin("UpdateAddonRepos", False)
            monitor = kodi.Monitor()
            while clock() - started < timeout:
                current = installed()
                if all(version_key(current[k]) >= version_key(v) for k, v in needed.items()):
                    return status("INSTALLED")
                _, visible = local_metadata(vfs)
                status("WAITING_INSTALL" if all(visible.get(k) == v for k, v in needed.items())
                       else "WAITING_VERSION")
                if monitor.waitForAbort(2):
                    return status("ABORTED")
            return status("INSTALL_TIMEOUT" if state.get("status") == "WAITING_INSTALL" else "INDEX_TIMEOUT")
        except (OSError, ValueError, RuntimeError, sqlite3.Error, ET.ParseError) as exc:
            state["error_type"] = type(exc).__name__
            return status("ERROR")
