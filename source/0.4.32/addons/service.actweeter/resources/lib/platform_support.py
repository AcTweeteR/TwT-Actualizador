"""Kodi platform identification shared by installation diagnostics."""

import platform
import sys

PLATFORM_CONDITIONS = (
    ("tvos", "System.Platform.TVOS"),
    ("android", "System.Platform.Android"),
    ("macos", "System.Platform.OSX"),
    ("windows", "System.Platform.Windows"),
    ("linux", "System.Platform.Linux"),
)

SUPPORTED_KODI_PLATFORMS = tuple(name for name, _ in PLATFORM_CONDITIONS)


def detect_platform(is_visible):
    """Map Kodi conditions to a canonical platform without implying runtime QA."""
    # Embedded Darwin Python can identify Apple TV as OSX; hardware takes priority.
    if sys.platform == "tvos" or platform.machine().casefold().startswith("appletv"):
        return "tvos"
    for name, condition in PLATFORM_CONDITIONS:
        try:
            if is_visible(condition):
                return name
        except Exception:
            continue
    return "unknown"


def configure_rivulet(is_visible, addon_factory):
    """Keep Rivulet's external-server client on tvOS without child-process retries."""
    if detect_platform(is_visible) != "tvos":
        return "unchanged"
    try:
        addon = addon_factory("plugin.video.rivulet")
    except RuntimeError:
        return "not_installed"
    if addon.getSetting("server_enable").casefold() == "false":
        return "already_external_only"
    # This switch controls only the embedded process, not server_url or account data.
    addon.setSetting("server_enable", "false")
    return "external_only"
