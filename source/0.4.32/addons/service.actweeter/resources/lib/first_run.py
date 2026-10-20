"""Secret-free first-run and service-status primitives for AcTweeteR."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from trakt_integration import STATUSES as TRAKT_STATUSES


WIZARD_STEPS = (
    "Bienvenida",
    "Preparar componentes automáticamente",
    "Conectar proveedor IPTV",
    "Autorizaciones externas",
    "Configurar y verificar servicios",
    "Finalizar configuración",
)
LEGACY_WIZARD_STEPS = {
    "Configurar SlyGuy Trailers (opcional)",
    "Configurar YouTube (opcional)",
    "Configurar IPTV / XStream",
    "Conectar proveedor IPTV / XStream",
    "Configurar TV / PVR",
    "Preparar tráilers (obligatorio)",
    "Configurar YouTube (obligatorio)",
    "Comprobar componentes",
    "Elegir introducción",
    "Completar instalación de complementos",
}
INTRO_OPTIONS = (
    ("Vídeo AcTweeteR", "actweeter_video"),
    ("Imagen AcTweeteR", "actweeter_image"),
    ("Sin introducción", "none"),
)
STEP_STATUSES = {"IN_PROGRESS", "RETURNED", "REVIEWED", "DONE", "SKIPPED"}
WIZARD_VERSION = 8
COMPONENT_OFFER_VERSION = "0.4.24"
XSTREAM_TVOS_MIN_PVR_VERSION = (21, 4, 0)
REQUIRED_EXTERNAL_ADDON_MINIMUMS = {
    "plugin.video.xstream-pro": "1.1.2",
    "pvr.iptvsimple": "21.4.0",
}

SETUP_STATES = {
    "NOT_STARTED", "INSTALLING_ADDONS", "ADDONS_READY", "WAITING_FOR_PROVIDER",
    "CONFIGURING_PROVIDER", "PROVIDER_READY", "CONFIGURING_TRAILERS",
    "TRAILERS_READY", "CONFIGURING_INTERFACE", "VERIFYING", "COMPLETE",
    "INCOMPLETE", "FAILED_RECOVERABLE",
}
SETUP_CHECK_STATUSES = {
    "PASS_RUNTIME", "PASS_AUTOMATED", "PASS_STATIC", "NOT_PROVIDED_RUNTIME",
    "FAIL", "BLOCKED", "NOT_TESTED",
}
# Completion gates describe an installed and configured core, not playback QA.
# Playback/search/visual-surface checks remain reportable but never block setup.
# EPG is optional: a provider may not supply guide data.
MANDATORY_SETUP_CHECKS = (
    "mandatory_addons", "provider_authentication", "movies_catalog",
    "series_catalog", "live_tv_ready", "pvr_configuration",
)
OPTIONAL_SETUP_CHECKS = (
    "epg_ready_or_not_provided", "trailer_addon_ready", "trailer_search",
    "trailer_resolution", "trailer_playback", "home_widgets", "spotlight", "search",
    "script_trakt_authorization", "xstream_trakt_authorization",
)
ALL_SETUP_CHECKS = frozenset(MANDATORY_SETUP_CHECKS + OPTIONAL_SETUP_CHECKS)

OPTIONAL_ADDONS = {
    "xstream": "plugin.video.xstream-pro",
    "pvr": "pvr.iptvsimple",
    "slyguy": "slyguy.trailers",
    "youtube": "plugin.video.youtube",
    "trakt": "script.trakt",
    "metadata": "plugin.video.tmdb.bingie.helper",
}
REQUIRED_ADDON_IDS = (
    "service.actweeter",
    "script.bingie.helper",
    "script.bingie.toolbox",
    "script.bingie.widgets",
    "script.skinshortcuts",
    "resource.images.studios.coloured",
    "plugin.video.tmdb.bingie.helper",
    "plugin.program.autocompletion",
    # Kodi's official YouTube add-on backs the skin's explicit fallback and
    # search actions. Installation is required; Google account/API setup is not.
    "plugin.video.youtube",
)

# Kodi installs an add-on only from repositories already present and enabled
# on that installation. YouTube is sourced from Kodi's built-in official repo;
# Google authorization remains separate from installing/enabling the add-on.
SLYGUY_INSTALL_SEQUENCE = (
    ("repository.slyguy", "0.0.9", "repository.actweeter"),
    ("slyguy.dependencies", "0.0.30", "repository.slyguy"),
    ("script.module.slyguy", "0.86.96", "repository.slyguy"),
    ("slyguy.trailers", "0.2.1", "repository.slyguy"),
)


def repository_candidates(sources):
    """Accept either installed AcTweeteR channel; never install/switch channels."""
    result = []
    for source in sources:
        for candidate in (("repository.actweeter.testing", "repository.actweeter")
                          if source == "repository.actweeter" else (source,)):
            if candidate not in result:
                result.append(candidate)
    return tuple(result)

# Kodi's repository resolver searches every enabled repository. These IDs are
# the authoritative repositories exposed by AcTweeteR 1.0.3 (Matke Omega and
# SlyGuy catalogs) and Kodi's built-in catalog; no user-added source is assumed.
# Compatibility names above remain for existing maintenance entry points.
# The catalog, rather than a second handwritten list, is authoritative.
from module_catalog import all_addons, installation_plan, repository_sources
REQUIRED_REPAIR_SOURCES = repository_sources()
OPTIONAL_ADDON_SOURCES = {
    key: all_addons()[addon_id]["repositories"][0]
    for key, addon_id in OPTIONAL_ADDONS.items()
    if all_addons().get(addon_id, {}).get("repositories")
}
from module_catalog import CATALOG_VERSION
REQUIRED_ADDON_IDS = tuple(
    addon_id for addon_id, item in all_addons().items()
    if item.get("required", True)
)
REQUIRED_EXTERNAL_ADDON_MINIMUMS = {
    addon_id: item["minimum"] for addon_id, item in all_addons().items()
    if item.get("required", True) and item["minimum"]
}


def optional_addon_action(key, addon_installed, source_installed, *, tvos=False,
                          addon_enabled=None):
    """Choose a safe wizard action without attempting an absent add-on."""
    addon_id = OPTIONAL_ADDONS.get(key)
    if not addon_id or key == "metadata":
        return "UNSUPPORTED"
    if addon_installed:
        return "CONFIGURE" if addon_enabled is not False else "ENABLE"
    # Do not attempt to fetch a tvOS native binary through a generic repo flow.
    # The signed Kodi build may already expose an integrated PVR add-on; callers
    # must inspect the installed ID and version before enabling dependent XStream.
    if tvos and key == "pvr":
        return "PLATFORM_UNAVAILABLE"
    source_id = OPTIONAL_ADDON_SOURCES.get(key)
    if not source_id:
        return "SOURCE_REQUIRED"
    if not source_installed:
        return "REPOSITORY_REQUIRED"
    return "OFFER_INSTALL"


def tvos_xstream_dependency_status(pvr_installed, pvr_enabled, pvr_version):
    """Fail-closed gate for XStream on tvOS, based on Kodi's actual PVR addon."""
    if not pvr_installed:
        return "PVR_MISSING"
    if not pvr_enabled:
        return "PVR_DISABLED"
    version = parse_addon_version(pvr_version)
    if version is None:
        return "PVR_VERSION_UNKNOWN"
    if version < XSTREAM_TVOS_MIN_PVR_VERSION:
        return "PVR_VERSION_INSUFFICIENT"
    return "READY"


