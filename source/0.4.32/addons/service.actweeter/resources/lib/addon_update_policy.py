"""Configure Kodi's native updater with consent; never download or install packages."""
from __future__ import annotations

import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import quote
import xml.etree.ElementTree as ET

from interface_layout import atomic_write, load_state

CHANNELS = {"repository.actweeter.testing": "Testing", "repository.actweeter": "Stable"}
COMPONENTS = ("service.actweeter", "skin.actweeter", "plugin.video.xstream-pro")
AUTO_SETTING = "general.addonupdates"
REPO_SETTING = "addons.updatemode"


def _rpc(kodi, method, **params):
    response = json.loads(kodi.executeJSONRPC(json.dumps(
        dict(jsonrpc="2.0", id=1, method=method, params=params))))
    if not isinstance(response, dict) or "error" in response or "result" not in response:
        raise RuntimeError(method)
    return response.get("result", {})


def installation_state(vfs):
    """Kodi 21.3 has no JSON-RPC origin/update-rule setter or reader. Read only."""
    try:
        folder = Path(vfs.translatePath("special://database"))
        _, names = vfs.listdir(str(folder))
        names = [name for name in names if re.fullmatch(r"Addons[0-9]+\.db", name)]
        name = max(names, key=lambda value: int(value[6:-3]))
        connection = sqlite3.connect("file:" + quote(str(folder / name), safe="/:") + "?mode=ro",
                                     uri=True, timeout=2)
        try:
            origins = dict(connection.execute("SELECT addonID, origin FROM installed"))
            blocked = {row[0] for row in connection.execute("SELECT addonID FROM update_rules")}
        finally:
            connection.close()
        return {identity: dict(origin=origins[identity], blocked=identity in blocked)
                for identity in COMPONENTS if identity in origins}
    except (OSError, ValueError, sqlite3.Error):
        return {}


def _saved_mode(vfs):
    try:
        stream = vfs.File("special://profile/guisettings.xml")
        try:
            root = ET.fromstring(stream.read())
        finally:
            stream.close()
        setting = root.find("setting[@id='general.addonupdates']")
        return int(setting.text) if setting is not None else None
    except (OSError, ValueError, ET.ParseError, TypeError):
        return None


def snapshot(kodi, vfs, expected=""):
    expected = expected if isinstance(expected, str) else ""
    settings = {}
    for setting in (AUTO_SETTING, REPO_SETTING):
        try:
            value = _rpc(kodi, "Settings.GetSettingValue", setting=setting).get("value")
            settings[setting] = value if type(value) is int else None
        except (RuntimeError, ValueError, TypeError):
            settings[setting] = None
    addons = {}
    for identity in (*COMPONENTS, *CHANNELS):
        try:
            details = _rpc(kodi, "Addons.GetAddonDetails", addonid=identity,
                           properties=["enabled", "version"]).get("addon", {})
            addons[identity] = details if isinstance(details, dict) else {}
        except (RuntimeError, ValueError, TypeError):
            addons[identity] = {}
    installed = installation_state(vfs)
    origins = {row["origin"] for row in installed.values() if row["origin"] in CHANNELS}
    if expected not in CHANNELS:
        expected = installed.get("service.actweeter", {}).get("origin", "")
        if expected not in CHANNELS:
            expected = next(iter(origins)) if len(origins) == 1 else ""
    problems = []
    if settings[AUTO_SETTING] != 0:
        problems.append("Actualización automática global desactivada o no verificable.")
    if expected not in CHANNELS:
        problems.append("Canal no confirmado: selecciona Testing o Stable en este asistente.")
    elif addons[expected].get("enabled") is not True:
        problems.append("Repositorio %s ausente o deshabilitado." % CHANNELS[expected])
    for identity in COMPONENTS:
        row = installed.get(identity)
        if not row or not row.get("origin"):
            problems.append(identity + ": origen no verificable; instalar desde el canal elegido.")
        elif expected and row["origin"] != expected:
            problems.append(identity + ": origen distinto del canal elegido.")
        if row and row["blocked"]:
            problems.append(identity + ": actualización individual bloqueada en Kodi.")
        if addons[identity].get("enabled") is not True:
            problems.append(identity + ": ausente o deshabilitado.")
    if settings[AUTO_SETTING] == 0 and _saved_mode(vfs) != 0:
        problems.append("Modo automático activo, pero guardado en disco pendiente de verificar tras cerrar Kodi normalmente.")
    return dict(settings=settings, expected=expected, addons=addons,
                installed=installed, problems=problems)


