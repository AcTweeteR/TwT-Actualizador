"""Kodi-native onboarding and on-demand service diagnostics.

Credentials are collected in masked input and persist only in the owning
add-on's native settings. Reports contain states, never credential values.
AcTweeteR detecta la presencia local de autorización; no almacena ni comparte
tokens de cuentas externas.
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
import time
from contextlib import contextmanager
from urllib.parse import parse_qs, urlparse

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON = xbmcaddon.Addon()
ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo("path"))
LIB_PATH = os.path.join(ADDON_PATH, "resources", "lib")
if LIB_PATH not in sys.path:
    sys.path.insert(0, LIB_PATH)

from first_run import (
    INTRO_OPTIONS,
    OPTIONAL_ADDON_SOURCES,
    OPTIONAL_ADDONS,
    REQUIRED_ADDON_IDS,
    REQUIRED_EXTERNAL_ADDON_MINIMUMS,
    REQUIRED_REPAIR_SOURCES,
    SLYGUY_INSTALL_SEQUENCE,
    addon_version_satisfies,
    claim_process_session,
    completion_blockers,
    has_xtream_configuration,
    home_diagnostic_snapshot,
    intro_mode_for_selection,
    load_state,
    mark_completed,
    mark_catalog_reconciled,
    mark_component_offer_seen,
    mark_deferred,
    mark_setup_check,
    mark_started,
    mark_step,
    optional_addon_action,
    poll_runtime_state,
    release_process_session,
    save_state,
    service_rows,
    should_offer_component_completion,
    should_offer_first_run,
    should_offer_first_run_in_process,
    tvos_xstream_dependency_status,
)
from xstream_setup import (
    SUPPORTED_XSTREAM_VERSIONS,
    SetupError,
    parse_xtream_input,
    prepare_https_endpoint,
    save_native_profile,
    validate_xtream_credentials,
)
from module_catalog import installation_plan
from platform_support import detect_platform
from dependency_graph import inspect_graph
from pvr_binding import profile_is_bound
from interface_layout import (LAYOUT_VERSION, interface_migration_due,
                              prepare_interface, backup_interface)
from factory_defaults import preferred_factory_language
from catalog_refresh import (begin_refresh, finish_refresh, new_request_id,
                             refresh_trace)
from plugin_query_trace import begin as begin_plugin_trace, emit as emit_plugin_trace
from interaction_trace import arm as arm_interaction_trace
from trakt_integration import (AUTH_ACTION as TRAKT_AUTH_ACTION,
                              AUTH_WINDOW as TRAKT_AUTH_WINDOW,
                              configure_fresh_defaults,
                              mark_trakt_status, supports_device_authorization)

SETTINGS_ADDONS = {
    "xstream": "plugin.video.xstream-pro",
    "pvr": "pvr.iptvsimple",
    "slyguy": "slyguy.trailers",
    "youtube": "plugin.video.youtube",
    "trakt": "script.trakt",
}
XSTREAM_TRAKT_AUTH_ACTION = (
    "RunPlugin(plugin://plugin.video.xstream-pro/?mode=xstream_trakt_authorize)"
)
METADATA_ADDONS = ("plugin.video.tmdb.bingie.helper",
                   "plugin.video.themoviedb.helper")
_HTTP_AUTHORIZED_BASE = ""  # One explicitly authorized endpoint, this invocation only.


def _state_path():
    root = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
    xbmcvfs.mkdirs(root)
    return os.path.join(root, "setup_state.json")


def _read_state():
    return load_state(_state_path())


def _write_state(state):
    save_state(_state_path(), state)


def _intro_session_path():
    profile = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
    xbmcvfs.mkdirs(profile)
    return os.path.join(profile, "intro_session.json")


def _first_run_session_path():
    profile = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
    xbmcvfs.mkdirs(profile)
    return os.path.join(profile, "first_run_session.json")


def _intro_blocks_first_run(*, resume_from_mask=False):
    """Do not put onboarding over AcTweeteR's modal startup animation."""
    window = xbmcgui.Window(10000)
    if window.getProperty("AcTweeteRStartupIntroActive") == "1":
        return True
    if xbmc.getInfoLabel("Window(Home).Property(AcTweeteRIntroPlayback)") == "1":
        return True
    # A RunScript launched by the mask's onunload can run while Kodi is still
    # dispatching that same unload event; explicit ownership flags are the
    # reliable gate for this resume path, not a transient Window.IsActive read.
    if resume_from_mask:
        return False
    return bool(xbmc.getCondVisibility("Window.IsActive(1103)"))


def _defer_first_run_until_intro_closes():
    xbmcgui.Window(10000).setProperty("AcTweeteRFirstRunPending", "1")
    xbmc.log("[AcTweeteR] FIRST_RUN_FLOW status=deferred reason=startup_intro",
             xbmc.LOGINFO)


def _apply_factory_language():
    """Select Spanish only while Kodi still marks its factory English default."""
    try:
        profile = xbmcvfs.translatePath("special://profile/guisettings.xml")
        current = _jsonrpc("Settings.GetSettingValue", {"setting": "locale.language"})
        current_value = current.get("value") if isinstance(current, dict) else None
        with open(profile, "rb") as stream:
            factory_settings = stream.read()
        target = preferred_factory_language(factory_settings, current_value)
        if target is None:
            return "PRESERVED"
        if not _addon_installed("resource.language.es_es"):
            return "LANGUAGE_RESOURCE_MISSING"
        changed = _jsonrpc("Settings.SetSettingValue", {
            "setting": "locale.language", "value": target})
        verified = _jsonrpc("Settings.GetSettingValue", {"setting": "locale.language"})
        if (changed is True and isinstance(verified, dict)
                and verified.get("value") == target):
            xbmc.log("[AcTweeteR] FACTORY_LANGUAGE status=applied language=es_es",
                     xbmc.LOGINFO)
            return "APPLIED"
        return "NOT_APPLIED"
    except Exception as exc:
        xbmc.log("[AcTweeteR] FACTORY_LANGUAGE status=error type=%s" %
                 type(exc).__name__, xbmc.LOGWARNING)
        return "ERROR"


def _addon_installed(addon_id):
    return bool(xbmc.getCondVisibility("System.HasAddon(%s)" % addon_id))


def _addon_enabled(addon_id):
    return bool(xbmc.getCondVisibility("System.AddonIsEnabled(%s)" % addon_id))


def _addon_ready(addon_id):
    return _addon_installed(addon_id) and _addon_enabled(addon_id)


def _set_xstream_profile_url(addon, setting_id, new_url):
    """Update only XStream's verified URL setting and confirm the write."""
    previous = addon.getSetting(setting_id)
    try:
        addon.setSetting(setting_id, new_url)
        if addon.getSetting(setting_id) == new_url:
            return True
    except Exception as exc:  # noqa: BLE001 - settings API errors must not expose values.
        xbmc.log("[AcTweeteR] HTTPS_MIGRATION status=write_error type=%s" %
                 type(exc).__name__, xbmc.LOGWARNING)
    try:
        addon.setSetting(setting_id, previous)
        restored = addon.getSetting(setting_id) == previous
    except Exception:  # noqa: BLE001 - report only a safe failure state.
        restored = False
    xbmc.log("[AcTweeteR] HTTPS_MIGRATION status=unconfirmed rollback=%s" %
             ("ok" if restored else "failed"), xbmc.LOGWARNING)
    return False


def _set_addon_enabled(addon_id, enabled=True):
    """Toggle an installed add-on through Kodi's JSON-RPC API and verify it."""
    response = json.loads(xbmc.executeJSONRPC(json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "Addons.SetAddonEnabled",
        "params": {"addonid": addon_id, "enabled": bool(enabled)},
    })))
    return "error" not in response and _addon_enabled(addon_id) is bool(enabled)


def _addon_requirement_ready(addon_id):
    if not _addon_ready(addon_id):
        return False
    minimum = REQUIRED_EXTERNAL_ADDON_MINIMUMS.get(addon_id)
    return minimum is None or addon_version_satisfies(_addon_version(addon_id), minimum)


def _wait_for_addon_ready(addon_id, timeout=120, *, required=False,
                          minimum_version=None):
    """Yield to Kodi while waiting for its asynchronous package transaction."""
    import time

    monitor = xbmc.Monitor()
    stop_at = time.monotonic() + timeout
    while time.monotonic() < stop_at:
        version_ok = (not minimum_version or addon_version_satisfies(
            _addon_version(addon_id), minimum_version))
        if ((_addon_requirement_ready(addon_id) if required else _addon_ready(addon_id))
                and version_ok):
            return True
        if monitor.waitForAbort(0.5):
            return False
    version_ok = (not minimum_version or addon_version_satisfies(
        _addon_version(addon_id), minimum_version))
    return ((_addon_requirement_ready(addon_id) if required else _addon_ready(addon_id))
            and version_ok)


def _mandatory_addons_ready():
    return all(_addon_requirement_ready(item["id"])
               for item in installation_plan(_platform()) if item["supported"]) and all(
                   item["supported"] for item in installation_plan(_platform())) and all(
                       item["status"] == "READY" for item in _installed_dependency_graph()) and _xstream_refresh_supported()


def _xstream_refresh_supported():
    """Version alone does not establish the AcTweeteR integration route."""
    try:
        addon = xbmcaddon.Addon("plugin.video.xstream-pro")
        if addon.getAddonInfo("version") not in SUPPORTED_XSTREAM_VERSIONS:
            return False
        handle = xbmcvfs.File(os.path.join(addon.getAddonInfo("path"), "resources", "lib", "addon.py"))
        try:
            source = handle.read()
        finally:
            handle.close()
        if isinstance(source, bytes):
            source = source.decode("utf-8")
        return bool(re.search(r'''elif\s+mode\s*==\s*["']actweeter_refresh_profile["']\s*:''', source))
    except Exception:
        return False


def _catalog_refresh_state_path():
    profile = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
    xbmcvfs.mkdirs(profile)
    return os.path.join(profile, "catalog_refresh_state.json")


def _dispatch_plugin_query(url, source, *, wait=False):
    """Trace an AcTweeteR-owned plug-in dispatch without logging its URI."""
    trace = begin_plugin_trace(
        url, source,
        log=lambda message: xbmc.log(message, xbmc.LOGINFO))
    try:
        xbmc.executebuiltin("RunPlugin(%s)" % url, bool(wait))
    except Exception as exc:
        emit_plugin_trace(
            trace, "error", error_type=type(exc).__name__,
            log=lambda message: xbmc.log(message, xbmc.LOGWARNING))
        raise
    emit_plugin_trace(
        trace, "finished" if wait else "dispatched",
        log=lambda message: xbmc.log(message, xbmc.LOGINFO))
    return trace


def _xstream_catalog_callback_supported():
    """Require the exact result bridge before exposing a completion claim."""
    if not _xstream_refresh_supported():
        return False
    try:
        addon = xbmcaddon.Addon("plugin.video.xstream-pro")
        handle = xbmcvfs.File(os.path.join(
            addon.getAddonInfo("path"), "resources", "lib", "addon.py"))
        try:
            source = handle.read()
        finally:
            handle.close()
        if isinstance(source, bytes):
            source = source.decode("utf-8")
        return ('actweeter_callback' in source
                and 'catalog_refresh_result' in source
                and 'RunScript(service.actweeter,catalog_refresh_result' in source)
    except Exception:
        return False