def parse_addon_version(value):
    """Parse Kodi's leading dotted numeric version without guessing suffixes."""
    if not isinstance(value, str):
        return None
    match = re.match(r"^(\d+(?:\.\d+)*)(?:$|[+~_-])", value.strip())
    if not match:
        return None
    try:
        parts = tuple(int(part) for part in match.group(1).split("."))
    except ValueError:
        return None
    return parts + (0,) * max(0, 3 - len(parts))


def addon_version_satisfies(installed, minimum):
    """Return false for unknown/invalid version strings; never guess compatibility."""
    current = parse_addon_version(installed)
    required = parse_addon_version(minimum)
    if current is None or required is None:
        return False
    width = max(len(current), len(required))
    return (current + (0,) * (width - len(current))) >= (required + (0,) * (width - len(required)))


def poll_runtime_state(probe, is_ready, wait, monotonic, *, timeout, interval):
    """Poll an external runtime state without blocking its host event loop.

    ``wait`` is supplied by the host (Kodi's Monitor.waitForAbort in product
    code), so callers yield while Kodi initializes rather than sleeping on the
    UI path. A timeout bounds the operation; only the observed predicate can
    produce READY.
    """
    timeout = max(0.0, float(timeout))
    interval = max(0.01, float(interval))
    deadline = monotonic() + timeout
    last = None
    while True:
        last = probe()
        if is_ready(last):
            return "READY", last
        remaining = deadline - monotonic()
        if remaining <= 0:
            return "TIMEOUT", last
        if wait(min(interval, remaining)):
            return "ABORTED", last


