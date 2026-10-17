"""In-Kodi, read-only diagnostics and explicit export for Kodi 21.

This entry point uses Kodi's local Python, info-label and VFS APIs only. It
does not call JSON-RPC, open a listener, upload data, or return setting values.
"""

from __future__ import annotations

import datetime
import json
import os

from diagnostics import relevant_log_lines
from module_catalog import MODULES, all_addons, addon_state
from dependency_graph import inspect_graph
from addon_metadata import installed_metadata
from platform_support import detect_platform

MAX_LOG_BYTES = 1024 * 1024


def _platform(xbmc):
    return detect_platform(xbmc.getCondVisibility)


def _read_log(vfs):
    try:
        path = vfs.translatePath("special://logpath/kodi.log")
        handle = vfs.File(path)
        try:
            size = handle.size()
            handle.seek(max(0, size - MAX_LOG_BYTES), 0)
            value = handle.read()
        finally:
            handle.close()
        return value.decode("utf-8", "replace") if isinstance(value, bytes) else str(value)
    except Exception:
        return ""


def _addon_rows(xbmc, xbmcaddon, vfs):
    platform = _platform(xbmc)
    rows = []
    for addon_id, descriptor in all_addons().items():
        version = installed_metadata(xbmcaddon, vfs, addon_id)["version"]
        try:
            enabled = bool(xbmc.getCondVisibility("System.AddonIsEnabled(%s)" % addon_id))
        except Exception:
            enabled = False
        rows.append(addon_state(descriptor, installed_version=version,
                                enabled=enabled, platform=platform))
    return rows


def _xstream_presence(xbmcaddon):
    profiles = []
    try:
        addon = xbmcaddon.Addon("plugin.video.xstream-pro")
    except Exception:
        return {"installed": False, "profiles": []}
    for number in range(1, 11):
        prefix = "profile_%d_" % number
        try:
            enabled = addon.getSetting(prefix + "enabled").strip().lower() == "true"
            endpoint = bool(addon.getSetting(prefix + "xtream_url"))
            username = bool(addon.getSetting(prefix + "xtream_username"))
            password = bool(addon.getSetting(prefix + "xtream_password"))
        except Exception:
            continue
        if enabled or endpoint or username or password:
            profiles.append({"profile": number, "enabled": enabled,
                             "endpoint_present": endpoint,
                             "username_present": username,
                             "password_present": password})
    return {"installed": True, "profiles": profiles}


def build_local_report(xbmc, xbmcaddon, vfs, *, captured_at=None):
    """Gather only allowlisted state; no JSON-RPC or secret values."""
    platform = _platform(xbmc)
    try:
        pvr = {
            "client_enabled": bool(xbmc.getCondVisibility("System.HasPVRAddon")),
            "tv_channels": bool(xbmc.getCondVisibility("PVR.HasTVChannels")),
            "radio_channels": bool(xbmc.getCondVisibility("PVR.HasRadioChannels")),
            "backend_channel_count": xbmc.getInfoLabel("PVR.BackendChannels") or "unknown",
            "current_programme_has_epg": bool(xbmc.getCondVisibility("VideoPlayer.HasEpg")),
        }
    except Exception:
        pvr = {"state": "UNAVAILABLE"}
    errors = relevant_log_lines(_read_log(vfs), limit=80)
    # Keep log excerpts useful for installation failures while refusing to
    # export unrelated user activity or provider/network details.
    errors = [line for line in errors if any(token in line.casefold() for token in (
        "slyguy", "dependency", "installaddon", "addoninstall", "failed to install",
        "failed to satisfy", "service.actweeter", "pvr", "xstream"))]
    kodi_version = xbmc.getInfoLabel("System.BuildVersion") or "unknown"
    module_rows = []
    for module in MODULES:
        row = {key: value for key, value in module.items() if key != "addons"}
        row["addons"] = [dict(addon) for addon in module.get("addons", ())]
        module_rows.append(row)
    def manifest(addon_id):
        try:
            path = installed_metadata(xbmcaddon, vfs, addon_id)["path"]
            if not path:
                return None
            handle = vfs.File(os.path.join(path, "addon.xml"))
            try:
                return handle.read()
            finally:
                handle.close()
        except Exception:
            return None

    def probe(addon_id):
        try:
            version = installed_metadata(xbmcaddon, vfs, addon_id)["version"]
            return version, bool(xbmc.getCondVisibility("System.AddonIsEnabled(%s)" % addon_id))
        except Exception:
            return "", False

    graph = inspect_graph(((key, value["minimum"]) for key, value in all_addons().items()),
                          manifest, probe)
    return {
        "schema": 1,
        "captured_at": captured_at or datetime.datetime.now(
            datetime.timezone.utc).isoformat(),
        "kodi_version": str(kodi_version)[:80],
        "platform": platform,
        "modules": module_rows,
        "addons": _addon_rows(xbmc, xbmcaddon, vfs),
        "dependency_graph": list(graph),
        "pvr": pvr,
        "xstream": _xstream_presence(xbmcaddon),
        "kodi_errors": {"sanitized": True, "lines": errors},
        "limitations": {
            "available_addon_versions": "Kodi does not expose repository candidate versions via local Python without JSON-RPC; Kodi log evidence is shown when present.",
            "epg": "The current-programme EPG flag is not a global EPG inventory.",
            "runtime": "Installed/enabled state is not proof of playback or provider operation.",
        },
    }


