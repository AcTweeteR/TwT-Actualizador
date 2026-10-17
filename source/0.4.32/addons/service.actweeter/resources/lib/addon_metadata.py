"""Read installed metadata, including disabled add-ons, without settings/RPC."""

import os
import re
from xml.etree import ElementTree as ET


def installed_metadata(xbmcaddon, vfs, addon_id):
    if not isinstance(addon_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", addon_id):
        return {"version": "", "path": ""}
    try:
        addon = xbmcaddon.Addon(addon_id)
        version = addon.getAddonInfo("version") or ""
        path = addon.getAddonInfo("path") or ""
        if version:
            return {"version": version, "path": path}
    except Exception:
        pass
    # Kodi 21's Python Addon constructor rejects disabled IDs. The installed
    # manifest remains in Kodi's own add-on roots; use VFS, never addon_data.
    for root in ("special://home/addons", "special://xbmc/addons"):
        path = root + "/" + addon_id
        try:
            handle = vfs.File(path + "/addon.xml")
            try:
                content = handle.read()
            finally:
                handle.close()
            if len(content) > 256 * 1024:
                continue
            manifest = ET.fromstring(content)
            version = manifest.get("version", "")
            if manifest.tag == "addon" and manifest.get("id") == addon_id and version:
                return {"version": version, "path": vfs.translatePath(path)}
        except Exception:
            continue
    return {"version": "", "path": ""}