def _catalog_refresh_start(dialog):
    addon_id = "plugin.video.xstream-pro"
    if (not _addon_requirement_ready(addon_id)
            or not _xstream_catalog_callback_supported()):
        dialog.notification("AcTweeteR", "XStream Pro no ofrece la integración de actualización requerida.",
                            xbmcgui.NOTIFICATION_WARNING, 6000)
        return
    request_id = None
    state_path = None
    try:
        xstream = xbmcaddon.Addon(addon_id)
        active = xstream.getSetting("active_pvr_profile") or "Profile 1"
        digits = "".join(char for char in active if char.isdigit())
        profile_number = int(digits or "1")
        if not 1 <= profile_number <= 10:
            raise ValueError("invalid active profile")
        request_id = new_request_id()
        state_path = _catalog_refresh_state_path()
        url = ("plugin://plugin.video.xstream-pro/?mode=actweeter_refresh_profile"
               "&pnum=%d&actweeter_callback=%s" % (profile_number, request_id))
        trace = begin_plugin_trace(
            url, "setup.catalog_refresh", correlation_id=request_id,
            log=lambda message: xbmc.log(message, xbmc.LOGINFO))
        if not begin_refresh(state_path, request_id, profile_number, trace=trace):
            dialog.notification("AcTweeteR", "Ya hay una actualización del catálogo en curso.",
                                xbmcgui.NOTIFICATION_INFO, 5000)
            return
        xbmc.executebuiltin("RunPlugin(%s)" % url, False)
        emit_plugin_trace(trace, "dispatched",
                          log=lambda message: xbmc.log(message, xbmc.LOGINFO))
    except Exception as exc:  # Suppress URL/profile details in diagnostics.
        if "trace" in locals():
            emit_plugin_trace(trace, "error", error_type=type(exc).__name__,
                              log=lambda message: xbmc.log(message, xbmc.LOGWARNING))
        if request_id and state_path:
            finish_refresh(state_path, request_id, False)
        xbmc.log("[AcTweeteR] CATALOG_REFRESH status=dispatch_error type=%s" %
                 type(exc).__name__, xbmc.LOGWARNING)
        dialog.notification("AcTweeteR", "No se pudo iniciar la actualización del catálogo.",
                            xbmcgui.NOTIFICATION_ERROR, 6000)
        return
    xbmc.log("[AcTweeteR] CATALOG_REFRESH status=dispatched profile=%d" %
             profile_number, xbmc.LOGINFO)
    dialog.notification("AcTweeteR", "Actualizando películas y series…",
                        xbmcgui.NOTIFICATION_INFO, 5000)


def _catalog_refresh_result(args, dialog):
    if len(args) < 2:
        return
    request_id, outcome = args[0], args[1].casefold()
    if outcome not in ("success", "error"):
        return
    trace = refresh_trace(_catalog_refresh_state_path(), request_id)
    accepted = finish_refresh(_catalog_refresh_state_path(), request_id,
                              outcome == "success")
    if not accepted:
        xbmc.log("[AcTweeteR] CATALOG_REFRESH status=stale_callback_ignored",
                 xbmc.LOGWARNING)
        return
    if trace:
        emit_plugin_trace(
            trace, "finished" if outcome == "success" else "error",
            error_type="XStreamRefreshError",
            log=lambda message: xbmc.log(
                message, xbmc.LOGINFO if outcome == "success" else xbmc.LOGWARNING))
    if outcome == "success":
        try:
            from interface_layout import refresh_recommendations
            refresh_recommendations(xbmcgui.Window(10000), xbmc.executebuiltin)
        except Exception as exc:
            xbmc.log("[AcTweeteR] RECOMMENDATION_REFRESH status=error type=%s" %
                     type(exc).__name__, xbmc.LOGWARNING)
        dialog.notification("AcTweeteR", "Catálogo actualizado.",
                            xbmcgui.NOTIFICATION_INFO, 5000)
        xbmc.log("[AcTweeteR] CATALOG_REFRESH status=completed", xbmc.LOGINFO)
    else:
        dialog.notification("AcTweeteR", "XStream no pudo actualizar el catálogo. Puedes intentarlo de nuevo.",
                            xbmcgui.NOTIFICATION_ERROR, 7000)
        xbmc.log("[AcTweeteR] CATALOG_REFRESH status=error", xbmc.LOGWARNING)


def _installed_dependency_graph():
    def read_manifest(addon_id):
        try:
            from addon_metadata import installed_metadata
            path = installed_metadata(xbmcaddon, xbmcvfs, addon_id)["path"]
            if not path:
                return None
            handle = xbmcvfs.File(os.path.join(path, "addon.xml"))
            try:
                return handle.read()
            finally:
                handle.close()
        except Exception:
            return None
    return inspect_graph(((item["id"], item["minimum"])
                          for item in installation_plan(_platform())), read_manifest,
                         lambda addon_id: (_addon_version(addon_id) if _addon_installed(addon_id)
                                           else "", _addon_enabled(addon_id)))


def _platform():
    return detect_platform(xbmc.getCondVisibility)


def _addon_version(addon_id):
    """Return only Kodi's addon version metadata; never inspect settings."""
    from addon_metadata import installed_metadata
    return installed_metadata(xbmcaddon, xbmcvfs, addon_id)["version"]


def _tvos_xstream_dependency_status():
    return tvos_xstream_dependency_status(
        _addon_installed("pvr.iptvsimple"),
        _addon_enabled("pvr.iptvsimple"),
        _addon_version("pvr.iptvsimple"),
    )


def _explain_tvos_xstream_dependency(dialog, *, offer_enable=True):
    """Gate XStream until this Kodi app actually exposes a compatible PVR."""
    status = _tvos_xstream_dependency_status()
    if status == "READY":
        return True
    if status == "PVR_DISABLED" and offer_enable:
        result = _request_native_addon_install(
            dialog, "pvr.iptvsimple", "complemento ya integrado en Kodi tvOS",
            required=True)
        if result == "INSTALLED" and _tvos_xstream_dependency_status() == "READY":
            return True
        status = _tvos_xstream_dependency_status()
    messages = {
        "PVR_MISSING": (
            "Esta instalación de Kodi para Apple TV no incluye IPTV Simple. "
            "XStream Pro declara ese complemento como dependencia obligatoria. "
            "Usa una compilación de Kodi tvOS que lo integre y vuelve a intentarlo; "
            "AcTweeteR no descargará ni instalará binarios por su cuenta."),
        "PVR_DISABLED": (
            "IPTV Simple sigue deshabilitado. Habilítalo desde Complementos → "
            "Mis complementos → Clientes PVR y vuelve a intentarlo."),
        "PVR_VERSION_INSUFFICIENT": (
            "La versión instalada de IPTV Simple es anterior a 21.4.0. "
            "XStream Pro no se instalará hasta que Kodi incluya una versión "
            "compatible."),
        "PVR_VERSION_UNKNOWN": (
            "Kodi no permite confirmar la versión de IPTV Simple. Para evitar "
            "una instalación incompleta, XStream Pro queda pendiente."),
    }
    dialog.ok("Requisito de XStream Pro", messages.get(status, messages["PVR_VERSION_UNKNOWN"]))
    return False


def _ensure_repository_enabled(dialog, repository_id):
    """Enable only an already-installed repository, after explicit consent."""
    if not repository_id or _addon_enabled(repository_id):
        return bool(repository_id and _addon_enabled(repository_id))
    if not _addon_installed(repository_id):
        return False
    if not dialog.yesno(
            "Activar repositorio",
            "%s ya está instalado, pero deshabilitado. ¿Quieres habilitarlo para que Kodi pueda resolver el complemento solicitado? No se instalará ningún repositorio nuevo." % repository_id,
            "Ahora no", "Habilitar"):
        return False
    try:
        if not _set_addon_enabled(repository_id, True):
            raise RuntimeError("Kodi did not confirm repository enablement")
    except Exception as exc:
        xbmc.log("[AcTweeteR] REPOSITORY_ENABLE status=error type=%s" %
                 type(exc).__name__, xbmc.LOGWARNING)
    return _addon_enabled(repository_id)


def _is_tvos():
    return bool(xbmc.getCondVisibility("System.Platform.TVOS"))


def _request_native_addon_install(dialog, addon_id, source_id, *, required=True,
                                  consent_granted=False, minimum_version=None):
    """Use Kodi's native resolver and wait for a verified installed state."""
    heading = "Componente obligatorio de AcTweeteR" if required else "Instalar integración opcional"
    role = "dependencia de la skin" if required else "integración adicional"
    if not consent_granted and not dialog.yesno(
            heading,
            "¿Pedir a Kodi que instale %s (%s) desde %s? Kodi gestiona las dependencias y confirmaciones; AcTweeteR no configura credenciales." %
            (addon_id, role, source_id),
            "Ahora no", "Instalar"):
        return "DECLINED"

    attempts = 0
    while attempts < 2:
        try:
            # Kodi's native installer handles dependency resolution, licenses,
            # platform packages, and its own confirmation UI.
            minimum = minimum_version or REQUIRED_EXTERNAL_ADDON_MINIMUMS.get(addon_id)
            update_needed = (_addon_installed(addon_id)
                             and minimum is not None
                             and not addon_version_satisfies(_addon_version(addon_id), minimum))
            if update_needed:
                # Kodi 21.3 InstallModal returns immediately for installed IDs;
                # InstallAddon cannot update them. Use Kodi's native update UI
                # without changing its origin/automatic-update preferences.
                xbmc.executebuiltin("UpdateAddonRepos", True)
                xbmc.executebuiltin("ActivateWindow(addonbrowser,addons://outdated/,return)", False)
                dialog.ok("Actualización necesaria",
                          "Kodi necesita actualizar %s antes de continuar. Confirma la actualización en la pantalla de Kodi y vuelve a pulsar Reparar instalación. Se conservarán sus datos." % addon_id)
                return "UPDATE_REQUIRED"
            if not _addon_installed(addon_id):
                xbmc.executebuiltin("InstallAddon(%s)" % addon_id, True)
            elif not _addon_enabled(addon_id):
                if not _set_addon_enabled(addon_id, True):
                    raise RuntimeError("Kodi did not confirm add-on enablement")
        except Exception as exc:
            xbmc.log("[AcTweeteR] ADDON_INSTALL status=error addon=%s type=%s" %
                     (addon_id, type(exc).__name__), xbmc.LOGWARNING)
        # Kodi's package transaction and dependency prompts are asynchronous
        # relative to the Python built-in call. Never issue a second install
        # while the first transaction may still be running.
        if _wait_for_addon_ready(addon_id, required=required,
                                 minimum_version=minimum_version):
            return "INSTALLED"
        if attempts >= 1:
            return "FAILED"
        if not dialog.yesno(
                "Instalación no confirmada",
                "Kodi no confirma que %s esté instalado y habilitado. Comprueba la conexión, la compatibilidad y el repositorio; ¿quieres volver a intentarlo ahora?" % addon_id,
                "Dejar pendiente", "Reintentar"):
            return "FAILED"
        attempts += 1
    return "FAILED"


def _install_slyguy_stack(dialog, *, open_settings=False, consent_granted=False):
    """Bootstrap the official SlyGuy repository, then resolve its dependency chain with Kodi."""
    already_ready = all(_addon_requirement_ready(addon_id)
                        for addon_id, _minimum, _source in SLYGUY_INSTALL_SEQUENCE)
    if not already_ready and not consent_granted and not dialog.yesno(
            "Preparar SlyGuy Trailers",
            "Kodi instalará repository.slyguy desde el catálogo upstream que AcTweeteR ya consulta; después instalará sus dependencias y Trailers desde repository.slyguy. No se copiarán ZIP de terceros a AcTweeteR. Kodi conservará sus confirmaciones de confianza/licencia y gestionará las actualizaciones oficiales.",
            "Ahora no", "Continuar"):
        return False

    if not _addon_enabled("repository.actweeter"):
        if not _ensure_repository_enabled(dialog, "repository.actweeter"):
            dialog.ok("Fuente AcTweeteR no disponible",
                      "Habilita repository.actweeter y vuelve a intentar la instalación de SlyGuy.")
            return False

    for addon_id, minimum, source_id in SLYGUY_INSTALL_SEQUENCE:
        if source_id != "repository.actweeter" and not _addon_enabled(source_id):
            if _addon_installed(source_id):
                if not _ensure_repository_enabled(dialog, source_id):
                    dialog.ok("Repositorio SlyGuy deshabilitado",
                              "Kodi necesita repository.slyguy habilitado para resolver sus paquetes oficiales.")
                    return False
            else:
                dialog.ok("Cadena SlyGuy incompleta",
                          "No se confirmó repository.slyguy. Kodi no puede consultar todavía los paquetes oficiales de SlyGuy.")
                return False

        outcome = _request_native_addon_install(
            dialog, addon_id, source_id, required=True, consent_granted=True,
            minimum_version=minimum)
        if outcome != "INSTALLED":
            dialog.ok(
                "Instalación SlyGuy pendiente",
                "Kodi no confirmó %s >= %s. No se descargó ni sustituyó ningún ZIP manualmente. Abre Diagnosticar instalación para ver el error de Kodi y vuelve a intentarlo después." %
                (addon_id, minimum))
            return False

        if addon_id == "repository.slyguy":
            # Kodi's supported built-in refreshes all enabled repository feeds.
            xbmc.executebuiltin("UpdateAddonRepos", True)

    if not all(_addon_ready(addon_id) and addon_version_satisfies(
            _addon_version(addon_id), minimum)
            for addon_id, minimum, _source in SLYGUY_INSTALL_SEQUENCE):
        dialog.ok("SlyGuy pendiente", "La cadena oficial no quedó instalada y habilitada en las versiones mínimas. No se marcará como lista.")
        return False

    if open_settings:
        xbmc.executebuiltin("Addon.OpenSettings(slyguy.trailers)", True)
    else:
        dialog.ok("SlyGuy preparado", "Repository SlyGuy, dependencias y Trailers están instalados y habilitados. Esto no demuestra todavía que un tráiler se resuelva o reproduzca en esta plataforma.")
    return True