def should_offer_component_completion(state, missing_addons, core_configured=False):
    """Offer once per service/catalog version when required packages are missing."""
    state = state or {}
    release_offer_due = state.get("component_offer_version") != COMPONENT_OFFER_VERSION
    catalog_offer_due = state.get("component_catalog_offer_version") != CATALOG_VERSION
    return bool(
        (state.get("completed") or state.get("prompted") or core_configured)
        and missing_addons
        and (release_offer_due or catalog_offer_due)
    )


def mark_component_offer_seen(state):
    result = normalize_state(state)
    result["component_offer_version"] = COMPONENT_OFFER_VERSION
    result["component_catalog_offer_version"] = CATALOG_VERSION
    return result


def mark_catalog_reconciled(state):
    """Record the catalog only after Kodi confirms every required package ready."""
    result = normalize_state(state)
    result["component_catalog_version"] = CATALOG_VERSION
    result["component_catalog_offer_version"] = CATALOG_VERSION
    result["component_offer_version"] = COMPONENT_OFFER_VERSION
    return result


def home_diagnostic_snapshot(*, window_id, focus_id, menu_visible,
                             widgets_count, widgets_updating, startup_mask,
                             intro_playback, missing_required_count):
    """Allowlist non-personal Home health fields for one-shot diagnostics."""
    def safe_int(value):
        try:
            number = int(value)
            return number if number >= 0 else -1
        except (TypeError, ValueError):
            return -1

    def safe_bool(value):
        if isinstance(value, str):
            return value.strip().casefold() in ("1", "true", "yes", "on")
        return bool(value)

    return {
        "window_id": safe_int(window_id),
        "focus_id": safe_int(focus_id),
        "menu_visible": safe_bool(menu_visible),
        "widgets_count": safe_int(widgets_count),
        "widgets_updating": safe_bool(widgets_updating),
        "startup_mask": safe_bool(startup_mask),
        "intro_playback": safe_bool(intro_playback),
        "missing_required_count": safe_int(missing_required_count),
    }


def has_xtream_configuration(addon):
    """Check presence only; never return, persist, or log credential values."""
    try:
        profile = addon.getSetting("active_pvr_profile") or "Profile 1"
        digits = "".join(char for char in profile if char.isdigit())
        number = int(digits or "1")
        if not 1 <= number <= 10:
            return False
        prefix = "profile_%d_" % number
        return (
            addon.getSetting(prefix + "enabled").casefold() == "true"
            and all(addon.getSetting(prefix + key).strip()
                    for key in ("xtream_url", "xtream_username", "xtream_password"))
        )
    except Exception:
        return False


def service_rows(installed, pvr=None, xstream_configured=None):
    """Return safe UI rows; values contain status only, never provider data."""
    installed = installed or {}
    rows = []
    required_present = bool(installed.get("required", False))
    rows.append({
        "service": "Componentes obligatorios de AcTweeteR",
        "status": "AVAILABLE" if required_present else "MISSING",
        "optional": False,
    })
    for key, label, optional in (
        ("xstream", "IPTV / XStream", False),
        ("pvr", "TV / PVR", False),
        ("slyguy", "SlyGuy Trailers", True),
        ("youtube", "YouTube (fallback y búsqueda; autorización según uso)", False),
        ("trakt", "Trakt", True),
        ("metadata", "Metadatos (dependencia de skin)", False),
    ):
        present = bool(installed.get(key, False))
        status = "INSTALLED_NOT_CHECKED" if present else ("OPTIONAL_MISSING" if optional else "MISSING")
        if key == "xstream" and present and xstream_configured is not None:
            status = "CONFIGURED" if xstream_configured else "SETUP_REQUIRED"
        if key == "pvr" and present and pvr is not None:
            if pvr.get("error"):
                status = "ERROR"
            elif pvr.get("scanning"):
                status = "INITIALIZING_OR_UNAVAILABLE"
            elif pvr.get("available"):
                status = "AVAILABLE"
            else:
                status = "INITIALIZING_OR_UNAVAILABLE"
        rows.append({"service": label, "status": status, "optional": optional})
    slyguy_present = bool(installed.get("slyguy", False))
    rows.append({
        "service": "Previews automáticos",
        "status": "INTEGRATION_NOT_CHECKED_NOW" if slyguy_present else "OPTIONAL_MISSING",
        "optional": True,
    })
    rows.append({
        "service": "OAuth Google",
        "status": "NOT_REQUIRED_FOR_SLYGUY",
        "optional": True,
    })
    return rows


