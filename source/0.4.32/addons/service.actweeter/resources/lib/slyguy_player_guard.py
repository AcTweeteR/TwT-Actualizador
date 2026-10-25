"""Reversible local fix for the verified SlyGuy 0.87.3 terminal-time race.

No SlyGuy source is distributed. Unknown or user-modified code is preserved.
"""
import hashlib
import json
from pathlib import Path

from interface_layout import atomic_write

ORIGINAL_HASH = "2de0733e0e3c8fd5e8e835de7aab57a40f7e6820cd1f24d5160a625fbc1d6c15"
BEFORE = b"    def _save_stop_time(self):\n        # getTime() still reports"
AFTER = (b"    def _save_stop_time(self):\n"
         b"        # AcTweeteR: Kodi logs getTime() failures before Python catches them.\n"
         b"        if not self.isPlaying():\n"
         b"            log.info('AcTweeteR SLYGUY_TERMINAL_TIME inactive_skipped')\n"
         b"            return\n"
         b"        # getTime() still reports")


def payload(source):
    if hashlib.sha256(source).hexdigest() != ORIGINAL_HASH or source.count(BEFORE) != 1:
        raise ValueError("unrecognized SlyGuy player source")
    result = source.replace(BEFORE, AFTER, 1)
    compile(result, "slyguy-player-guard", "exec")
    return result


def install(kodi, addon_factory, vfs):
    """Apply once while idle; the next normal startup loads the guarded module."""
    if kodi.getCondVisibility("Player.HasMedia"):
        return "PLAYER_ACTIVE"
    addon = addon_factory("script.module.slyguy")
    addon_version = addon.getAddonInfo("version")
    # Validate the actual source signature, not a frozen release number.
    target = Path(vfs.translatePath(addon.getAddonInfo("path"))) / "resources/lib/player.py"
    if target.is_symlink():
        return "USER_CHANGES_PRESERVED"
    source = target.read_bytes()
    root = Path(vfs.translatePath(addon_factory("service.actweeter").getAddonInfo("profile")))
    backup = root / "slyguy_player_guard" / "player.py.original"
    manifest = backup.with_name("manifest.json")
    if backup.exists():
        original = backup.read_bytes()
        expected = payload(original)
        if source == expected:
            return "CURRENT"
        if source != original:
            return "USER_CHANGES_PRESERVED"
    else:
        expected = payload(source)
        atomic_write(backup, source)
        if backup.read_bytes() != source:
            raise OSError("SlyGuy guard backup verification failed")
    # Only this known source is replaced, after its backup has been verified.
    atomic_write(target, expected)
    if target.read_bytes() != expected:
        atomic_write(target, backup.read_bytes())
        raise OSError("SlyGuy guard verification failed")
    atomic_write(manifest, json.dumps({
        "version": addon_version, "original_sha256": ORIGINAL_HASH,
        "patched_sha256": hashlib.sha256(expected).hexdigest(),
        "status": "RESTART_REQUIRED",
    }, sort_keys=True).encode())
    return "RESTART_REQUIRED"
