"""Kodi plugin-source entry point for authenticated remote diagnostics."""

from __future__ import annotations

import datetime
import json
import os
import re
import sqlite3
import sys
import urllib.parse
import xml.etree.ElementTree as ET

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

from diagnostics import encode_report_chunks, report_payload
from interface_layout import interface_report, backup_interface, prepare_interface
from platform_support import detect_platform
from slyguy_bridge_install import install as install_preview_bridge, rollback as rollback_preview_bridge


def _rpc(method, params=None):
    request = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        request["params"] = params
    try:
        response = json.loads(xbmc.executeJSONRPC(json.dumps(request)))
    except Exception:
        return {"error": {"code": None}}
    return response if isinstance(response, dict) else {"error": {"code": None}}


def _xstream_profiles():
    try:
        addon = xbmcaddon.Addon("plugin.video.xstream-pro")
        version = addon.getAddonInfo("version")
    except Exception:
        return []
    if version != "1.1.2":
        return [{"profile": 1, "enabled": False, "endpoint_present": False,
                 "username_present": False, "password_present": False}]
    output = []
    for number in range(1, 11):
        prefix = "profile_%d_" % number
        try:
            enabled = addon.getSetting(prefix + "enabled").strip().lower() == "true"
            endpoint = addon.getSetting(prefix + "xtream_url")
            username = addon.getSetting(prefix + "xtream_username")
            password = addon.getSetting(prefix + "xtream_password")
        except Exception:
            continue
        if enabled or endpoint or username or password:
            output.append({
                "profile": number, "enabled": enabled,
                "endpoint_present": bool(endpoint),
                "username_present": bool(username),
                "password_present": bool(password),
            })
    return output


def _read_log_tail():
    """Read only Kodi's own log tail in-process; never export the raw file."""
    try:
        path = xbmcvfs.translatePath("special://logpath/kodi.log")
        handle = xbmcvfs.File(path)
        try:
            size = handle.size()
            handle.seek(max(0, size - 1024 * 1024), 0)
            data = handle.read()
        finally:
            handle.close()
        if isinstance(data, bytes):
            return data.decode("utf-8", "replace")[-MAX_LOG_TAIL_CHARS:]
        return str(data)[-MAX_LOG_TAIL_CHARS:]
    except Exception:
        return ""


MAX_LOG_TAIL_CHARS = 1024 * 1024


def _addon_xml(path):
    try:
        file = xbmcvfs.File(path.rstrip("/\\") + "/addon.xml")
        try:
            raw = file.read()
        finally:
            file.close()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", "replace")
        root = ET.fromstring(raw)
    except Exception:
        return {}
    addon_id = root.get("id", "")
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,160}", addon_id):
        return {}
    requires = root.find("requires")
    dependencies = []
    if requires is not None:
        for imported in requires.findall("import"):
            dep_id = imported.get("addon", "")
            if re.fullmatch(r"[A-Za-z0-9._-]{1,160}", dep_id):
                dependencies.append({
                    "addonid": dep_id,
                    "version": imported.get("version", ""),
                    "optional": imported.get("optional", "false").lower() == "true",
                })
    metadata = root.find("extension[@point='xbmc.addon.metadata']")
    license_text = metadata.findtext("license", default="") if metadata is not None else ""
    platform_text = metadata.findtext("platform", default="all") if metadata is not None else "all"
    provider = root.get("provider-name", "")
    return {"addonid": addon_id, "license": license_text[:160],
            "platform": platform_text[:80], "provider": provider[:120],
            "xml_dependencies": dependencies}


def _origins():
    """Read install origins from Kodi's add-on DB only; no profile settings."""
    database_dir = xbmcvfs.translatePath("special://database")
    try:
        names, _ = xbmcvfs.listdir(database_dir)
    except Exception:
        return {}
    candidates = sorted((name for name in names
                         if re.fullmatch(r"Addons[0-9]+\.db", name)), reverse=True)
    if not candidates:
        return {}
    path = os.path.join(database_dir, candidates[0])
    try:
        uri = "file:" + urllib.parse.quote(path, safe="/:\\") + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=2)
        try:
            rows = connection.execute("SELECT addonID, origin FROM installed").fetchall()
        finally:
            connection.close()
        return {addon_id: origin for addon_id, origin in rows
                if isinstance(addon_id, str) and isinstance(origin, str)}
    except Exception:
        return {}