def _state_path(addon, vfs):
    return Path(vfs.translatePath(addon.getAddonInfo("profile"))) / "update_policy.json"


def _record(path, state, report, *, save_channel=False):
    versions = [report["addons"][identity].get("version", "") for identity in COMPONENTS]
    state = dict(state, **load_state(path))
    state.update(versions=versions, problems=report["problems"])
    if save_channel:
        state["expected"] = report["expected"]
    atomic_write(path, json.dumps(state, ensure_ascii=False, sort_keys=True).encode())


def configure(kodi, addon, vfs, dialog):
    path = _state_path(addon, vfs)
    state = load_state(path)
    report = snapshot(kodi, vfs, state.get("expected", ""))
    if not report["expected"]:
        choices = list(CHANNELS)
        selected = dialog.select("Canal de actualizaciones AcTweeteR", list(CHANNELS.values()))
        if selected in range(len(choices)):
            state["expected"] = choices[selected]
    if report["settings"][AUTO_SETTING] in (1, 2) and dialog.yesno(
            "Actualizaciones automáticas de Kodi",
            "¿Autorizar la instalación automática de actualizaciones? Es un ajuste global: "
            "también puede actualizar otros addons habilitados desde sus repositorios. "
            "No cambiaremos tu canal ni la opción «Cualquier repositorio».",
            nolabel="Conservar preferencia", yeslabel="Autorizar"):
        try:
            if _rpc(kodi, "Settings.SetSettingValue", setting=AUTO_SETTING, value=0) is not True:
                raise RuntimeError("setting rejected")
        except (RuntimeError, ValueError, TypeError):
            dialog.ok("Actualizaciones pendientes", "Kodi no confirmó el cambio. Se volverá a comprobar; no se anuncian actualizaciones garantizadas.")
    report = snapshot(kodi, vfs, state.get("expected", report["expected"]))
    try:
        _record(path, state, report, save_channel=True)
    except OSError:
        report["problems"].append("No se pudo guardar la revisión en AcTweeteR; vuelve a intentarlo.")
    lines = ["Canal elegido: " + CHANNELS.get(report["expected"], "no confirmado"),
             "Modo automático: " + ("activo" if report["settings"][AUTO_SETTING] == 0 else "no confirmado"),
             "Actualizar addons oficiales desde: " +
             {0: "repositorios oficiales de Kodi", 1: "cualquier repositorio"}.get(report["settings"][REPO_SETTING], "no verificable"),
             "«Actualizar addons oficiales desde» se conserva: no es necesario cambiarlo para AcTweeteR."]
    lines += [identity + ": " + (report["installed"].get(identity, {}).get("origin") or "sin origen confirmado")
              for identity in COMPONENTS]
    lines += report["problems"] or ["No se detectan bloqueos de configuración. Kodi comprobará versiones compatibles según su programación nativa."]
    lines += ["El canal no se cambia escribiendo en la base de datos. Si hay un origen incorrecto, usa Versiones en la ficha del addon y elige el repositorio correspondiente.",
              "La instalación automática real se verifica aparte; un ajuste correcto no demuestra una descarga."]
    dialog.textviewer("Actualizaciones de AcTweeteR", "\n".join(lines))
    return report


def review(kodi, addon, vfs, dialog):
    """One warning per changed version/problem; never a consent dialog at startup."""
    path = _state_path(addon, vfs)
    state = load_state(path)
    report = snapshot(kodi, vfs, state.get("expected", ""))
    versions = [report["addons"][identity].get("version", "") for identity in COMPONENTS]
    if report["problems"] and (versions != state.get("versions") or report["problems"] != state.get("problems")):
        dialog.notification("Actualizaciones de AcTweeteR",
                            "Revisión pendiente: abre Configuración AcTweeteR → Actualizaciones y canal.", time=8000)
    _record(path, state, report)
    return report