def format_report(report):
    lines = ["Kodi %s · %s" % (report.get("kodi_version", "unknown"),
                               report.get("platform", "unknown")), ""]
    states = {item.get("id"): item for item in report.get("addons", [])}
    for module in report.get("modules", []):
        lines.append("[%s] %s%s" % (module["id"], module["name"],
                                   " (obligatorio)" if module.get("required") else ""))
        for descriptor in module.get("addons", ()):
            addon = states.get(descriptor["id"], {})
            lines.append("  %s: requiere %s; instalada=%s; estado=%s; disponible=%s" % (
                descriptor["id"], ">=" + (descriptor["minimum"] or "sin mínimo"),
                addon.get("installed_version") or "no", addon.get("install_state", "desconocido"),
                "no consultada por Kodi local"))
        lines.append("")
    pvr = report.get("pvr", {})
    lines.extend(("PVR: cliente habilitado=%s; canales TV=%s; canales backend=%s; EPG del programa actual=%s" % (
        pvr.get("client_enabled", "desconocido"), pvr.get("tv_channels", "desconocido"),
        pvr.get("backend_channel_count", "desconocido"),
        pvr.get("current_programme_has_epg", "no evaluable")),))
    xstream = report.get("xstream", {})
    profiles = xstream.get("profiles", [])
    lines.append("XStream: instalado=%s; perfiles con datos=%d" % (
        xstream.get("installed", False), len(profiles)))
    lines.append("No se muestran valores de servidor, usuario ni contraseña.")
    log_lines = report.get("kodi_errors", {}).get("lines", [])
    lines.append("\nDependencias pendientes (addon.xml instalado):")
    unresolved = [item for item in report.get("dependency_graph", ()) if item["status"] != "READY"]
    lines.extend("%s: requiere %s; instalada=%s; %s" % (
        item["id"], item["minimum"] or "sin mínimo", item["installed_version"] or "no", item["status"])
        for item in unresolved)
    if not unresolved:
        lines.append("No se detectaron dependencias pendientes en los manifiestos inspeccionados.")
    lines.append("\nErrores Kodi relevantes (sanitizados):")
    lines.extend(log_lines or ["No se encontraron líneas coincidentes en el fragmento de log leído."])
    lines.append("\nVersiones disponibles: no consultables por la API Python local; no se inventan.")
    lines.append("Catálogo modular y políticas completas: incluidas en el JSON exportado.")
    return "\n".join(lines)


def save_report(report, vfs, root):
    vfs.mkdirs(root)
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(root, "actweeter-diagnostic-%s.json" % timestamp)
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    handle = vfs.File(path, "w")
    try:
        handle.write(payload)
    finally:
        handle.close()
    return path


def run(dialog, xbmc, xbmcaddon, vfs, *, profile_path):
    report = build_local_report(xbmc, xbmcaddon, vfs)
    root = os.path.join(profile_path, "diagnostics")
    saved_path = save_report(report, vfs, root)
    dialog.textviewer("Diagnóstico de instalación AcTweeteR", format_report(report))
    if not dialog.yesno(
            "Exportar informe sanitizado",
            "El informe está guardado en los datos de AcTweeteR. ¿Quieres copiarlo a una carpeta local o de red seleccionada desde Kodi? No contiene valores de credenciales.",
            "Ahora no", "Elegir carpeta"):
        return "SAVED_LOCAL"
    destination = dialog.browse(3, "Carpeta para el informe", "files", "",
                                False, False, "")
    if not destination:
        return "SAVED_LOCAL"
    filename = os.path.basename(saved_path)
    target = os.path.join(destination, filename)
    if vfs.exists(target):
        dialog.ok("Exportación cancelada", "Ya existe un informe con ese nombre en la carpeta seleccionada. El informe local se conserva.")
        return "SAVED_LOCAL"
    if not vfs.copy(saved_path, target):
        dialog.ok("No se pudo exportar", "Kodi no pudo copiar el informe a la carpeta elegida. El archivo local se conserva.")
        return "SAVED_LOCAL"
    dialog.ok("Informe exportado", "El informe sanitizado se copió a la carpeta seleccionada. No se mostrará ni registrará su ruta de red.")
    return "EXPORTED"