def _installed_addons():
    installed = {key: _addon_ready(addon_id)
                 for key, addon_id in OPTIONAL_ADDONS.items() if key != "metadata"}
    installed["required"] = _mandatory_addons_ready()
    installed["metadata"] = any(_addon_installed(addon_id)
                                for addon_id in METADATA_ADDONS)
    return installed


def _jsonrpc(method, params=None):
    """Return Kodi JSON-RPC result or None without leaking response data."""
    try:
        payload = {"jsonrpc": "2.0", "id": 1, "method": method}
        if params is not None:
            payload["params"] = params
        response = json.loads(xbmc.executeJSONRPC(json.dumps(payload)))
        if "error" in response:
            return None
        return response.get("result")
    except Exception:  # Kodi JSON-RPC errors are non-fatal and never expose payloads.
        return None


def _xstream_catalog_status():
    """Count provider category entries through Kodi's own plugin directory API."""
    counts = {}
    for kind, mode in (("movies", "movies_menu"), ("series", "series_menu")):
        result = _jsonrpc("Files.GetDirectory", {
            "directory": "plugin://plugin.video.xstream-pro/?mode=%s" % mode,
            "media": "files",
        })
        files = result.get("files") if isinstance(result, dict) else None
        if not isinstance(files, list):
            counts[kind] = None
            continue
        # XStream adds a search folder even with no provider categories. It is
        # not catalog evidence and must never make an empty catalog pass.
        counts[kind] = 0
        for item in files:
            if not isinstance(item, dict):
                continue
            path = urlparse(item.get("file", ""))
            query = parse_qs(path.query)
            if (path.scheme == "plugin" and path.netloc == OPTIONAL_ADDONS["xstream"]
                    and query.get("mode") == ["xtream_streams"]
                    and query.get("type") == ["movie" if kind == "movies" else "series"]
                    and query.get("cat_id", [""])[0]):
                counts[kind] += 1
    return counts


def _pvr_status():
    """Verify Kodi PVR state, channel groups/channels, and whether any EPG exists."""
    properties = _jsonrpc("PVR.GetProperties", {
        "properties": ["available", "scanning"],
    })
    if not isinstance(properties, dict):
        return {"error": True, "available": False, "scanning": False,
                "groups": 0, "channels": 0, "broadcasts": 0,
                "error_stage": "PVR.GetProperties"}

    groups_result = _jsonrpc("PVR.GetChannelGroups", {"channeltype": "tv"})
    if not isinstance(groups_result, dict):
        return {"error": True, "available": bool(properties.get("available")),
                "scanning": bool(properties.get("scanning")), "groups": 0,
                "channels": 0, "broadcasts": 0,
                "error_stage": "PVR.GetChannelGroups"}
    groups = groups_result.get("channelgroups", []) if isinstance(groups_result, dict) else []
    channel_count = 0
    broadcast_count = 0
    # Kodi may return a custom/empty group first. Probe only a bounded prefix,
    # stop as soon as one group contains channels, and keep all IDs transient.
    if isinstance(groups, list):
        for group in groups[:10]:
            group_id = group.get("channelgroupid") if isinstance(group, dict) else None
            if group_id is None:
                continue
            channels_result = _jsonrpc("PVR.GetChannels", {
                "channelgroupid": group_id,
                "limits": {"start": 0, "end": 20000},
            })
            if not isinstance(channels_result, dict):
                return {"error": True, "available": bool(properties.get("available")),
                        "scanning": bool(properties.get("scanning")),
                        "groups": len(groups), "channels": 0, "broadcasts": 0,
                        "error_stage": "PVR.GetChannels"}
            channels = (channels_result.get("channels", [])
                        if isinstance(channels_result, dict) else [])
            if isinstance(channels, list) and channels:
                channel_count = len(channels)
                break

    if channel_count:
        # One small sample suffices to tell whether the guide currently has data;
        # no channel names, IDs, programme titles, or paths are retained.
        channels_result = _jsonrpc("PVR.GetChannels", {
            "channelgroupid": group_id,
            "limits": {"start": 0, "end": 5},
        })
        channels = channels_result.get("channels", []) if isinstance(channels_result, dict) else []
        if isinstance(channels, list):
            for channel in channels[:5]:
                channel_id = channel.get("channelid") if isinstance(channel, dict) else None
                if channel_id is None:
                    continue
                broadcasts_result = _jsonrpc("PVR.GetBroadcasts", {
                    "channelid": channel_id,
                    "limits": {"start": 0, "end": 1},
                })
                broadcasts = (broadcasts_result.get("broadcasts", [])
                              if isinstance(broadcasts_result, dict) else [])
                if isinstance(broadcasts, list):
                    broadcast_count += len(broadcasts)
                if broadcast_count:
                    break
    return {
        "error": False,
        "available": bool(properties.get("available")),
        "scanning": bool(properties.get("scanning")),
        "groups": len(groups) if isinstance(groups, list) else 0,
        "channels": channel_count,
        "broadcasts": broadcast_count,
        "error_stage": None,
    }


def _pvr_ready(status):
    return bool(
        isinstance(status, dict) and not status.get("error")
        and status.get("available") and not status.get("scanning")
        and status.get("groups", 0) > 0 and status.get("channels", 0) > 0
    )


def _wait_for_pvr_ready(timeout=120, interval=2, *, verify_binding=False):
    """Yield to Kodi while its PVR client initializes, until state is observed."""
    monitor = xbmc.Monitor()
    return poll_runtime_state(
        _pvr_status, lambda status: _pvr_ready(status) and (
            not verify_binding or _pvr_profile_binding()), monitor.waitForAbort, time.monotonic,
        timeout=timeout, interval=interval,
    )


def _enable_xstream_pvr_sync(addon):
    """Enable XStream's version-pinned auto-sync setting and verify the write."""
    try:
        if (addon.getSetting("auto_sync_pvr") or "").strip().casefold() == "true":
            return True
        addon.setSetting("auto_sync_pvr", "true")
        return (addon.getSetting("auto_sync_pvr") or "").strip().casefold() == "true"
    except Exception as exc:  # Do not expose add-on settings or exception text.
        xbmc.log("[AcTweeteR] PVR_AUTOCONFIG status=setting_error type=%s" %
                 type(exc).__name__, xbmc.LOGWARNING)
        return False


def _pvr_profile_binding():
    try:
        addon = xbmcaddon.Addon(OPTIONAL_ADDONS["xstream"])
        if addon.getAddonInfo("version") not in SUPPORTED_XSTREAM_VERSIONS:
            return False
        active = addon.getSetting("active_pvr_profile") or "Profile 1"
        match = re.search(r"([0-9]+)$", active)
        number = int(match.group(1)) if match else 1
        return profile_is_bound(xbmcvfs.translatePath(addon.getAddonInfo("profile")), number,
                               xbmcvfs.translatePath("special://profile/addon_data/pvr.iptvsimple"), xbmcvfs)
    except Exception:
        return False


def _configure_pvr_from_xstream(dialog):
    """Ask the AcTweeteR-patched XStream profile route to refresh and sync PVR.

    This deliberately does not copy credentials or write IPTV Simple settings.
    The version-pinned integration route owns generated M3U/XMLTV and preserves
    foreign IPTV Simple instances. Kodi's plugin dispatcher and progress UI
    remain in control; this script polls PVR state separately.
    """
    xstream_id = OPTIONAL_ADDONS["xstream"]
    pvr_id = OPTIONAL_ADDONS["pvr"]
    if not _addon_ready(xstream_id):
        dialog.ok("TV todavía no está preparada",
                  "Instala y habilita XStream Pro antes de preparar los canales.")
        return False
    if not _xstream_refresh_supported():
        dialog.ok("Integración XStream pendiente",
                  "XStream está instalado, pero no ofrece la integración de configuración AcTweeteR. Repara su paquete desde el repositorio AcTweeteR conservando sus datos.")
        return False
    if not _addon_requirement_ready(pvr_id):
        dialog.ok("PVR no disponible",
                  "Kodi no tiene una versión compatible de IPTV Simple. No se modificó ninguna configuración PVR.")
        return False
    status = _pvr_status()
    if _pvr_ready(status) and _pvr_profile_binding():
        return True
    state = _read_state()
    if state.get("setup_checks", {}).get("provider_authentication") != "PASS_RUNTIME":
        dialog.ok("Conecta primero tu proveedor",
                  "La sincronización PVR requiere que AcTweeteR haya validado el perfil de XStream en esta sesión de configuración.")
        return False
    if not dialog.yesno(
            "Preparar TV y canales",
            "AcTweeteR activará la sincronización PVR de XStream si hace falta y actualizará sus propios canales y guía. Kodi actualizará el servicio PVR; las demás instancias IPTV Simple se conservarán. Puedes cambiar la sincronización automática después en XStream. ¿Continuar?",
            nolabel="Ahora no", yeslabel="Preparar TV"):
        return False
    try:
        xstream = xbmcaddon.Addon(xstream_id)
        active = xstream.getSetting("active_pvr_profile") or "Profile 1"
        digits = "".join(char for char in active if char.isdigit())
        profile_number = int(digits or "1")
        if not 1 <= profile_number <= 10:
            raise ValueError("invalid active profile")
        if not _enable_xstream_pvr_sync(xstream):
            dialog.ok("No se pudo activar la sincronización",
                      "XStream no confirmó el ajuste de sincronización PVR. No se inició ningún cambio en IPTV Simple.")
            return False
        query_trace = _dispatch_plugin_query(
            "plugin://plugin.video.xstream-pro/?mode=actweeter_refresh_profile&pnum=%d" % profile_number,
            "setup.pvr_autoconfig", wait=False)
    except Exception as exc:  # Do not expose provider paths or exception text.
        xbmc.log("[AcTweeteR] PVR_AUTOCONFIG status=dispatch_error type=%s" %
                 type(exc).__name__, xbmc.LOGWARNING)
        dialog.ok("No se pudo iniciar la sincronización",
                  "XStream Pro no pudo iniciar la preparación de TV. No se marcará este paso como completado.")
        return False
    outcome, result = _wait_for_pvr_ready(verify_binding=True)
    if outcome == "READY" and _pvr_profile_binding():
        emit_plugin_trace(
            query_trace, "unobserved",
            log=lambda message: xbmc.log(message, xbmc.LOGINFO))
        xbmc.log("[AcTweeteR] PVR_AUTOCONFIG status=verified groups=%d channels=%d epg=%s" %
                 (result["groups"], result["channels"],
                  "available" if result.get("broadcasts", 0) else "not_observed"),
                 xbmc.LOGINFO)
        return True
    emit_plugin_trace(
        query_trace, "cancel_requested" if outcome == "ABORTED" else "unobserved",
        log=lambda message: xbmc.log(message, xbmc.LOGWARNING))
    xbmc.log("[AcTweeteR] PVR_AUTOCONFIG status=%s available=%s scanning=%s groups=%d channels=%d error_stage=%s" %
             (outcome,
              bool(result.get("available")), bool(result.get("scanning")),
              result.get("groups", 0), result.get("channels", 0),
              result.get("error_stage") or "none"), xbmc.LOGWARNING)
    if outcome == "ABORTED":
        heading = "Comprobación PVR interrumpida"
        message = "Kodi está cerrando o canceló la comprobación. No se cambió la configuración; vuelve a comprobar el estado de TV."
    elif result.get("error"):
        heading = "Kodi no pudo consultar PVR"
        message = "La consulta de %s falló. La instalación sigue incompleta; revisa el estado del cliente IPTV Simple en Kodi y vuelve a intentar." % (result.get("error_stage") or "PVR")
    else:
        heading = "TV todavía se está preparando"
        message = "Kodi no confirmó grupos y canales dentro del tiempo de espera. La sincronización no se repetirá automáticamente; cuando termine la carga de PVR, vuelve a comprobar el estado."
    dialog.ok(heading, message)
    return False


