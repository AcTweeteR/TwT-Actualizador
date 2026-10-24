"""Optional TMDb API key onboarding. Never log, export or copy credentials."""
from __future__ import annotations

import json
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from interface_layout import atomic_write

SETTING = "tmdb_alias_api_key"
VERSION = 1
API_URL = "https://api.themoviedb.org/3/movie/603"
REGISTER_URL = "https://www.themoviedb.org/settings/api"
ATTRIBUTION = "This product uses the TMDB API but is not endorsed or certified by TMDB."


def valid_key(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{32}", value) is not None


def check_key(value, requester=None):
    """Use one public movie endpoint; return only status, never the key or response."""
    if not valid_key(value):
        return False
    if requester is None:
        def requester(url):
            with urlopen(Request(url, headers={"Accept": "application/json"}), timeout=7) as response:
                return response.status == 200
    try:
        return requester(API_URL + "?" + urlencode({"api_key": value})) is True
    except Exception:
        return False


def marker(addon, vfs):
    return Path(vfs.translatePath(addon.getAddonInfo("profile"))) / "tmdb_onboarding.json"


def configure(addon, vfs, dialog, *, requester=None):
    """Opt-in guide, masked keyboard, public verification. Can always be reopened."""
    existing = addon.getSetting(SETTING)
    if valid_key(existing):
        if not dialog.yesno("TMDb · Smart Search", "Ya existe una clave API TMDb. ¿Quieres sustituirla? La actual se conservará si cancelas.", nolabel="Conservar", yeslabel="Cambiar"):
            return "CONFIGURED"
    else:
        if not dialog.yesno("TMDb · Smart Search (opcional)",
            "Para consultar títulos originales, traducciones y nombres alternativos puedes introducir una clave API v3 propia y gratuita de TMDb. La búsqueda IPTV seguirá funcionando sin ella.\n\n"
            + ATTRIBUTION,
            nolabel="Omitir", yeslabel="Configurar"):
            return "SKIPPED"
    # Kodi Dialog.input enmascara la entrada. No se registra ni almacena en logs.
    dialog.ok("Obtener una clave de TMDb", "Si aún no tienes tu clave gratuita, visita https://www.themoviedb.org/settings/api desde tu teléfono u ordenador. Copia la API Key v3 (32 caracteres). No necesitas un inicio de sesión TMDb dentro de Kodi.")
    candidate = dialog.input("Pega tu API Key v3 de TMDb (32 caracteres)", type=0, option=1)
    if not valid_key(candidate):
        if candidate:
            dialog.ok("Clave TMDb", "Formato no válido. La clave anterior no se ha modificado. Vuelve a intentarlo desde Configuración → TMDb.")
            return "INVALID"
        return "CANCELLED"
    if not check_key(candidate, requester):
        dialog.ok("TMDb sin verificar", "No se ha podido validar la clave o la conexión. No se ha guardado; puedes volver a intentarlo más tarde.")
        return "UNVERIFIED"
    try:
        addon.setSetting(SETTING, candidate)
        saved = addon.getSetting(SETTING) == candidate
    except Exception:
        saved = False
    if not saved:
        dialog.ok("Error guardando TMDb", "Kodi no ha confirmado el guardado de la clave. Comprueba los ajustes de AcTweeteR.")
        return "SAVE_FAILED"
    dialog.ok("TMDb configurado", "Clave validada y guardada en los ajustes locales de AcTweeteR. Reabre Smart Search para activar los alias.")
    return "CONFIGURED"


def offer_once(addon, vfs, dialog, *, requester=None):
    """Offer independently from core setup; recover a modal interrupted by restart."""
    path = marker(addon, vfs)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            state = {}
    except (OSError, ValueError):
        state = {}
    if valid_key(addon.getSetting(SETTING)):
        try:
            atomic_write(path, json.dumps({"version": VERSION, "result": "CONFIGURED"}).encode("utf-8"))
        except Exception:
            pass
        return "CONFIGURED"
    result = state.get("result")
    if state.get("version") == VERSION:
        if result in ("SKIPPED", "CONFIGURED", "INVALID", "CANCELLED", "UNVERIFIED",
                      "SAVE_FAILED"):
            return "ALREADY_OFFERED"
    # Failed/interrupted offers remain retryable in the same Kodi process.
    # The caller guards concurrent first-run wizard sessions.
    try:
        atomic_write(path, json.dumps({"version": VERSION, "result": "OFFERED"}).encode("utf-8"))
    except Exception:
        return "FAILED_RECOVERABLE"
    try:
        outcome = configure(addon, vfs, dialog, requester=requester)
    except Exception:
        outcome = "FAILED_RECOVERABLE"
    try:
        atomic_write(path, json.dumps({"version": VERSION, "result": outcome}).encode("utf-8"))
    except Exception:
        return "FAILED_RECOVERABLE"
    return outcome