def should_offer_first_run(state, core_configured):
    """Offer onboarding until the strict setup contract is actually complete."""
    state = state or {}
    # An already-configured Master upgraded from an older wizard should not
    # be taken hostage by a new automatic modal. Its new runtime checks remain
    # INCOMPLETE and explicitly available via Settings/repair, not marked PASS.
    if core_configured and (state.get("legacy_completed_review")
                            or state.get("configured_onboarding_declined")):
        # A conscious "not now" on an already-configured device persists;
        # incomplete mandatory checks remain incomplete.
        return False
    if (state.get("completed") and state.get("setup_state") == "COMPLETE"
            and state.get("wizard_version", 1) >= WIZARD_VERSION
            and not completion_blockers(state)):
        return False
    # A deferral suppresses the modal only for the Kodi process in which the
    # user chose it. Legacy prompted=true states have no process scope and are
    # re-offered once so an interrupted/obscured first run cannot be lost.
    return True


def should_offer_first_run_in_process(state, core_configured, process_id):
    """Offer incomplete setup on a new Kodi process, not repeatedly per Home load."""
    state = state or {}
    deferred_for = state.get("deferred_process_id")
    if (state.get("prompted") and deferred_for == process_id
            and isinstance(process_id, int) and not isinstance(process_id, bool)):
        return False
    return should_offer_first_run(state, core_configured)


def intro_mode_for_selection(selection):
    """Map a Kodi dialog index to a supported mode; cancellation is no choice."""
    if type(selection) is not int or not 0 <= selection < len(INTRO_OPTIONS):
        return None
    return INTRO_OPTIONS[selection][1]