def _evaluate_setup_gates(state):
    """Refresh the core install/configuration gates; playback QA stays optional."""
    state = mark_setup_check(
        state, "mandatory_addons",
        "PASS_RUNTIME" if _mandatory_addons_ready() else "FAIL")
    state = mark_setup_check(state, "trailer_addon_ready", "PASS_RUNTIME" if all(
        _addon_requirement_ready(addon_id)
        for addon_id, _minimum, _source in SLYGUY_INSTALL_SEQUENCE) else "FAIL")

    provider_addon = None
    provider_https = False
    provider_ready = state.get("setup_checks", {}).get("provider_authentication") == "PASS_RUNTIME"
    if provider_ready and _addon_ready(OPTIONAL_ADDONS["xstream"]):
        try:
            provider_addon = xbmcaddon.Addon(OPTIONAL_ADDONS["xstream"])
            provider_ready = has_xtream_configuration(provider_addon)
            active = provider_addon.getSetting("active_pvr_profile") or "Profile 1"
            digits = "".join(char for char in active if char.isdigit())
            profile = int(digits or "1")
            base, username, password = parse_xtream_input(
                provider_addon.getSetting("profile_%d_xtream_url" % profile),
                provider_addon.getSetting("profile_%d_xtream_username" % profile),
                provider_addon.getSetting("profile_%d_xtream_password" % profile),
            )
            provider_ready = (provider_ready and bool(username and password)
                              and urlparse(base).scheme in ("http", "https"))
            if provider_ready:
                # A saved PASS is historical evidence. Recheck the active
                # account before committing a new completion decision.
                transport_allowed = (urlparse(base).scheme == "https"
                                     or base == _HTTP_AUTHORIZED_BASE)
                provider_ready = (transport_allowed and validate_xtream_credentials(
                    base, username, password,
                    allow_insecure=base == _HTTP_AUTHORIZED_BASE,
                    user_agent=provider_addon.getSetting("custom_user_agent")) == "AUTHENTICATED")
            provider_https = provider_ready and urlparse(base).scheme == "https"
        except Exception:
            provider_ready = False
    state = mark_setup_check(
        state, "provider_authentication",
        "PASS_RUNTIME" if provider_ready else "FAIL")

    catalog = _xstream_catalog_status() if provider_ready else {"movies": None, "series": None}
    movies_ok = isinstance(catalog.get("movies"), int) and catalog["movies"] > 0
    series_ok = isinstance(catalog.get("series"), int) and catalog["series"] > 0
    state = mark_setup_check(state, "movies_catalog",
                             "PASS_RUNTIME" if movies_ok else "FAIL")
    state = mark_setup_check(state, "series_catalog",
                             "PASS_RUNTIME" if series_ok else "FAIL")

    pvr = _pvr_status() if _addon_ready(OPTIONAL_ADDONS["pvr"]) else {
        "error": True, "available": False, "scanning": False,
        "groups": 0, "channels": 0, "broadcasts": 0,
    }
    tv_ready = _pvr_ready(pvr)
    state = mark_setup_check(state, "live_tv_ready",
                             "PASS_RUNTIME" if tv_ready else "FAIL")
    state = mark_setup_check(state, "pvr_configuration",
                             "PASS_RUNTIME" if tv_ready and _pvr_profile_binding() else "FAIL")
    # Trakt is an independent enhancement, never an IPTV/setup completion gate.
    # Authorization status is informational only: AcTweeteR does not inspect
    # either add-on's private token or infer success from a dismissed dialog.
    # EPG is observed but deliberately non-blocking. Empty data is NOT called
    # “not provided”: that would require provider-specific proof.
    epg_status = "PASS_RUNTIME" if pvr["broadcasts"] > 0 else "NOT_TESTED"
    state = mark_setup_check(state, "epg_ready_or_not_provided", epg_status)
    return state, {"movies": catalog.get("movies"), "series": catalog.get("series"),
                   "pvr": pvr, "https_persisted": provider_https}


def _collect_status():
    installed = _installed_addons()
    configured = None
    if installed.get("xstream"):
        try:
            configured = has_xtream_configuration(xbmcaddon.Addon(OPTIONAL_ADDONS["xstream"]))
        except Exception:
            configured = False
    pvr = _pvr_status() if installed.get("pvr") else None
    return service_rows(installed, pvr=pvr, xstream_configured=configured)


def _show_status(dialog):
    with _setup_progress("Comprobando tus servicios"):
        state, evidence = _evaluate_setup_gates(_read_state())
        _write_state(mark_completed(state))
    checks = state.get("setup_checks", {})
    passed = lambda key: checks.get(key) == "PASS_RUNTIME"
    pvr = evidence["pvr"]
    lines = [
        "Componentes: " + ("preparados" if passed("mandatory_addons") else "pendientes de reparación"),
        "Proveedor: " + ("conexión comprobada" if passed("provider_authentication") else "conexión no confirmada; reintenta sin cambiar tus datos"),
        "Películas: " + ("%d categorías comprobadas" % evidence["movies"] if passed("movies_catalog") else "catálogo pendiente"),
        "Series: " + ("%d categorías comprobadas" % evidence["series"] if passed("series_catalog") else "catálogo pendiente"),
        "Televisión: " + ("%d canales sincronizados" % pvr["channels"] if passed("pvr_configuration") else "sincronización pendiente"),
        "Guía: " + ("programación comprobada" if passed("epg_ready_or_not_provided") else "programación todavía no comprobada"),
        "Tráilers: " + ("componentes preparados" if passed("trailer_addon_ready") else "componentes pendientes"),
        "Trakt: opcional; puedes conectarlo desde los ajustes de sus complementos.",
        "La reproducción se comprueba por separado. El detalle técnico está en Diagnosticar instalación.",
    ]
    dialog.textviewer("Tus servicios AcTweeteR", "\n".join(lines))


@contextmanager
def _setup_progress(message):
    """Show real work, without invented percentages or credential values."""
    factory = getattr(xbmcgui, "DialogProgressBG", None)
    progress = factory() if factory else None
    try:
        if progress:
            progress.create("Preparando AcTweeteR", message)
        yield
    finally:
        if progress:
            progress.close()


def _verify_connected_services(dialog):
    """Continue after authentication; never turn an accepted step into completion."""
    _write_state(mark_step(mark_started(_read_state()), "Configurar y verificar servicios", "IN_PROGRESS"))
    with _setup_progress("Sincronizando televisión y guía"):
        ready = _configure_pvr_from_xstream(dialog)
    if not ready:
        _write_state(mark_step(_read_state(), "Configurar y verificar servicios", "RETURNED"))
        return False
    with _setup_progress("Verificando conexión, películas, series y canales"):
        result = _finish_setup(dialog)
    return result


def _open_settings(dialog, key):
    addon_id = SETTINGS_ADDONS.get(key)
    if not addon_id:
        return
    if key == "slyguy":
        _install_slyguy_stack(dialog, open_settings=True)
        return
    installed = _addon_installed(addon_id)
    enabled = _addon_enabled(addon_id)
    if installed and enabled:
        # Kodi owns each add-on's official configuration UI and secret storage.
        xbmc.executebuiltin("Addon.OpenSettings(%s)" % addon_id, True)
        return

    if key == "xstream" and _is_tvos():
        if not _explain_tvos_xstream_dependency(dialog):
            return

    source_id = OPTIONAL_ADDON_SOURCES.get(key)
    source_enabled = _ensure_repository_enabled(dialog, source_id)
    action = optional_addon_action(
        key, installed, source_enabled, tvos=_is_tvos(), addon_enabled=enabled)
    if action == "ENABLE":
        result = _request_native_addon_install(
            dialog, addon_id, "instalación existente de Kodi")
        if result == "INSTALLED":
            xbmc.executebuiltin("Addon.OpenSettings(%s)" % addon_id, True)
        else:
            dialog.ok("Complemento deshabilitado",
                      "%s sigue deshabilitado. Puedes reintentar más tarde; Home no depende de este servicio." % addon_id)
        return
    if action == "PLATFORM_UNAVAILABLE":
        if key == "xstream":
            dialog.ok(
                "XStream no disponible en tvOS",
                "XStream Pro declara IPTV Simple como dependencia obligatoria. Este Kodi no presenta ahora pvr.iptvsimple instalado y habilitado en una versión compatible; AcTweeteR no descargará binarios ni modificará Kodi.app. Si esta distribución incluye PVR integrado, habilítalo desde la interfaz oficial de Kodi y vuelve a comprobar. La configuración seguirá incompleta mientras falte.")
            return
        dialog.ok(
            "No disponible en tvOS",
            "Este Kodi no presenta pvr.iptvsimple como complemento instalable. AcTweeteR no descargará ni instalará binarios externos; consulta la distribución de Kodi de este dispositivo. La TV/PVR no se verificará como lista, pero puedes seguir usando Kodi."
        )
        return
    if action == "REPOSITORY_REQUIRED":
        if source_id and _addon_installed(source_id):
            dialog.ok("Repositorio deshabilitado",
                      "%s no se habilitó. Puedes activarlo desde Complementos → Mis complementos → Repositorios y volver a intentarlo." % source_id)
            return
        dialog.ok(
            "Repositorio necesario",
            "Kodi no encuentra %s. AcTweeteR necesita su repositorio Kodi 1.0.3 habilitado para resolver esta dependencia sin un ZIP manual. Completa primero la instalación del repositorio AcTweeteR y vuelve a reparar los componentes." % source_id,
        )
        return
    if action != "OFFER_INSTALL":
        dialog.ok("Componente requerido", "No hay una vía de instalación autorizada configurada para este complemento. El asistente seguirá incompleto.")
        return

    result = _request_native_addon_install(
        dialog, addon_id, source_id,
        required=True)
    if result != "INSTALLED":
        dialog.ok(
            "Instalación pendiente",
            ("Has omitido %s. Puedes volver a intentarlo desde este asistente." if result == "DECLINED" else
             "No se confirmó la instalación de %s. La opción sigue disponible para reintentar desde este asistente.") % addon_id,
        )
        return
    dialog.ok(
        "Componente instalado",
        "%s está instalado. La instalación sola no completa la configuración; vuelve al asistente para abrir sus ajustes oficiales y verificar las funciones. AcTweeteR no añade credenciales automáticamente." % addon_id,
    )


