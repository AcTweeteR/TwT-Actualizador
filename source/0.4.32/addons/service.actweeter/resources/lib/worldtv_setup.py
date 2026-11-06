"""Conservative first-run and upgrade configuration of independent WorldTV."""
from __future__ import annotations

PLAYLIST = "https://iptv-org.github.io/iptv/index.country.m3u"
EPG = "https://raw.githubusercontent.com/teleonline/listas/main/epg.xml.gz"
ADDON_ID = "plugin.video.launcherm3u"


def configure(addon_factory):
    """Configure only an empty/WorldTV source. Never change an unrelated playlist."""
    try:
        addon = addon_factory(ADDON_ID)
    except (RuntimeError, ImportError, Exception):
        return "not_installed"
    try:
        configured = (addon.getSetting("m3u_url") or "").strip()
        if configured and configured != PLAYLIST:
            return "custom_source_preserved"
        if not configured:
            addon.setSetting("m3u_url", PLAYLIST)
        addon.setSetting("m3u_type", "1")
        existing_epg = (addon.getSetting("epg_url") or "").strip()
        if not existing_epg:
            addon.setSetting("epg_url", EPG)
            addon.setSetting("epg_type", "1")
            addon.setSetting("epg_enabled", "true")
        # Prevent an M3U url-tvg header from replacing our explicitly chosen EPG.
        if not existing_epg or existing_epg == EPG:
            addon.setSetting("auto_url_tvg", "false")
        return "configured" if not configured else "already_configured"
    except (OSError, RuntimeError, ValueError) as exc:
        return "settings_error:" + type(exc).__name__
