"""Narrow, version-gated adapter for XStream Pro's native profile settings.

Credentials are accepted only in memory and written directly to XStream's own
Kodi settings after the user explicitly requests an authenticated connection.
This module never persists a second copy or logs input values.
"""

from __future__ import annotations

import json
import ast
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

MINIMUM_XSTREAM_VERSION = "1.1.2"
DEFAULT_XSTREAM_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
PROFILE_SETTINGS = {
    "profile_1_enabled": ("bool", "true"),
    "profile_1_source_type": ("labelenum", "Xtream Codes"),
    "profile_1_xtream_url": ("text", None),
    "profile_1_xtream_username": ("text", None),
    "profile_1_xtream_password": ("text", None),
    "profile_1_load_live": ("bool", "true"),
    "profile_1_load_movies": ("bool", "true"),
    "profile_1_load_series": ("bool", "true"),
}
REQUIRED_XSTREAM_DEPENDENCIES = {
    "xbmc.python": "3.0.1",
    "script.module.requests": "2.22.0",
    "pvr.iptvsimple": "21.4.0",
}


class SetupError(ValueError):
    """Safe-to-display error code; never includes submitted values."""


_VERSION = re.compile(
    r"^(\d+(?:\.\d+){2,3})(?:~(alpha|beta|rc)(\d+))?$", re.IGNORECASE)
_PRERELEASE_ORDER = {"alpha": 0, "beta": 1, "rc": 2}


def parse_xstream_version(value):
    """Parse Kodi dotted versions and order prereleases before the same release."""
    if not isinstance(value, str):
        return None
    match = _VERSION.fullmatch(value.strip())
    if not match:
        return None
    try:
        numbers = tuple(int(part) for part in match.group(1).split("."))
        stage = match.group(2)
        suffix = (3, 0) if stage is None else (
            _PRERELEASE_ORDER[stage.casefold()], int(match.group(3)))
    except (KeyError, ValueError):
        return None
    return numbers + (0,) * (4 - len(numbers)) + suffix


def xstream_version_satisfies(installed, minimum=MINIMUM_XSTREAM_VERSION):
    current = parse_xstream_version(installed)
    required = parse_xstream_version(minimum)
    return current is not None and required is not None and current >= required


def _mode_routes(tree):
    routes = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare) or len(node.ops) != 1 or not isinstance(node.ops[0], ast.Eq):
            continue
        if isinstance(node.left, ast.Name) and node.left.id == "mode":
            routes.update(item.value for item in node.comparators
                          if isinstance(item, ast.Constant) and isinstance(item.value, str))
    return routes


def _read_ast(path):
    with open(path, "r", encoding="utf-8") as source:
        return ast.parse(source.read())