def _configure_xstream_provider(dialog):
    """Collect credentials once, validate them, then write only XStream settings."""
    global _HTTP_AUTHORIZED_BASE
    _HTTP_AUTHORIZED_BASE = ""
    addon_id = OPTIONAL_ADDONS["xstream"]
    if not _addon_ready(addon_id):
        _open_settings(dialog, "xstream")
        return False
    if _addon_version(addon_id) not in SUPPORTED_XSTREAM_VERSIONS:
        dialog.ok(
            "XStream Pro no compatible",
            "Esta versión de XStream no coincide con la integración comprobada. Actualiza el componente desde AcTweeteR Repository; tus datos se conservarán.",
        )
        return False
    if not _xstream_refresh_supported():
        dialog.ok("Integración XStream pendiente",
                  "El paquete instalado no permite preparar el contenido automáticamente desde AcTweeteR. Repara XStream desde nuestro repositorio antes de introducir datos; tus ajustes se conservarán.")
        return False
    try:
        addon = xbmcaddon.Addon(addon_id)
    except Exception as exc:  # noqa: BLE001 - avoid surfacing external add-on details.
        xbmc.log(f"[AcTweeteR] XSTREAM_SETUP status=addon_api_error type={type(exc).__name__}",
                 xbmc.LOGWARNING)
        dialog.ok("XStream no disponible", "Kodi no pudo abrir los ajustes del complemento. Reinténtalo desde el asistente.")
        return False
    try:
        already_configured = has_xtream_configuration(addon)
    except Exception:  # noqa: BLE001 - upstream add-on settings API is implementation-specific.
        already_configured = False
    # An earlier successful profile does not authenticate a new attempt.
    _write_state(mark_setup_check(mark_started(_read_state()), "provider_authentication", "NOT_TESTED"))
    if already_configured:
        keep_existing = dialog.yesno(
            "Proveedor IPTV ya configurado",
            "El perfil activo de XStream ya contiene datos. Puedes conservarlo y comprobar la conexión, o cambiar el proveedor. AcTweeteR no mostrará ni copiará los valores existentes.",
            nolabel="Cambiar",
            yeslabel="Conservar")
        if keep_existing:
            try:
                profile_name = addon.getSetting("active_pvr_profile") or "Profile 1"
                digits = "".join(char for char in profile_name if char.isdigit())
                profile_number = int(digits or "1")
                if not 1 <= profile_number <= 10:
                    raise SetupError("PROFILE_UNAVAILABLE")
                prefix = "profile_%d_" % profile_number
                base, username, password = parse_xtream_input(
                    addon.getSetting(prefix + "xtream_url"),
                    addon.getSetting(prefix + "xtream_username"),
                    addon.getSetting(prefix + "xtream_password"),
                )
                if not username or not password:
                    raise SetupError("CREDENTIALS_REQUIRED")
                allow_insecure = False
                if urlparse(base).scheme == "http":
                    transport, secure_base = prepare_https_endpoint(base)
                    if transport == "HTTPS_READY":
                        if not _set_xstream_profile_url(
                                addon, prefix + "xtream_url", secure_base):
                            raise SetupError("XSTREAM_SETTINGS_WRITE_FAILED")
                        base = secure_base
                    elif transport == "HTTP_ONLY":
                        allow_insecure = dialog.yesno(
                            "Proveedor sin HTTPS",
                            "No se encontró un endpoint HTTPS válido. Si continúas, el proveedor recibirá el usuario y la contraseña sin cifrado de transporte. ¿Autorizas esa conexión insegura?",
                            nolabel="Cancelar", yeslabel="Enviar sin cifrar")
                        if not allow_insecure:
                            return False
                    else:
                        raise SetupError(transport)
                status = validate_xtream_credentials(
                    base, username, password, allow_insecure=allow_insecure,
                    user_agent=addon.getSetting("custom_user_agent"))
            except SetupError as exc:
                status = str(exc)
            except Exception as exc:  # noqa: BLE001 - never expose external values.
                xbmc.log("[AcTweeteR] XSTREAM_SETUP status=existing_profile_error type=%s" %
                         type(exc).__name__, xbmc.LOGWARNING)
                status = "SERVER_UNAVAILABLE"
            if status != "AUTHENTICATED":
                messages = {
                    "SERVER_REJECTED": "El servidor rechazó la solicitud.",
                    "REDIRECT_REFUSED": "El servidor intentó redirigir a otro host. Por seguridad, AcTweeteR no envió allí las credenciales.",
                    "HTTPS_UNAVAILABLE": "No se pudo confirmar una conexión HTTPS segura con el mismo servidor.",
                    "HTTP_ONLY": "El proveedor solo responde por HTTP.",
                    "SERVER_UNAVAILABLE": "No se pudo conectar con el servidor.",
                    "INVALID_RESPONSE": "El servidor respondió con un formato no reconocido.",
                    "INVALID_CREDENTIALS": "El proveedor no aceptó la configuración guardada.",
                    "ACCOUNT_UNAVAILABLE": "El proveedor indica que la cuenta no está disponible.",
                    "CREDENTIALS_REQUIRED": "Faltan datos en el perfil activo.",
                    "PROFILE_UNAVAILABLE": "El perfil activo de XStream no es válido.",
                    "SERVER_INVALID": "La dirección guardada no es válida.",
                }
                dialog.ok("No se pudo comprobar el proveedor",
                          messages.get(status, "No se pudo validar el perfil guardado."))
                return False
            if allow_insecure and urlparse(base).scheme == "http":
                _HTTP_AUTHORIZED_BASE = base
            state = _read_state()
            _write_state(mark_setup_check(state, "provider_authentication", "PASS_RUNTIME"))
            try:
                _dispatch_plugin_query(
                    "plugin://plugin.video.xstream-pro/?mode=actweeter_refresh_profile&pnum=%d" %
                    profile_number,
                    "setup.provider_existing_profile", wait=True)
            except Exception as exc:  # noqa: BLE001 - suppress provider details.
                xbmc.log("[AcTweeteR] XSTREAM_REFRESH status=error type=%s" %
                         type(exc).__name__, xbmc.LOGWARNING)
                dialog.ok("Catálogo pendiente",
                          "La cuenta está validada, pero no se pudo iniciar la actualización automática. Los catálogos siguen pendientes.")
            return True

    server = dialog.input("Servidor o URL Xtream", type=xbmcgui.INPUT_ALPHANUM)
    if not server:
        return False
    embedded = False
    try:
        parsed = parse_xtream_input(server)
        embedded = bool(parsed[1] and parsed[2])
    except SetupError as exc:
        if str(exc) != "CREDENTIALS_REQUIRED":
            dialog.ok("Datos no válidos", "La dirección debe ser una URL HTTP/HTTPS válida del proveedor.")
            return False
    if embedded:
        base, username, password = parsed
    else:
        base = server
        username = dialog.input("Usuario", type=xbmcgui.INPUT_ALPHANUM)
        if not username:
            return False
        password = dialog.input(
            "Contraseña", type=xbmcgui.INPUT_ALPHANUM,
            option=xbmcgui.ALPHANUM_HIDE_INPUT)
        if not password:
            return False

    try:
        base, username, password = parse_xtream_input(base, username, password)
    except SetupError:
        dialog.ok("Datos no válidos", "Comprueba el servidor, usuario y contraseña e inténtalo de nuevo.")
        return False
    allow_insecure = False
    if urlparse(base).scheme == "http":
        transport, secure_base = prepare_https_endpoint(base)
        if transport == "HTTPS_READY":
            base = secure_base
        elif transport == "HTTP_ONLY":
            allow_insecure = dialog.yesno(
                "Proveedor sin HTTPS",
                "No se encontró un endpoint HTTPS válido. Si continúas, el proveedor recibirá el usuario y la contraseña sin cifrado de transporte. ¿Autorizas esa conexión insegura?",
                nolabel="Cancelar", yeslabel="Enviar sin cifrar")
            if not allow_insecure:
                return False
        else:
            dialog.ok(
                "No se pudo verificar HTTPS",
                "AcTweeteR no enviará credenciales porque la respuesta HTTPS no pudo verificarse de forma segura.")
            return False

    try:
        status = validate_xtream_credentials(
            base, username, password, allow_insecure=allow_insecure,
            user_agent=addon.getSetting("custom_user_agent"))
    except Exception as exc:  # noqa: BLE001 - never emit provider URL or credentials.
        xbmc.log(f"[AcTweeteR] XSTREAM_SETUP status=validation_error type={type(exc).__name__}",
                 xbmc.LOGWARNING)
        status = "SERVER_UNAVAILABLE"
    messages = {
        "SERVER_REJECTED": "El servidor rechazó la solicitud. Comprueba la dirección y vuelve a intentarlo.",
        "REDIRECT_REFUSED": "El servidor intentó redirigir a otro host. Por seguridad, AcTweeteR no envió allí las credenciales.",
        "HTTPS_UNAVAILABLE": "No se pudo confirmar una conexión HTTPS segura con el mismo servidor.",
        "HTTP_ONLY": "El proveedor solo responde por HTTP.",
        "SERVER_UNAVAILABLE": "No se pudo conectar con el servidor. Comprueba la conexión e inténtalo de nuevo.",
        "INVALID_RESPONSE": "El servidor respondió con un formato no reconocido por Xtream Codes.",
        "INVALID_CREDENTIALS": "El proveedor no aceptó estas credenciales.",
        "ACCOUNT_UNAVAILABLE": "El proveedor indica que la cuenta está caducada o deshabilitada.",
    }
    if status != "AUTHENTICATED":
        dialog.ok("No se pudo conectar", messages.get(status, "No se pudo validar la cuenta."))
        return False
    if allow_insecure and urlparse(base).scheme == "http":
        _HTTP_AUTHORIZED_BASE = base
    try:
        save_native_profile(
            addon, base, username, password,
            translated_addon_path=xbmcvfs.translatePath(
                addon.getAddonInfo("path")))
    except Exception as exc:  # noqa: BLE001 - Kodi settings bridge errors may be implementation-specific.
        code = (str(exc) if isinstance(exc, SetupError)
                else "XSTREAM_SETTINGS_WRITE_FAILED")
        dialog.ok(
            "No se guardó la configuración",
            f"XStream Pro no coincide con el esquema comprobado o Kodi no confirmó el guardado ({code}). No se guardó una copia en AcTweeteR.",
        )
        return False

    state = _read_state()
    _write_state(mark_setup_check(state, "provider_authentication", "PASS_RUNTIME"))
    try:
        _dispatch_plugin_query(
            "plugin://plugin.video.xstream-pro/?mode=actweeter_refresh_profile&pnum=1",
            "setup.provider_new_profile", wait=True)
    except Exception as exc:  # noqa: BLE001 - log only exception type, never URL or credentials.
        xbmc.log("[AcTweeteR] XSTREAM_REFRESH status=error type=%s" %
                 type(exc).__name__, xbmc.LOGWARNING)
        dialog.ok("Catálogo pendiente",
                  "La cuenta está guardada, pero no se pudo preparar el catálogo. Puedes reintentarlo desde este configurador sin volver a introducir tus datos.")
        return False
    return True


def _missing_components():
    missing = [item["id"] for item in installation_plan(_platform())
               if not item["supported"] or not _addon_requirement_ready(item["id"])]
    for item in _installed_dependency_graph():
        if item["status"] != "READY" and item["id"] not in missing:
            missing.append(item["id"])
    if (_addon_ready("plugin.video.xstream-pro") and not _xstream_refresh_supported()
            and "plugin.video.xstream-pro" not in missing):
        missing.append("plugin.video.xstream-pro")
    return missing


def _complete_missing_components(dialog, *, consent_granted=False, quiet=False):
    """Display progress from confirmed components, and always close the UI."""
    factory = getattr(xbmcgui, "DialogProgressBG", None)
    progress = factory() if factory else None
    if progress:
        progress.create("Preparando AcTweeteR", "Comprobando componentes")

    def update(addon_id):
        if progress:
            rows = _installed_dependency_graph()
            confirmed = sum(row["status"] == "READY" for row in rows)
            total = len(rows)
            progress.update(int(100 * confirmed / total) if total else 0,
                            "Preparando AcTweeteR",
                            "%d de %d componentes comprobados · %s" % (confirmed, total, addon_id))
    try:
        return _install_components_once(dialog, consent_granted=consent_granted,
                                        quiet=quiet, on_component=update)
    finally:
        if progress:
            progress.close()