def claim_process_session(path, process_id, claim_key=None):
    """Atomically claim one process-scoped startup action across Home loads.

    Failure to persist is fail-closed: skipping a cosmetic intro is safer than
    starting it twice or leaving a second modal over the Home screen. A caller
    may supply a non-sensitive claim key when a changed input fingerprint must
    be retried within the same Kodi process.
    """
    if isinstance(process_id, bool) or not isinstance(process_id, int) or process_id <= 0:
        return False
    destination = Path(path)
    lock = destination.with_name(destination.name + ".claim-" + str(process_id))
    lock_fd = None
    temporary = None
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        lock_fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except (FileExistsError, OSError):
        return False

    try:
        try:
            previous = json.loads(destination.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            previous = None
        if (isinstance(previous, dict) and previous.get("schema_version") == 1 and
                previous.get("process_id") == process_id and
                previous.get("claim_key") == claim_key):
            return False

        descriptor, temporary_name = tempfile.mkstemp(
            prefix=destination.name + ".tmp-", dir=str(destination.parent))
        temporary = Path(temporary_name)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump({"schema_version": 1, "process_id": process_id,
                       "claim_key": claim_key}, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except OSError:
        return False
    finally:
        if lock_fd is not None:
            os.close(lock_fd)
        for transient in (temporary, lock):
            if transient is not None:
                try:
                    transient.unlink()
                except OSError:
                    pass
    return True


def release_process_session(path, process_id):
    """Release only this process's claim when startup UI had to be deferred."""
    destination = Path(path)
    try:
        claimed = json.loads(destination.read_text(encoding="utf-8"))
        if (isinstance(claimed, dict) and claimed.get("schema_version") == 1
                and claimed.get("process_id") == process_id):
            destination.unlink()
            return True
    except (OSError, ValueError, TypeError):
        pass
    return False


def claim_intro_for_process(path, process_id):
    """Compatibility name for the process-scoped intro claim."""
    return claim_process_session(path, process_id)


def normalize_state(state):
    """Reject malformed or unsupported wizard state without interrupting Kodi."""
    if not isinstance(state, dict) or state.get("schema_version") != 1:
        return {}
    result = {"schema_version": 1, "wizard_version": 1}
    version = state.get("wizard_version")
    if isinstance(version, int) and not isinstance(version, bool) and 1 <= version <= WIZARD_VERSION:
        result["wizard_version"] = version
    for key in ("prompted", "completed", "started", "legacy_completed_review",
                "configured_onboarding_declined"):
        if isinstance(state.get(key), bool):
            result[key] = state[key]
    deferred_process_id = state.get("deferred_process_id")
    if (isinstance(deferred_process_id, int) and not isinstance(deferred_process_id, bool)
            and deferred_process_id > 0):
        result["deferred_process_id"] = deferred_process_id
    offer_version = state.get("component_offer_version")
    if isinstance(offer_version, str) and len(offer_version) <= 24:
        result["component_offer_version"] = offer_version
    for key in ("component_catalog_version", "component_catalog_offer_version"):
        catalog_version = state.get(key)
        if (isinstance(catalog_version, int) and not isinstance(catalog_version, bool)
                and 0 <= catalog_version <= CATALOG_VERSION):
            result[key] = catalog_version
    if state.get("last_step") in WIZARD_STEPS or state.get("last_step") in LEGACY_WIZARD_STEPS:
        result["last_step"] = state["last_step"]
    index = state.get("last_step_index")
    if isinstance(index, int) and not isinstance(index, bool) and 0 <= index < len(WIZARD_STEPS):
        result["last_step_index"] = index
    raw_steps = state.get("step_status")
    if isinstance(state.get("trakt_status"), str) and state["trakt_status"] in TRAKT_STATUSES:
        # Older releases inferred this label by reading script.trakt's private
        # token setting. Preserve progress, but never treat that inference as
        # proof that either integration is authorized.
        trakt_status = state["trakt_status"]
        if trakt_status == "AUTHORIZED_LOCAL":
            trakt_status = "AUTHORIZATION_UNVERIFIED"
        result["script_trakt_status"] = trakt_status
    for key in ("script_trakt_status", "xstream_trakt_status"):
        value = state.get(key)
        if isinstance(value, str) and value in TRAKT_STATUSES:
            if value == "AUTHORIZED_LOCAL":
                value = "AUTHORIZATION_UNVERIFIED"
            result[key] = value
    if isinstance(raw_steps, dict):
        result["step_status"] = {
            key: value for key, value in raw_steps.items()
            if isinstance(key, str) and (key in WIZARD_STEPS or key in LEGACY_WIZARD_STEPS)
            and isinstance(value, str) and value in STEP_STATUSES
        }
    else:
        result["step_status"] = {}
    config_status = state.get("configuration_status")
    if config_status in ("CORE_READY", "PARTIALLY_CONFIGURED", "CONFIGURATION_REQUIRED", "INCOMPLETE"):
        result["configuration_status"] = config_status
    setup_state = state.get("setup_state")
    if isinstance(setup_state, str) and setup_state in SETUP_STATES:
        result["setup_state"] = setup_state
    raw_checks = state.get("setup_checks")
    if isinstance(raw_checks, dict):
        result["setup_checks"] = {
            key: value for key, value in raw_checks.items()
            if isinstance(key, str) and key in ALL_SETUP_CHECKS
            and isinstance(value, str) and value in SETUP_CHECK_STATUSES
        }
    else:
        result["setup_checks"] = {}
    if (result.get("completed") and any(
            result["setup_checks"].get(key) != "PASS_RUNTIME"
            for key in MANDATORY_SETUP_CHECKS)):
        if result["wizard_version"] < WIZARD_VERSION:
            result["legacy_completed_review"] = True
        result.update(completed=False, prompted=False, setup_state="INCOMPLETE",
                      configuration_status="INCOMPLETE")
    elif result.get("completed") and result["wizard_version"] < WIZARD_VERSION:
        # A wizard-version bump alone must not make a previously complete core
        # installation repeat onboarding (e.g. optional Trakt/UI additions).
        # Core checks are validated above; optional authorizations are ignored.
        result["wizard_version"] = WIZARD_VERSION
    return result


def load_state(path):
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            return normalize_state(json.load(handle))
    except (OSError, ValueError, TypeError):
        return {}


def save_state(path, state):
    """Atomically persist only allowlisted, non-secret wizard state."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    sanitized = normalize_state(state)
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(sanitized, handle, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, destination)
    return sanitized


def mark_prompted(state):
    result = normalize_state(state)
    result.update({"schema_version": 1, "wizard_version": WIZARD_VERSION, "prompted": True})
    return result


def mark_started(state):
    result = normalize_state(state)
    result.update({"schema_version": 1, "wizard_version": WIZARD_VERSION,
                   "prompted": False, "started": True, "setup_state": "INSTALLING_ADDONS",
                   "completed": False, "configuration_status": "INCOMPLETE"})
    result.pop("deferred_process_id", None)
    result.pop("configured_onboarding_declined", None)
    return result


def mark_deferred(state, process_id, *, core_configured=False):
    """Persist a resumable first-run deferral scoped to this Kodi process."""
    result = normalize_state(state)
    result.update({"schema_version": 1, "wizard_version": WIZARD_VERSION,
                   "prompted": True, "completed": False})
    if core_configured is True:
        result["configured_onboarding_declined"] = True
    if isinstance(process_id, int) and not isinstance(process_id, bool) and process_id > 0:
        result["deferred_process_id"] = process_id
    else:
        result.pop("deferred_process_id", None)
    return result


def mark_step(state, step, status):
    result = normalize_state(state)
    if not isinstance(step, str) or (step not in WIZARD_STEPS
                                     and step not in LEGACY_WIZARD_STEPS):
        return result
    if not isinstance(status, str) or status not in STEP_STATUSES:
        return result
    result.update({"schema_version": 1, "wizard_version": WIZARD_VERSION, "last_step": step})
    steps = dict(result.get("step_status", {}))
    steps[str(step)] = str(status)
    result["step_status"] = steps
    if status == "IN_PROGRESS":
        result["setup_state"] = {
            "Preparar componentes automáticamente": "INSTALLING_ADDONS",
            "Conectar proveedor IPTV": "CONFIGURING_PROVIDER",
            "Autorizaciones externas": "CONFIGURING_TRAILERS",
            "Configurar y verificar servicios": "VERIFYING",
            "Finalizar configuración": "VERIFYING",
            "Reparar componentes": "INSTALLING_ADDONS",
            "Comprobar componentes": "INSTALLING_ADDONS",
            "Completar instalación de complementos": "INSTALLING_ADDONS",
            "Configurar IPTV / XStream": "CONFIGURING_PROVIDER",
            "Conectar proveedor IPTV / XStream": "CONFIGURING_PROVIDER",
            "Configurar TV / PVR": "CONFIGURING_PROVIDER",
            "Preparar tráilers (obligatorio)": "CONFIGURING_TRAILERS",
            "Configurar YouTube (obligatorio)": "CONFIGURING_TRAILERS",
        }.get(step, "CONFIGURING_INTERFACE")
    elif not result.get("completed"):
        result["setup_state"] = "INCOMPLETE"
    return result


def mark_setup_check(state, check, status):
    """Persist one allowlisted verification result without sensitive payloads."""
    result = normalize_state(state)
    if (not isinstance(check, str) or check not in ALL_SETUP_CHECKS
            or not isinstance(status, str) or status not in SETUP_CHECK_STATUSES):
        return result
    checks = dict(result.get("setup_checks", {}))
    checks[check] = status
    result["setup_checks"] = checks
    result["schema_version"] = 1
    result["wizard_version"] = WIZARD_VERSION
    if check in MANDATORY_SETUP_CHECKS:
        result["setup_state"] = "VERIFYING"
        result["completed"] = False
        result["prompted"] = False
        result["configuration_status"] = "INCOMPLETE"
    return result


def completion_blockers(state):
    """Return mandatory checks lacking acceptable real runtime evidence."""
    checks = normalize_state(state).get("setup_checks", {})
    blockers = []
    for check in MANDATORY_SETUP_CHECKS:
        status = checks.get(check)
        if status != "PASS_RUNTIME":
            blockers.append(check)
    return tuple(blockers)


def mark_completed(state, configuration_status=None):
    """Complete only when core install/configuration gates have runtime proof."""
    result = normalize_state(state)
    result["setup_state"] = "VERIFYING"
    if completion_blockers(result):
        result.update({"schema_version": 1, "wizard_version": WIZARD_VERSION,
                       "prompted": False, "completed": False,
                       "setup_state": "INCOMPLETE", "configuration_status": "INCOMPLETE"})
        return result
    result.update({"schema_version": 1, "wizard_version": WIZARD_VERSION,
                   "prompted": True, "completed": True,
                   "setup_state": "COMPLETE", "configuration_status": "CORE_READY"})
    result.pop("deferred_process_id", None)
    return result