def inspect_xstream_compatibility(path, version):
    """Verify the settings, declared dependencies and AcTweeteR routes we use.

    Returns ``(compatible, missing_capabilities)``; version is only a minimum
    gate, never a closed allowlist. The AST/XML checks protect future releases.
    """
    missing = []
    if not xstream_version_satisfies(version):
        missing.append("version>=1.1.2")
    root_path = str(path or "").rstrip("/\\")
    try:
        manifest = ET.parse(root_path + "/addon.xml").getroot()
        if manifest.get("id") != "plugin.video.xstream-pro" or manifest.get("version") != version:
            missing.append("addon_manifest_identity")
        imports = {node.get("addon"): node.get("version")
                   for node in manifest.findall("./requires/import")
                   if node.get("addon")}
        if any(not xstream_version_satisfies(
                imports.get(dependency, ""), minimum)
               for dependency, minimum in REQUIRED_XSTREAM_DEPENDENCIES.items()):
            missing.append("required_dependencies")
    except (OSError, ET.ParseError):
        missing.append("addon_manifest")
    try:
        settings = ET.parse(root_path + "/resources/settings.xml").getroot()
        found = {node.get("id"): node.get("type") for node in settings.iter("setting")
                 if node.get("id")}
        if any(found.get(key) != expected[0]
               for key, expected in PROFILE_SETTINGS.items()):
            missing.append("xtream_profile_settings")
    except (OSError, ET.ParseError):
        missing.append("xtream_profile_settings")
    try:
        addon_tree = _read_ast(root_path + "/resources/lib/addon.py")
        routes = _mode_routes(addon_tree)
        strings = {node.value for node in ast.walk(addon_tree)
                   if isinstance(node, ast.Constant) and isinstance(node.value, str)}
        if "actweeter_refresh_profile" not in routes:
            missing.append("profile_refresh_route")
        if ("actweeter_callback" not in strings
                or not any("catalog_refresh_result" in value for value in strings)):
            missing.append("catalog_refresh_callback")
    except (OSError, SyntaxError, UnicodeError):
        missing.append("xstream_dispatch_module")
    try:
        premium = _read_ast(root_path + "/resources/lib/premium_routes.py")
        functions = {node.name for node in premium.body
                     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        if not {"catalog", "metadata", "dispatch"} <= functions:
            missing.append("provider_widget_and_metadata_routes")
    except (OSError, SyntaxError, UnicodeError):
        missing.append("provider_widget_and_metadata_routes")
    try:
        changes = _read_ast(root_path + "/resources/lib/series_changes.py")
        functions = {node.name for node in changes.body
                     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        if not {"record_catalog", "record_series_info", "status"} <= functions:
            missing.append("series_change_events")
    except (OSError, SyntaxError, UnicodeError):
        missing.append("series_change_events")
    return not missing, tuple(missing)


def parse_xtream_input(server, username="", password=""):
    """Normalize a base URL or common Xtream get.php URL without leaking creds."""
    raw = (server or "").strip()
    if not raw or len(raw) > 2048:
        raise SetupError("SERVER_REQUIRED")
    try:
        parts = urllib.parse.urlsplit(raw)
        port = parts.port
    except ValueError:
        raise SetupError("SERVER_INVALID") from None
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        raise SetupError("SERVER_INVALID")
    if parts.fragment:
        raise SetupError("SERVER_INVALID")

    user = (username or "").strip()
    secret = password or ""
    query = urllib.parse.parse_qs(parts.query, keep_blank_values=True)
    if not user:
        user = (query.get("username") or [""])[0]
    if not secret:
        secret = (query.get("password") or [""])[0]
    if not user and parts.username:
        user = urllib.parse.unquote(parts.username)
    if not secret and parts.password:
        secret = urllib.parse.unquote(parts.password)
    if bool(user) != bool(secret):
        raise SetupError("CREDENTIALS_REQUIRED")

    path = parts.path.rstrip("/")
    lower_path = path.casefold()
    for suffix in ("/player_api.php", "/get.php", "/xmltv.php"):
        if lower_path.endswith(suffix):
            path = path[:-len(suffix)].rstrip("/")
            break
    host = parts.hostname.encode("idna").decode("ascii")
    if ":" in host and not host.startswith("["):
        host = "[" + host + "]"
    netloc = host + ((":" + str(port)) if port is not None else "")
    base = urllib.parse.urlunsplit((parts.scheme.lower(), netloc, path, "", ""))
    return base, user, secret


def _same_host_https_redirect(current_url, new_url):
    """Allow TLS redirects only when hostname and effective port are identical."""
    try:
        current = urllib.parse.urlsplit(current_url)
        target = urllib.parse.urlsplit(new_url)
        current_host = current.hostname.encode("idna").decode("ascii").casefold()
        target_host = target.hostname.encode("idna").decode("ascii").casefold()
        current_port = current.port
        target_port = target.port
    except (AttributeError, UnicodeError, ValueError):
        return False
    if (current.scheme not in ("http", "https") or target.scheme != "https"
            or current_host != target_host or target.username or target.password
            or target.fragment):
        return False
    current_effective_port = current_port or (443 if current.scheme == "https" else 80)
    target_effective_port = target_port or 443
    return current_effective_port == target_effective_port


class _SameHostHttpsRedirect(urllib.request.HTTPRedirectHandler):
    max_repeats = 3
    max_redirections = 3

    def redirect_request(self, request, response, code, message, headers, newurl):
        if not _same_host_https_redirect(request.full_url, newurl):
            return None
        return super().redirect_request(
            request, response, code, message, headers, newurl)


def prepare_https_endpoint(server, *, timeout=10, opener_factory=None):
    """Probe HTTP providers without credentials and return a verified HTTPS base.

    Returns ("HTTPS_READY", base) only after a no-credential request reached
    the same hostname and effective port over verified TLS. A provider that
    does not offer that exact endpoint returns ("HTTP_ONLY", None). Unsafe
    redirects fail closed. No response URL, body, or exception text escapes.
    """
    base, _, _ = parse_xtream_input(server)
    parts = urllib.parse.urlsplit(base)
    if parts.scheme == "https":
        return "HTTPS_READY", base
    if parts.scheme != "http":
        return "HTTPS_UNAVAILABLE", None
    endpoint = base.rstrip("/") + "/player_api.php"
    opener = (opener_factory or urllib.request.build_opener)(
        _SameHostHttpsRedirect())
    request = urllib.request.Request(
        endpoint, headers={"Accept": "application/json"})
    try:
        with opener.open(request, timeout=max(1, min(int(timeout), 15))) as response:
            final = urllib.parse.urlsplit(response.geturl())
            original_port = parts.port or 80
            final_port = final.port or (443 if final.scheme == "https" else 80)
            host = parts.hostname.encode("idna").decode("ascii").casefold()
            final_host = final.hostname.encode("idna").decode("ascii").casefold()
            if (final_host != host
                    or final_port != original_port or final.username
                    or final.password or final.query or final.fragment
                    or not final.path.casefold().endswith("/player_api.php")):
                return "HTTPS_UNAVAILABLE", None
            if final.scheme == "http":
                return "HTTP_ONLY", None
            if final.scheme != "https" or response.getcode() != 200:
                return "HTTPS_UNAVAILABLE", None
            secure_path = final.path[:-len("/player_api.php")].rstrip("/")
            final_netloc = final.hostname
            if ":" in final_netloc and not final_netloc.startswith("["):
                final_netloc = "[" + final_netloc + "]"
            if final.port is not None:
                final_netloc += ":" + str(final.port)
            secure_base = urllib.parse.urlunsplit(
                ("https", final_netloc, secure_path, "", ""))
            return "HTTPS_READY", secure_base
    except urllib.error.HTTPError as exc:
        # HTTPError may be raised by a lightweight opener/test double without
        # an underlying response file. Closing such an error can itself raise
        # (notably on Python 3.9); close only when a response body exists.
        if getattr(exc, "fp", None) is not None:
            exc.close()
        return ("REDIRECT_REFUSED" if 300 <= exc.code < 400
                else "HTTPS_UNAVAILABLE"), None
    except (OSError, TimeoutError, urllib.error.URLError, ValueError,
            UnicodeError):
        return "HTTPS_UNAVAILABLE", None


def validate_xtream_credentials(server, username, password, *, timeout=10,
                                opener_factory=None,
                                https_probe_opener_factory=None,
                                allow_insecure=False, user_agent=None):
    """Probe the entered Xtream account at its server; return a safe result code.

    Redirects are deliberately refused so credentials cannot be forwarded to a
    different host. No response body, URL, or exception message is returned.
    """
    base, user, secret = parse_xtream_input(server, username, password)
    if not user or not secret:
        raise SetupError("CREDENTIALS_REQUIRED")
    if urllib.parse.urlsplit(base).scheme == "http":
        transport, secure_base = prepare_https_endpoint(
            base, timeout=timeout,
            opener_factory=https_probe_opener_factory)
        if transport == "HTTPS_READY":
            base = secure_base
        elif transport != "HTTP_ONLY" or not allow_insecure:
            return transport
    query = urllib.parse.urlencode({"username": user, "password": secret})
    endpoint = base + "/player_api.php?" + query
    agent = str(user_agent or DEFAULT_XSTREAM_USER_AGENT).strip()
    if not agent or "\r" in agent or "\n" in agent:
        agent = DEFAULT_XSTREAM_USER_AGENT
    opener = (opener_factory or urllib.request.build_opener)(
        _SameHostHttpsRedirect())
    request = urllib.request.Request(endpoint, headers={
        "Accept": "*/*", "User-Agent": agent,
    })
    try:
        with opener.open(request, timeout=max(1, min(int(timeout), 15))) as response:
            if response.getcode() != 200:
                return "SERVER_REJECTED"
            payload = response.read(1024 * 1024)
    except urllib.error.HTTPError as exc:
        if getattr(exc, "fp", None) is not None:
            exc.close()
        return "REDIRECT_REFUSED" if 300 <= exc.code < 400 else "SERVER_REJECTED"
    except (OSError, TimeoutError, urllib.error.URLError, ValueError):
        return "SERVER_UNAVAILABLE"
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, TypeError):
        return "INVALID_RESPONSE"
    if not isinstance(data, dict):
        return "INVALID_RESPONSE"
    user_info = data.get("user_info")
    if not isinstance(user_info, dict):
        return "INVALID_RESPONSE"
    if str(user_info.get("auth", "")) not in ("1", "true", "True"):
        return "INVALID_CREDENTIALS"
    if str(user_info.get("status", "")).strip().casefold() in {
            "expired", "disabled", "banned"}:
        return "ACCOUNT_UNAVAILABLE"
    return "AUTHENTICATED"


def _settings_schema(addon, translated_addon_path=None):
    if not xstream_version_satisfies(addon.getAddonInfo("version")):
        raise SetupError("XSTREAM_VERSION_BELOW_MINIMUM")
    path = translated_addon_path or addon.getAddonInfo("path")
    settings_path = path.rstrip("/\\") + "/resources/settings.xml"
    try:
        root = ET.parse(settings_path).getroot()
    except (OSError, ET.ParseError) as exc:
        raise SetupError("XSTREAM_SCHEMA_UNAVAILABLE") from exc
    found = {}
    for setting in root.iter("setting"):
        setting_id = setting.get("id")
        if setting_id:
            found[setting_id] = setting.get("type")
    for setting_id, (expected_type, _) in PROFILE_SETTINGS.items():
        if found.get(setting_id) != expected_type:
            raise SetupError("XSTREAM_SCHEMA_MISMATCH")


def save_native_profile(addon, server, username, password, *,
                         translated_addon_path=None):
    """Write only the verified Profile 1 fields in XStream's own settings."""
    base, user, secret = parse_xtream_input(server, username, password)
    if not user or not secret:
        raise SetupError("CREDENTIALS_REQUIRED")
    _settings_schema(addon, translated_addon_path)
    values = {
        "profile_1_enabled": True,
        "profile_1_source_type": "Xtream Codes",
        "profile_1_xtream_url": base,
        "profile_1_xtream_username": user,
        "profile_1_xtream_password": secret,
        "profile_1_load_live": True,
        "profile_1_load_movies": True,
        "profile_1_load_series": True,
    }
    settings = addon.getSettings()
    def read(key):
        return settings.getBool(key) if PROFILE_SETTINGS[key][0] == "bool" else settings.getString(key)

    def write(key, value):
        return settings.setBool(key, value) if PROFILE_SETTINGS[key][0] == "bool" else settings.setString(key, value)

    try:
        previous = {key: read(key) for key in values}
    except Exception:
        raise SetupError("XSTREAM_SETTINGS_READ_FAILED") from None
    written = []
    try:
        for key, value in values.items():
            written.append(key)
            if write(key, value) is False:
                raise SetupError("XSTREAM_SETTINGS_WRITE_FAILED")
        if any(read(key) != value for key, value in values.items()):
            raise SetupError("XSTREAM_SETTINGS_VERIFY_FAILED")
    except Exception as exc:  # normalize Kodi bridge errors without exposing values.
        rollback_failed = False
        for key in reversed(written):
            try:
                if write(key, previous[key]) is False:
                    rollback_failed = True
            except Exception:  # noqa: BLE001 - preserve fail-closed result without logging values.
                rollback_failed = True
        if rollback_failed:
            raise SetupError("XSTREAM_SETTINGS_ROLLBACK_FAILED") from None
        if isinstance(exc, SetupError):
            raise
        raise SetupError("XSTREAM_SETTINGS_WRITE_FAILED") from None
    return "SAVED_TO_XSTREAM"