def _install_components_once(dialog, *, consent_granted=False, quiet=False,
                             on_component=lambda addon_id: None):
    """Repair the mandatory add-on graph through Kodi, with one consent step."""
    missing = _missing_components()
    if not missing:
        _write_state(mark_catalog_reconciled(_read_state()))
        if not quiet:
            dialog.ok("Componentes preparados", "Los complementos obligatorios están instalados y habilitados. La autenticación, los catálogos, PVR/EPG y la reproducción todavía requieren verificación real.")
        return True

    if not consent_granted and not dialog.yesno(
            "Preparar componentes de AcTweeteR",
            "Kodi preparará todos los componentes de AcTweeteR desde fuentes autorizadas. Mostrará sus propias confirmaciones de seguridad. Se conservarán los datos de los complementos existentes.",
            "Ahora no", "Continuar"):
        return False

    labels = {
        "plugin.video.xstream-pro": "XStream Pro",
        "pvr.iptvsimple": "PVR IPTV Simple",
        "script.bingie.helper": "BINGIE Helper",
        "script.bingie.toolbox": "BINGIE Toolbox",
        "script.bingie.widgets": "BINGIE Widgets",
        "script.skinshortcuts": "Skin Shortcuts",
        "resource.images.studios.coloured": "Studio artwork",
        "plugin.video.tmdb.bingie.helper": "BINGIE metadata helper",
        "plugin.program.autocompletion": "Search keyboard support",
        "plugin.video.youtube": "YouTube search and trailer fallback",
    }
    outcomes = []
    dependency_rows = {item["id"]: item for item in _installed_dependency_graph()}
    unsupported = {item["id"] for item in installation_plan(_platform())
                   if not item["supported"]}
    for addon_id in missing:
        on_component(addon_id)
        if (addon_id == "plugin.video.xstream-pro" and _addon_ready(addon_id)
                and _addon_version(addon_id) in SUPPORTED_XSTREAM_VERSIONS and not _xstream_refresh_supported()):
            outcomes.append("XStream: falta la integración AcTweeteR. Kodi debe reinstalar el paquete correcto desde el repositorio AcTweeteR conservando sus datos; InstallAddon no sustituye un ID ya instalado.")
            continue
        row = dependency_rows.get(addon_id, {})
        if row.get("status") in ("INVALID_MANIFEST", "DEPENDENCY_CYCLE"):
            outcomes.append("%s: metadatos instalados no válidos; reparar desde el gestor de Kodi sin borrar sus datos." % addon_id)
            continue
        if addon_id in unsupported:
            outcomes.append("%s: compatibilidad de plataforma no verificada." % addon_id)
            continue
        if (_is_tvos() and addon_id in ("pvr.iptvsimple", "inputstream.adaptive")
                and not _addon_installed(addon_id)):
            outcomes.append(
                "PVR IPTV Simple: este Kodi tvOS no lo presenta instalado; no se descargará ni instalará un binario tvOS genérico.")
            continue
        if (_is_tvos() and addon_id == "plugin.video.xstream-pro"
                and _tvos_xstream_dependency_status() != "READY"):
            outcomes.append(
                "XStream Pro: pendiente; primero debe existir IPTV Simple tvOS habilitado y >=21.4.0.")
            continue
        sources = REQUIRED_REPAIR_SOURCES.get(addon_id, ("repository.actweeter", "repository.xbmc.org"))
        for source in sources:
            if _addon_enabled(source):
                break
            if _addon_installed(source) and not _addon_enabled(source):
                _ensure_repository_enabled(dialog, source)
        enabled_sources = [source for source in sources if _addon_enabled(source)]
        if not enabled_sources and not _addon_installed(addon_id):
            outcomes.append("%s: fuente requerida no disponible (%s)." %
                            (labels.get(addon_id, addon_id), ", ".join(sources)))
            continue
        result = _request_native_addon_install(
            dialog, addon_id, ", ".join(enabled_sources) or "instalación existente de Kodi",
            required=True, consent_granted=True,
            minimum_version=row.get("minimum") or None)
        if addon_id == "repository.slyguy" and result == "INSTALLED":
            xbmc.executebuiltin("UpdateAddonRepos", True)
        on_component(addon_id)
        outcomes.append("%s: %s." % (
            labels.get(addon_id, addon_id),
            "instalado y habilitado" if result == "INSTALLED" else
            "pendiente; puedes reintentar desde este asistente"))
    outcomes.append(
        "Se usa el resolvedor nativo de Kodi; cada add-on conserva su configuración. "
        "La instalación de componentes no prueba proveedor, catálogo, EPG ni reproducción.")
    remaining = _missing_components()
    if not remaining:
        _write_state(mark_catalog_reconciled(_read_state()))
    if not quiet or remaining:
        dialog.textviewer("Instalación de complementos", "\n\n".join(outcomes))
    return not remaining


def _home_diagnostic():
    """Log a one-shot, secret-free snapshot; never records labels or paths."""
    window_id = focus_id = -1
    try:
        response = json.loads(xbmc.executeJSONRPC(json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "GUI.GetProperties",
            "params": {"properties": ["currentwindow"]},
        })))
        window_id = response.get("result", {}).get("currentwindow", {}).get("id", -1)
        if isinstance(window_id, int) and window_id >= 0:
            focus_id = xbmcgui.Window(window_id).getFocusId()
    except Exception:
        pass
    missing_required = sum(not _addon_ready(addon_id)
                           for addon_id in REQUIRED_ADDON_IDS)
    widgets_count = xbmc.getInfoLabel("Container(77777).NumItems")
    snapshot = home_diagnostic_snapshot(
        window_id=window_id,
        focus_id=focus_id,
        menu_visible=xbmc.getCondVisibility("Control.IsVisible(900)"),
        widgets_count=widgets_count,
        widgets_updating=xbmc.getCondVisibility("Container(77777).IsUpdating"),
        startup_mask=xbmc.getInfoLabel("Window(Home).Property(StartupMask)"),
        intro_playback=xbmc.getInfoLabel("Window(Home).Property(AcTweeteRIntroPlayback)"),
        missing_required_count=missing_required,
    )
    xbmc.log(
        "[AcTweeteR] HOME_DIAGNOSTIC window=%d focus=%d menu_visible=%d widgets=%d updating=%d startup_mask=%d intro=%d missing_required=%d" % (
            snapshot["window_id"], snapshot["focus_id"], snapshot["menu_visible"],
            snapshot["widgets_count"], snapshot["widgets_updating"],
            snapshot["startup_mask"], snapshot["intro_playback"],
            snapshot["missing_required_count"]), xbmc.LOGINFO)
    return snapshot


def _set_intro(dialog):
    selected = dialog.select("Introducción", [label for label, _ in INTRO_OPTIONS])
    mode = intro_mode_for_selection(selected)
    if mode is None:
        return False
    xbmc.executebuiltin("Skin.SetString(splash_screen,%s)" % mode)
    return True


def _run_install_diagnostics(dialog):
    """Show and export sanitized Kodi diagnostics without JSON-RPC."""
    from diagnostic_ui import run as run_local_diagnostics

    profile_path = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
    return run_local_diagnostics(dialog, xbmc, xbmcaddon, xbmcvfs,
                                 profile_path=profile_path)


def _preview_notify(action, payload):
    encoded = base64.b64encode(json.dumps(
        {"action": action, **payload}, separators=(",", ":")
    ).encode("utf-8")).decode("ascii")
    request = {"jsonrpc": "2.0", "id": 1, "method": "JSONRPC.NotifyAll",
               "params": {"sender": "service.actweeter.SIGNAL",
                          "message": "actweeter_auto_preview", "data": [encoded]}}
    try:
        response = json.loads(xbmc.executeJSONRPC(
            json.dumps(request, separators=(",", ":"))))
        status = "accepted" if "error" not in response else "rejected"
    except Exception as exc:
        xbmc.log("[AcTweeteR] AUTO_PREVIEW_SIGNAL action=%s status=error type=%s" %
                 (action, type(exc).__name__), xbmc.LOGWARNING)
        return False
    xbmc.log("[AcTweeteR] AUTO_PREVIEW_SIGNAL action=%s status=%s" %
             (action, status), xbmc.LOGINFO)
    return status == "accepted"


def _auto_preview_focus(args):
    if len(args) < 1:
        xbmc.log("[AcTweeteR] AUTO_PREVIEW_FOCUS status=invalid_args", xbmc.LOGWARNING)
        return
    try:
        container = int(args[0])
        delay = float(args[1]) if len(args) > 1 else 3.0
        if container <= 0 or not (0.0 <= delay <= 60.0):
            xbmc.log("[AcTweeteR] AUTO_PREVIEW_FOCUS status=invalid_target", xbmc.LOGWARNING)
            return
        result = json.loads(xbmc.executeJSONRPC(json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "GUI.GetProperties",
            "params": {"properties": ["currentwindow"]},
        })))
        window = int(result["result"]["currentwindow"]["id"])
        focus = int(xbmcgui.Window(window).getFocusId())
        prefix = "Container(%d).ListItem." % container
        trailer = xbmc.getInfoLabel(prefix + "Trailer")
        trailer_id = ""
        try:
            parsed = urlparse(trailer)
            query = parse_qs(parsed.query)
            if parsed.hostname in ("youtube.com", "www.youtube.com", "m.youtube.com",
                                  "youtu.be", "plugin.video.youtube"):
                candidate = ((query.get("v") or query.get("video_id") or [""])[0]
                             if parsed.hostname != "youtu.be" else
                             parsed.path.strip("/"))
                if re.fullmatch(r"[A-Za-z0-9_-]{6,64}", candidate):
                    trailer_id = candidate
        except (TypeError, ValueError):
            trailer_id = ""
        payload = {
            "window": window,
            "container": container,
            "focus": focus,
            "position": int(xbmc.getInfoLabel("Container(%d).CurrentItem" % container) or "-1"),
            "media_type": xbmc.getInfoLabel(prefix + "DBType").lower(),
            "imdb": xbmc.getInfoLabel(prefix + "UniqueID(imdb)"),
            "tmdb": xbmc.getInfoLabel(prefix + "UniqueID(tmdb)"),
            "dbid": xbmc.getInfoLabel(prefix + "DBID"),
            "title": xbmc.getInfoLabel(prefix + "Title"),
            "year": xbmc.getInfoLabel(prefix + "Year"),
            "trailer_id": trailer_id,
            "delay": delay,
        }
        xbmc.log("[AcTweeteR] AUTO_PREVIEW_FOCUS status=captured window=%d container=%d focus=%d media=%s identity=%s trailer=%s" %
                 (window, container, focus, payload["media_type"],
                  "present" if payload["imdb"] or payload["tmdb"] or payload["dbid"] else "missing",
                  "present" if trailer_id else "missing"), xbmc.LOGINFO)
        _preview_notify("focus", payload)
    except (KeyError, TypeError, ValueError):
        xbmc.log("[AcTweeteR] AUTO_PREVIEW_FOCUS status=state_unavailable", xbmc.LOGWARNING)
        return
    except Exception as exc:
        xbmc.log("[AcTweeteR] AUTO_PREVIEW_FOCUS status=error type=%s" %
                 type(exc).__name__, xbmc.LOGWARNING)
        return


def _auto_preview_cancel(args):
    try:
        container = int(args[0]) if args else 0
        payload = {}
        if container > 0:
            result = json.loads(xbmc.executeJSONRPC(json.dumps({
                "jsonrpc": "2.0", "id": 1, "method": "GUI.GetProperties",
                "params": {"properties": ["currentwindow"]},
            })))
            window = int(result["result"]["currentwindow"]["id"])
            focus = int(xbmcgui.Window(window).getFocusId())
            prefix = "Container(%d).ListItem." % container
            payload = {
                "container": container, "window": window, "focus": focus,
                "position": int(xbmc.getInfoLabel(
                    "Container(%d).CurrentItem" % container) or "-1"),
                "media_type": xbmc.getInfoLabel(prefix + "DBType").lower(),
                "imdb": xbmc.getInfoLabel(prefix + "UniqueID(imdb)"),
                "tmdb": xbmc.getInfoLabel(prefix + "UniqueID(tmdb)"),
                "dbid": xbmc.getInfoLabel(prefix + "DBID"),
            }
        _preview_notify("cancel", payload)
    except (TypeError, ValueError):
        xbmc.log("[AcTweeteR] AUTO_PREVIEW_CANCEL status=state_unavailable", xbmc.LOGWARNING)
        return
    except Exception as exc:
        xbmc.log("[AcTweeteR] AUTO_PREVIEW_CANCEL status=error type=%s" %
                 type(exc).__name__, xbmc.LOGWARNING)
        return


def _auto_preview_preempt(owner):
    if owner in ("MANUAL_DETAIL", "MANUAL_SPOTLIGHT", "VOD", "OTHER"):
        _preview_notify("preempt", {"owner": owner})


def _play_intro():
    """Open the existing skin mask once per Kodi process for AcTweeteR modes."""
    mode = xbmc.getInfoLabel("Skin.String(splash_screen)")
    if mode not in ("actweeter_video", "actweeter_image"):
        return
    session_path = _intro_session_path()
    if not claim_process_session(session_path, os.getpid()):
        xbmc.log("[AcTweeteR] INTRO_SESSION_GUARD status=not_claimed",
                 xbmc.LOGINFO)
        return
    xbmc.log("[AcTweeteR] INTRO_SESSION_GUARD status=claimed",
             xbmc.LOGINFO)
    # Claim before inspecting playback: on startup the mask/player can become
    # active before this Home onload script runs. That must still consume the
    # process-wide attempt, or a later Home activation can replay the intro.
    if xbmc.getCondVisibility("Player.HasMedia"):
        return
    xbmc.executebuiltin("SetProperty(AcTweeteRIntroShown,1,Home)")
    xbmc.executebuiltin("SetProperty(StartupMask,1,Home)")
    xbmcgui.Window(10000).setProperty("AcTweeteRStartupIntroActive", "1")
    if mode == "actweeter_video":
        # Establish ownership before opening the modal so menu focus cannot
        # clear the startup mask during the window-creation transition.
        xbmc.executebuiltin("SetProperty(AcTweeteRIntroPlayback,1,Home)")
    xbmc.executebuiltin("ActivateWindow(1103)")


