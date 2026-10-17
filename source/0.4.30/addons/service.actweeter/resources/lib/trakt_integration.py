"""Bridge to the official Trakt add-on; never owns or exports account tokens."""
from __future__ import annotations

from xml.etree import ElementTree as ET

AUTH_ACTION = "RunScript(script.trakt,action=auth_info)"
AUTH_WINDOW = "script-trakt-DeviceAuthDialog.xml"
STATUSES = frozenset(("NOT_STARTED", "WAITING_FOR_AUTHORIZATION",
                      "AUTHORIZATION_UNVERIFIED", "OAUTH_CONFIGURATION_REQUIRED",
                      "AUTHORIZED_RUNTIME", "AUTHORIZED_LOCAL", "DEFERRED", "UNAVAILABLE",
                      "UNSUPPORTED", "FAILED_RECOVERABLE"))
# No library-wide import/export, title-based guesses, PVR scrobbling, or removal
# of a user's remote collection is initiated by AcTweeteR.
SAFE_FRESH_DEFAULTS = {
    "scrobble_movie": "true", "scrobble_episode": "true",
    "scrobble_fallback": "false", "scrobble_secondary_title": "false",
    "scrobble_mythtv_pvr": "false", "sync_on_update": "false",
    "ExcludeLiveTV": "true",
    "last_reminder": "-1",
}


def supports_device_authorization(settings_xml):
    """Verify the action exported by the installed add-on's settings schema."""
    try:
        root = ET.fromstring(settings_xml)
    except (TypeError, ValueError, ET.ParseError):
        return False
    for setting in root.iter("setting"):
        if setting.get("id") != "Auth_Info":
            continue
        for data in setting.iter("data"):
            if "".join((data.text or "").split()) == AUTH_ACTION:
                return True
    return False


def mark_trakt_status(state, status, *, integration="script"):
    """Persist separate allowlisted states; never persist account credentials."""
    if status not in STATUSES or status == "AUTHORIZED_LOCAL":
        raise ValueError("unsupported Trakt status")
    keys = {"script": "script_trakt_status", "xstream": "xstream_trakt_status"}
    if integration not in keys:
        raise ValueError("unsupported Trakt integration")
    result = dict(state)
    result.setdefault("schema_version", 1)
    result[keys[integration]] = status
    return result


def configure_fresh_defaults(addon, *, newly_installed=False):
    """Do not alter settings of any add-on that predates this installation."""
    if not newly_installed:
        return False
    for key, value in SAFE_FRESH_DEFAULTS.items():
        addon.setSetting(key, value)
        if addon.getSetting(key) != value:
            raise RuntimeError("Trakt settings readback failed")
    return True