def _addon_inventory():
    response = _rpc("Addons.GetAddons", {
        "type": "unknown", "enabled": "all", "installed": True,
        "properties": ["name", "version", "enabled", "broken", "dependencies", "path"],
        "limits": {"start": 0, "end": 1000},
    })
    addons = response.get("result", {}).get("addons", []) if "error" not in response else []
    origins = _origins()
    rows = []
    for addon in addons if isinstance(addons, list) else []:
        if not isinstance(addon, dict):
            continue
        row = dict(addon)
        row.update(_addon_xml(str(addon.get("path", ""))))
        row["source"] = origins.get(addon.get("addonid", ""), "")
        rows.append(row)
    return rows


def _pvr_snapshot():
    methods = {}
    properties = _rpc("PVR.GetProperties", {"properties": ["available", "scanning"]})
    if "error" in properties:
        methods["PVR.GetProperties"] = properties
    else:
        result = properties.get("result", {})
        methods["PVR.GetProperties"] = {
            "available": result.get("available") is True,
            "scanning": result.get("scanning") is True,
        }
    clients = _rpc("PVR.GetClients")
    if "error" in clients:
        methods["PVR.GetClients"] = clients
    else:
        records = clients.get("result", {}).get("clients", [])
        methods["PVR.GetClients"] = {"client_count": len(records)
            if isinstance(records, list) else 0}
    groups = _rpc("PVR.GetChannelGroups", {"channeltype": "tv"})
    if "error" in groups:
        methods["PVR.GetChannelGroups"] = groups
    else:
        records = groups.get("result", {}).get("channelgroups", [])
        methods["PVR.GetChannelGroups"] = {"channel_group_count": len(records)
            if isinstance(records, list) else 0}
    return methods


def build_report():
    platform = detect_platform(xbmc.getCondVisibility)
    return report_payload(
        kodi_version=xbmc.getInfoLabel("System.BuildVersion"),
        platform=platform,
        addons=_addon_inventory(),
        xstream_profiles=_xstream_profiles(),
        pvr_methods=_pvr_snapshot(),
        log_text=_read_log_tail(),
        captured_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )


def serve(handle, report=None):
    report = report if report is not None else build_report()
    labels = encode_report_chunks(report)
    root_url = "plugin://service.actweeter/?action=diagnostic_report"
    for index, label in enumerate(labels, 1):
        item = xbmcgui.ListItem(label=label)
        xbmcplugin.addDirectoryItem(
            handle, root_url + "&part=%d" % index, item, isFolder=False)
    xbmcplugin.endOfDirectory(handle, succeeded=True, updateListing=False,
                               cacheToDisc=False)


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    try:
        handle = int(argv[1])
    except (IndexError, TypeError, ValueError):
        return
    query = argv[2] if len(argv) > 2 else ""
    params = urllib.parse.parse_qs(query.lstrip("?"), keep_blank_values=True)
    if params.get('action') == ['rollback_preview_bridge']:
        status=rollback_preview_bridge(xbmc,xbmcaddon.Addon,xbmcvfs)
        report=interface_report(xbmc,xbmcaddon.Addon,xbmcvfs)
        report['preview_bridge_status']=status
        serve(handle,report)
        return
    if params.get('action') == ['activate_preview_bridge']:
        status=install_preview_bridge(xbmc,xbmcaddon.Addon,xbmcvfs,xbmcgui.Dialog(),
                                      consent=params.get('consent')==['1'])
        report=interface_report(xbmc,xbmcaddon.Addon,xbmcvfs)
        report['preview_bridge_status']=status
        serve(handle,report)
        return
    if params.get('action') == ['backup_interface']:
        backup_interface(xbmcaddon.Addon, xbmcvfs)
        serve(handle, interface_report(xbmc, xbmcaddon.Addon, xbmcvfs))
        return
    if params.get('action') == ['prepare_interface']:
        status=prepare_interface(xbmc,xbmcaddon.Addon,xbmcvfs,xbmcgui,xbmcgui.Dialog())
        report=interface_report(xbmc,xbmcaddon.Addon,xbmcvfs)
        report['preparation_status']=status
        serve(handle,report)
        return
    if params.get('action') == ['interface_report']:
        serve(handle, interface_report(xbmc, xbmcaddon.Addon, xbmcvfs))
        return
    if params.get("action") != ["diagnostic_report"]:
        xbmcplugin.endOfDirectory(handle, succeeded=False, cacheToDisc=False)
        return
    serve(handle)


if __name__ == "__main__":
    main()