def _intro_watchdog():
    """Release the visible splash only when the local intro never started."""
    if not xbmc.getInfoLabel("Window(Home).Property(AcTweeteRIntroPlayback)"):
        return
    if xbmc.getCondVisibility("Player.HasVideo"):
        xbmc.log("[AcTweeteR] INTRO_WATCHDOG status=player_active", xbmc.LOGINFO)
        return
    xbmc.log("[AcTweeteR] INTRO_WATCHDOG status=playback_not_started", xbmc.LOGWARNING)
    xbmc.executebuiltin("ClearProperty(AcTweeteRIntroPlayback,Home)")
    xbmc.executebuiltin("ClearProperty(StartupMask,Home)")
    xbmc.executebuiltin("Dialog.Close(1103,true)")


def _prepare_product_interface(dialog, *, allow_prompt=False):
    try:
        return prepare_interface(xbmc, xbmcaddon.Addon, xbmcvfs, xbmcgui,
                                 dialog, allow_prompt=allow_prompt)
    except Exception as exc:
        xbmc.log('[AcTweeteR] INTERFACE_LAYOUT status=error type=%s'%type(exc).__name__,xbmc.LOGERROR)
        return 'ERROR'


def _run_pending_interface_migration(dialog, *, explicit=False):
    """Run a layout update independently of the once-per-process wizard.

    A dismissed/failed migration is not retried on every Home refresh in the
    same Kodi session. The existing explicit repair action remains available
    and bypasses that per-session suppression.
    """
    window = xbmcgui.Window(10000)
    marker = str(LAYOUT_VERSION)
    marker_name = "AcTweeteR.InterfaceMigrationAttempted"
    if explicit:
        window.clearProperty(marker_name)
    elif window.getProperty(marker_name) == marker:
        return "ATTEMPTED_THIS_SESSION"

    profile = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
    state_path = os.path.join(profile, "interface_layout_state.json")
    state = load_state(state_path)
    if not interface_migration_due(state):
        return "CURRENT"

    xbmc.log("[AcTweeteR] INTERFACE_LAYOUT_UPDATE status=started target=%d" %
             LAYOUT_VERSION, xbmc.LOGINFO)
    result = _prepare_product_interface(dialog, allow_prompt=True)
    if result != "GENERATED":
        window.setProperty(marker_name, marker)
        xbmc.log("[AcTweeteR] INTERFACE_LAYOUT_UPDATE status=deferred result=%s" %
                 result, xbmc.LOGWARNING)
        return result

    window.clearProperty(marker_name)
    xbmc.log("[AcTweeteR] INTERFACE_LAYOUT_UPDATE status=verified target=%d" %
             LAYOUT_VERSION, xbmc.LOGINFO)
    return result


def _finish_setup(dialog):
    if _prepare_product_interface(dialog, allow_prompt=True) != 'GENERATED':
        dialog.ok('Interfaz pendiente', 'La preparación de las filas de AcTweeteR no se ha confirmado. Tus ajustes se conservan; puedes volver a reparar la interfaz.')
        return False
    state, evidence = _evaluate_setup_gates(_read_state())
    blockers = completion_blockers(state)
    _write_state(mark_completed(state))
    if blockers:
        reasons = {
            "mandatory_addons": "Faltan componentes compatibles instalados y habilitados.",
            "provider_authentication": "No se ha confirmado la conexión con tu proveedor.",
            "movies_catalog": "No se ha confirmado el catálogo de películas.",
            "series_catalog": "No se ha confirmado el catálogo de series.",
            "live_tv_ready": "Kodi todavía no ofrece canales en directo.",
            "pvr_configuration": "La sincronización de televisión sigue pendiente.",
            "trailer_addon_ready": "La cadena de SlyGuy Trailers no está preparada.",
        }
        dialog.ok("Configuración incompleta", "\n".join(reasons.get(key, key) for key in blockers))
        return False
    dialog.ok("AcTweeteR está preparado",
              "Tus componentes y catálogos están preparados. La reproducción real se comprueba por separado; la disponibilidad de guía depende del proveedor.")
    return True


def _connect_trakt(dialog):
    """Run script.trakt's native device flow without inspecting its token."""
    def status(value):
        _write_state(mark_trakt_status(_read_state(), value, integration="script"))
        return value

    installed_before = _addon_installed("script.trakt")
    previous = _read_state().get("script_trakt_status")
    if previous in ("AUTHORIZATION_UNVERIFIED", "AUTHORIZED_LOCAL"):
        if not dialog.yesno(
                "Verificación de Trakt pendiente",
                "La autorización anterior se conserva, pero AcTweeteR no puede verificarla mediante una interfaz pública. Puedes reintentar; también puedes volver sin afectar a IPTV ni a la configuración principal.",
                nolabel="Ahora no", yeslabel="REINTENTAR"):
            return status("AUTHORIZATION_UNVERIFIED")
    if not dialog.yesno(
            "Conectar Trakt",
            "Trakt es opcional. La autorización se abrirá en el complemento oficial de Kodi. Si cancelas, puedes seguir usando AcTweeteR y conectarlo más tarde desde este asistente o desde los ajustes de Trakt.",
            nolabel="Ahora no", yeslabel="CONECTAR"):
        return status("DEFERRED")
    outcome = _request_native_addon_install(
        dialog, "script.trakt", "repository.xbmc.org", required=True,
        consent_granted=True, minimum_version="3.9.0")
    if outcome != "INSTALLED":
        dialog.ok("Trakt pendiente", "No se pudo preparar el complemento oficial. Tus datos IPTV se conservan; reintenta la autorización desde el asistente.")
        return status("UNAVAILABLE")
    try:
        addon = xbmcaddon.Addon("script.trakt")
        schema = os.path.join(xbmcvfs.translatePath(addon.getAddonInfo("path")),
                              "resources", "settings.xml")
        handle = xbmcvfs.File(schema)
        try:
            supported = supports_device_authorization(handle.read())
        finally:
            handle.close()
        if not supported:
            dialog.ok("Trakt no disponible", "Esta versión no publica el flujo Device Code esperado. La configuración permanece pendiente; actualiza el complemento desde Kodi y reintenta.")
            return status("UNSUPPORTED")
        configure_fresh_defaults(addon, newly_installed=not installed_before)
        status("WAITING_FOR_AUTHORIZATION")
        shown = xbmc.getCondVisibility("Window.IsVisible(%s)" % TRAKT_AUTH_WINDOW)
        if not shown:
            xbmc.executebuiltin(TRAKT_AUTH_ACTION, False)
        monitor = xbmc.Monitor()
        started = time.monotonic()
        # Observe only whether the native dialog is still open. Its appearance
        # or dismissal is not an authorization result; no token/settings are read.
        while not monitor.abortRequested():
            visible = xbmc.getCondVisibility("Window.IsVisible(%s)" % TRAKT_AUTH_WINDOW)
            if shown and not visible:
                break
            shown = shown or visible
            elapsed = time.monotonic() - started
            if elapsed >= 600 or (not shown and elapsed >= 90):
                break
            if monitor.waitForAbort(0.5):
                break
        dialog.ok("Autorización sin verificar",
                  "El flujo oficial se abrió, pero script.trakt no ofrece a AcTweeteR una señal pública para confirmar el resultado sin leer su token privado. La autorización queda pendiente y no se marcará como completada.")
        return status("AUTHORIZATION_UNVERIFIED")
    except Exception as exc:
        xbmc.log("[AcTweeteR] TRAKT_SETUP status=error type=%s" % type(exc).__name__, xbmc.LOGWARNING)
        dialog.ok("Trakt pendiente", "No se pudo completar la autorización. Tus datos IPTV se conservan; vuelve a intentarlo desde el asistente.")
        return status("FAILED_RECOVERABLE")


def _connect_xstream_trakt(dialog):
    """Open XStream's own Device Code flow; never inspect or copy its token."""
    def status(value):
        _write_state(mark_trakt_status(_read_state(), value, integration="xstream"))
        return value

    if not _addon_installed("plugin.video.xstream-pro"):
        dialog.ok("XStream no disponible",
                  "No se encontró XStream Pro. IPTV principal y el resto de AcTweeteR no dependen de esta autorización.")
        return status("UNAVAILABLE")
    if not dialog.yesno(
            "Recomendaciones de XStream (opcional)",
            "XStream abrirá su autorización Trakt Device Code nativa. Esta vinculación solo habilita sus funciones de cuenta y recomendaciones; no activa un segundo scrobbling. Puedes cancelar y seguir usando IPTV sin cambios.",
            nolabel="Ahora no", yeslabel="CONECTAR"):
        return status("DEFERRED")
    try:
        # Upstream XStream 1.1.2 has its own Device Code route and bundled
        # upstream OAuth application configuration. AcTweeteR does not copy
        # those values, own the flow, or infer success from its dismissal.
        xbmc.executebuiltin(XSTREAM_TRAKT_AUTH_ACTION, True)
        # Refresh XStream's provider inventory off the widget request path.
        # Its completion callback refreshes the Home container after the exact
        # availability cache has been rebuilt.
        _catalog_refresh_start(dialog)
        dialog.ok(
            "Vinculación no verificable por AcTweeteR",
            "El flujo nativo de XStream ha terminado. XStream conserva su autorización; AcTweeteR no lee su token ni puede verificarlo mediante una API pública. La fila solo aparecerá si XStream devuelve recomendaciones con coincidencia exacta en tu catálogo IPTV. Puedes reintentar desde este menú.",
        )
        return status("AUTHORIZATION_UNVERIFIED")
    except Exception as exc:
        xbmc.log("[AcTweeteR] XSTREAM_TRAKT status=error type=%s" % type(exc).__name__, xbmc.LOGWARNING)
        dialog.ok("XStream pendiente",
                  "No se pudo abrir la autorización nativa. La configuración IPTV se conserva; puedes reintentar más tarde.")
        return status("FAILED_RECOVERABLE")


def _run_onboarding(dialog):
    """One sequential setup flow; maintenance is separate from first-run setup."""
    if not dialog.yesno(
            "Bienvenido a AcTweeteR",
            "Configura tu televisión y catálogo multimedia en unos pasos. Prepararemos los componentes y solo te pediremos los datos de tu proveedor y las autorizaciones necesarias.",
            nolabel="Ahora no", yeslabel="COMENZAR"):
        _write_state(mark_deferred(_read_state(), os.getpid()))
        return False
    _write_state(mark_started(_read_state()))
    while not xbmc.Monitor().abortRequested():
        _write_state(mark_step(_read_state(), "Preparar componentes automáticamente", "IN_PROGRESS"))
        if _complete_missing_components(dialog, consent_granted=True, quiet=True):
            break
        if not dialog.yesno("Preparación pendiente · 2 de 6",
                            "Algunos componentes no están preparados. Tus datos se conservan y podrás reanudar la instalación.",
                            nolabel="Salir", yeslabel="REINTENTAR"):
            _write_state(mark_step(_read_state(), "Preparar componentes automáticamente", "RETURNED"))
            return False
    if xbmc.Monitor().abortRequested():
        return False
    _write_state(mark_step(_read_state(), "Preparar componentes automáticamente", "DONE"))
    while not xbmc.Monitor().abortRequested():
        _write_state(mark_step(_read_state(), "Conectar proveedor IPTV", "IN_PROGRESS"))
        with _setup_progress("Comprobando la conexión y preparando el catálogo"):
            connected = _configure_xstream_provider(dialog)
        if connected:
            break
        if not dialog.yesno("Conexión pendiente · 3 de 6",
                            "No se ha confirmado tu proveedor. Puedes corregir los datos o salir y continuar más tarde.",
                            nolabel="Salir", yeslabel="REINTENTAR"):
            _write_state(mark_step(_read_state(), "Conectar proveedor IPTV", "RETURNED"))
            return False
    if xbmc.Monitor().abortRequested():
        return False
    _write_state(mark_step(_read_state(), "Conectar proveedor IPTV", "DONE"))
    _write_state(mark_step(_read_state(), "Autorizaciones externas", "IN_PROGRESS"))
    if dialog.yesno(
            "Trakt es opcional",
            "Puedes autorizar el complemento oficial de Kodi ahora para scrobbling y sincronización de biblioteca. También puedes configurarlo después desde sus ajustes. IPTV, películas, series, TV y EPG no dependen de Trakt.",
            nolabel="Ahora no", yeslabel="CONECTAR"):
        _connect_trakt(dialog)
    _connect_xstream_trakt(dialog)
    _write_state(mark_step(_read_state(), "Autorizaciones externas", "REVIEWED"))
    _write_state(mark_step(_read_state(), "Configurar y verificar servicios", "IN_PROGRESS"))
    return _verify_connected_services(dialog)


def _wizard(dialog, *, first_run=False):
    if first_run:
        return _run_onboarding(dialog)

    options = [
        "Preparar componentes automáticamente",
        "Conectar proveedor IPTV",
        "Preparar tráilers y autorizaciones",
        "Configurar y verificar servicios",
        "Finalizar configuración",
        "Reparar componentes",
        "Diagnosticar instalación",
        "Reparar interfaz de AcTweeteR",
        "Conectar Trakt (opcional)",
        "Vincular recomendaciones de XStream (opcional)",
        "Actualizar catálogo y recomendaciones de XStream",
    ]
    while True:
        state = _read_state()
        start_at = int(state.get("last_step_index", 0)) if str(state.get("last_step_index", "0")).isdigit() else 0
        choice = dialog.select("Configuración inicial de AcTweeteR", options,
                               preselect=min(start_at, len(options) - 1))
        if choice < 0:
            break
        if choice == 8:
            _connect_trakt(dialog)
            continue
        if choice == 9:
            _connect_xstream_trakt(dialog)
            continue
        if choice == 10:
            _catalog_refresh_start(dialog)
            continue
        if choice == 6:
            _run_install_diagnostics(dialog)
            continue
        if choice == 7:
            result = _prepare_product_interface(dialog, allow_prompt=True)
            dialog.ok("Interfaz de AcTweeteR", "Diseño preparado. Vuelve a Inicio para comprobar sus filas." if result == "GENERATED" else "El diseño no se ha aplicado: %s. Se conservan tus ajustes." % result)
            continue
        if choice == 4:
            state, evidence = _evaluate_setup_gates(state)
            if not completion_blockers(state):
                state = mark_completed(state)
            blockers = completion_blockers(state)
            if blockers:
                state = mark_step(state, options[choice], "REVIEWED")
                _write_state(state)
                reasons = {
                    "mandatory_addons": "faltan componentes obligatorios instalados/habilitados",
                    "provider_authentication": "el perfil activo de XStream no tiene autenticación runtime vigente",
                    "movies_catalog": "Kodi no pudo confirmar categorías de películas",
                    "series_catalog": "Kodi no pudo confirmar categorías de series",
                    "live_tv_ready": "PVR aún no ofrece grupos/canales listos",
                    "pvr_configuration": "PVR IPTV Simple no está configurado con grupos y canales disponibles",
                }
                details = [reasons.get(item, item) for item in blockers]
                dialog.ok(
                    "Configuración incompleta",
                    "AcTweeteR no guardará SETUP_COMPLETE todavía.\n• %s\n\n"
                    "Comprobación actual: %s categorías de películas, %s de series, %s grupos y %s canales. "
                    "Perfil HTTPS persistente: %s. La EPG y las pruebas de reproducción no bloquean la instalación. Puedes actualizar el proveedor/PVR y volver a comprobar."
                    % ("\n• ".join(details),
                       evidence["movies"] if evidence["movies"] is not None else "sin datos",
                       evidence["series"] if evidence["series"] is not None else "sin datos",
                       evidence["pvr"]["groups"], evidence["pvr"]["channels"],
                       "sí" if evidence["https_persisted"] else "no/pendiente"),
                )
            else:
                _write_state(state)
                dialog.ok("AcTweeteR", "AcTweeteR está preparado. El perfil IPTV persistido usa HTTPS: %s. La reproducción de películas, episodios y tráilers se valida por separado." % (
                    "sí" if evidence["https_persisted"] else "no; usa HTTP autorizado por el usuario"))
            return
        if choice == 5:
            _complete_missing_components(dialog)
            state = _read_state()
            _write_state(mark_step(state, options[choice], "REVIEWED"))
            continue
        _write_state(mark_step(state, options[choice], "IN_PROGRESS"))
        if choice == 0:
            _complete_missing_components(dialog)
            state = _read_state()
            _write_state(mark_step(state, options[choice], "REVIEWED"))
            continue
        if choice == 3:
            pvr_ready = False
            if _addon_ready(OPTIONAL_ADDONS["pvr"]):
                pvr_ready = _pvr_ready(_pvr_status())
            if not pvr_ready:
                _configure_pvr_from_xstream(dialog)
                state = _read_state()
                state, _ = _evaluate_setup_gates(state)
                _write_state(state)
            _show_status(dialog)
        elif choice == 1:
            with _setup_progress("Comprobando la conexión y preparando el catálogo"):
                connected = _configure_xstream_provider(dialog)
            if connected:
                _write_state(mark_step(_read_state(), options[choice], "DONE"))
                if _verify_connected_services(dialog):
                    return
        elif choice == 2:
            _install_slyguy_stack(dialog)
            dialog.ok(
                "Tráilers y autorizaciones",
                "La instalación utiliza repository.slyguy y el resolvedor nativo de Kodi. La reproducción real de un tráiler sigue siendo una comprobación separada. YouTube puede requerir autorización propia; AcTweeteR no lee ni guarda sus tokens.",
            )
        else:
            _show_status(dialog)
        state = _read_state()
        state["last_step_index"] = choice
        result = "REVIEWED" if choice in (2, 3) else "RETURNED"
        _write_state(mark_step(state, options[choice], result))


def main():
    dialog = xbmcgui.Dialog()
    action = sys.argv[1].strip().casefold() if len(sys.argv) > 1 else "wizard"
    args = [part.strip() for part in sys.argv[2:]]
    if action == 'backup_interface':
        result=backup_interface(xbmcaddon.Addon,xbmcvfs)
        xbmc.log('[AcTweeteR] INTERFACE_BACKUP status=verified files=%d'%len(result['files']),xbmc.LOGINFO)
    elif action == "catalog_refresh":
        _catalog_refresh_start(dialog)
    elif action == "catalog_refresh_result":
        _catalog_refresh_result(args, dialog)
    elif action in ('prepare_interface','repair_interface'):
        if action == 'repair_interface':
            _run_pending_interface_migration(dialog, explicit=True)
        else:
            _prepare_product_interface(dialog, allow_prompt=False)
    elif action == "preview_focus":
        _auto_preview_focus(args)
    elif action == "preview_cancel":
        _auto_preview_cancel(args)
    elif action == "preview_manual":
        _auto_preview_preempt("MANUAL_DETAIL")
    elif action == "preview_spotlight":
        _auto_preview_preempt("MANUAL_SPOTLIGHT")
    elif action == "preview_vod":
        _auto_preview_preempt("VOD")
    elif action == "touch_trace":
        values = {}
        for part in args:
            key, separator, value = part.partition("=")
            if separator and key in ("control", "variant"):
                values[key] = value
        dialog_id = None
        focus_id = None
        try:
            dialog_id = xbmcgui.getCurrentWindowDialogId()
            if type(dialog_id) is int and dialog_id > 0:
                focus_id = xbmcgui.Window(dialog_id).getFocusId()
        except (AttributeError, RuntimeError, SystemError, ValueError):
            pass
        arm_interaction_trace(
            xbmcgui.Window(10000), values.get("control", ""),
            values.get("variant", ""),
            log=lambda message: xbmc.log(message, xbmc.LOGINFO),
            dialog_id=dialog_id, focus_id=focus_id,
        )
    elif action == "preview_exit":
        # Leaving a skin surface cancels its own preview work; it does not
        # imply that an unrelated/external player has taken ownership.
        _preview_notify("exit", {})
    elif action in ("first_run", "firstrun", "first_run_resume"):
        resume = action == "first_run_resume"
        window = xbmcgui.Window(10000)
        if resume and window.getProperty("AcTweeteRFirstRunPending") != "1":
            return
        if not resume:
            # On a fresh profile the startup mask may already be opening. Start
            # the chosen intro before showing any modal onboarding dialog.
            _play_intro()
        if _intro_blocks_first_run(resume_from_mask=resume):
            _defer_first_run_until_intro_closes()
            return
        if resume:
            window.clearProperty("AcTweeteRFirstRunPending")
        xbmc.log("[AcTweeteR] FIRST_RUN_FLOW status=entered", xbmc.LOGINFO)
        # Claim the whole startup UI flow after the intro gate; repeated Home
        # loads must not stack welcome or component dialogs.
        if not claim_process_session(_first_run_session_path(), os.getpid()):
            xbmc.log("[AcTweeteR] FIRST_RUN_FLOW status=skipped reason=session_claimed",
                     xbmc.LOGINFO)
            _run_pending_interface_migration(dialog)
            return
        language_status = _apply_factory_language()
        xbmc.log("[AcTweeteR] FACTORY_LANGUAGE status=%s" % language_status,
                 xbmc.LOGINFO)
        # Upgrades apply AcTweeteR-owned defaults automatically. If the profile
        # contains hand-edited Skin Shortcuts, the layout migrator asks before
        # replacing those files and keeps the pre-migration backup.
        _prepare_product_interface(dialog, allow_prompt=True)
        # Skin Shortcuts can rebuild Home during first-run preparation. If that
        # opens the startup mask, release the claim and resume on its on-unload.
        if _intro_blocks_first_run():
            release_process_session(_first_run_session_path(), os.getpid())
            _defer_first_run_until_intro_closes()
            return
        installed = _installed_addons()
        configured = False
        if installed.get("xstream"):
            try:
                configured = has_xtream_configuration(xbmcaddon.Addon(OPTIONAL_ADDONS["xstream"]))
            except Exception:
                configured = False
        state = _read_state()
        offer_first_run = (should_offer_first_run(state, configured) if resume else
                           should_offer_first_run_in_process(state, configured, os.getpid()))
        if offer_first_run:
            xbmc.log("[AcTweeteR] FIRST_RUN_WIZARD status=offered", xbmc.LOGINFO)
            _wizard(dialog, first_run=True)
        else:
            reason = "prompted" if state.get("prompted") else "core_configured"
            xbmc.log("[AcTweeteR] FIRST_RUN_WIZARD status=skipped reason=%s" % reason,
                     xbmc.LOGINFO)
            missing = _missing_components()
            if should_offer_component_completion(state, missing, configured):
                # Persist before opening UI so repeated Home loads cannot stack
                # prompts. A declined offer remains available from Settings.
                _write_state(mark_component_offer_seen(state))
                required_missing = any(item in REQUIRED_REPAIR_SOURCES for item in missing)
                offer_text = (
                    "Esta actualización detectó componentes requeridos que faltan. ¿Abrir el asistente para pedir a Kodi que los instale desde repositorios autorizados? Puedes posponerlo, pero la configuración seguirá incompleta."
                    if required_missing else
                    "Esta actualización puede ayudarte a instalar los complementos opcionales que faltan. No son necesarios para Home y no se configurarán automáticamente. ¿Abrir el asistente?"
                )
                if dialog.yesno(
                        "Revisión de complementos de AcTweeteR",
                        offer_text,
                        "Ahora no", "Abrir asistente"):
                    _wizard(dialog)
    elif action in ("services", "status"):
        _show_status(dialog)
    elif action in ("diagnostics", "diagnosticar"):
        _run_install_diagnostics(dialog)
    elif action == "intro":
        _play_intro()
    elif action == "intro_watchdog":
        _intro_watchdog()
    else:
        _wizard(dialog)


if __name__ == "__main__":
    main()
