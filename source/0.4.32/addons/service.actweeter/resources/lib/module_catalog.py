"""Declarative AcTweeteR module catalog for Kodi-managed components.

This catalog records provenance and lifecycle policy; it never downloads or
redistributes third-party packages itself. Kodi's repositories remain the
installer and update authority.
"""

from __future__ import annotations

import re


CATALOG_VERSION = 18
ALL_TARGET_PLATFORMS = ("macos", "windows", "linux", "android", "tvos")

MODULES = (
    {
        "id": "core",
        "name": "AcTweeteR Core",
        "required": True,
        "addons": (
            {"id": "skin.actweeter", "minimum": "1.2.8", "source": "repository.actweeter",
             "license": "GPL-2.0-or-later", "platforms": ALL_TARGET_PLATFORMS,
             "dependencies": ("service.actweeter", "script.bingie.helper", "script.bingie.toolbox",
                              "script.bingie.widgets", "script.skinshortcuts"),
             "configuration": "Skin shortcuts and user preferences",
             "update": "Kodi add-on repository automatic updates",
             "recovery": "Kodi reinstall/update; preserve Kodi userdata"},
            {"id": "service.actweeter", "minimum": "0.4.23", "source": "repository.actweeter",
             "license": "GPL-2.0-or-later", "platforms": ALL_TARGET_PLATFORMS,
             "dependencies": ("plugin.video.xstream-pro", "pvr.iptvsimple", "plugin.video.youtube"),
             "configuration": "Resumable setup state in add-on profile; Trakt account authorization remains user-owned",
             "update": "Kodi add-on repository automatic updates",
             "recovery": "Rerun AcTweeteR setup/repair"},
            {"id": "xbmc.gui", "minimum": "5.17.0", "source": "Kodi application",
             "license": "Kodi upstream", "platforms": ALL_TARGET_PLATFORMS,
             "dependencies": (), "configuration": "Provided by Kodi; not independently configured",
             "update": "Kodi application update", "recovery": "Update/reinstall compatible Kodi build"},
            {"id": "script.bingie.helper", "minimum": "1.1.2", "source": "repository.actweeter / Matke Omega",
             "license": "upstream metadata", "platforms": ALL_TARGET_PLATFORMS,
             "dependencies": (), "configuration": "Skin helper actions",
             "update": "Original repository catalog", "recovery": "Kodi native reinstall"},
            {"id": "script.bingie.toolbox", "minimum": "1.0.0", "source": "repository.actweeter / Matke Omega",
             "license": "upstream metadata", "platforms": ALL_TARGET_PLATFORMS,
             "dependencies": (), "configuration": "Skin tools and shortcuts",
             "update": "Original repository catalog", "recovery": "Kodi native reinstall"},
            {"id": "script.bingie.widgets", "minimum": "1.0.1", "source": "repository.actweeter / Matke Omega",
             "license": "upstream metadata", "platforms": ALL_TARGET_PLATFORMS,
             "dependencies": (), "configuration": "Widget providers and skin settings",
             "update": "Original repository catalog", "recovery": "Kodi native reinstall"},
            {"id": "script.skinshortcuts", "minimum": "2.0.3", "source": "Kodi official repository",
             "license": "upstream metadata", "platforms": ALL_TARGET_PLATFORMS,
             "dependencies": (), "configuration": "Generated menu in Kodi profile",
             "update": "Kodi official repository", "recovery": "Rerun skin shortcut generation"},
            {"id": "resource.images.studios.coloured", "minimum": "0.0.24", "source": "repository.actweeter / Kodi official",
             "license": "upstream metadata", "platforms": ALL_TARGET_PLATFORMS,
             "dependencies": (), "configuration": "Image resource package",
             "update": "Original repository catalog", "recovery": "Kodi native reinstall"},
            {"id": "plugin.video.tmdb.bingie.helper", "minimum": "1.0.1", "source": "repository.actweeter / Matke Omega",
             "license": "upstream metadata", "platforms": ALL_TARGET_PLATFORMS,
             "dependencies": (), "configuration": "Metadata and widget integration",
             "update": "Original repository catalog", "recovery": "Kodi native reinstall"},
            {"id": "plugin.program.autocompletion", "minimum": "2.1.2", "source": "repository.actweeter / Kodi official",
             "license": "upstream metadata", "platforms": ALL_TARGET_PLATFORMS,
             "dependencies": (), "configuration": "Search keyboard support",
             "update": "Original repository catalog", "recovery": "Kodi native reinstall"},
            {"id": "resource.language.es_es", "minimum": "11.0.108", "source": "Kodi official repository",
             "license": "Kodi language resource", "platforms": ALL_TARGET_PLATFORMS,
             "dependencies": (), "configuration": "Factory Spanish UI language resource",
             "update": "Kodi official repository", "recovery": "Kodi native reinstall"},
        ),
    },
    {
        "id": "iptv",
        "name": "IPTV",
        "required": True,
        "addons": (
            {"id": "plugin.video.xstream-pro", "minimum": "1.1.2.4", "source": "repository.actweeter",
             "license": "CC-BY-NC-4.0", "platforms": ALL_TARGET_PLATFORMS,
             "dependencies": ("pvr.iptvsimple",),
             "configuration": "Provider credentials stay in XStream settings; not copied into AcTweeteR",
             "update": "Kodi repository origin; AcTweeteR must maintain its package source",
             "recovery": "Rerun provider repair without resetting profile"},
            {"id": "pvr.iptvsimple", "minimum": "21.4.0", "source": "Kodi official or platform-bundled",
             "license": "upstream metadata", "platforms": ALL_TARGET_PLATFORMS,
             "dependencies": (), "configuration": "PVR settings configured only after user/provider consent",
             "update": "Kodi official/platform binary update channel",
             "recovery": "Enable or repair through Kodi's native add-on manager"},
        ),
    },
    {
        "id": "trailers",
        "name": "Trailers (SlyGuy)",
        "required": True,
        "addons": (
            {"id": "repository.slyguy", "minimum": "0.0.9", "source": "official SlyGuy repository package, bootstrapped from its live catalog",
             "license": "upstream metadata; no AcTweeteR redistribution", "platforms": ALL_TARGET_PLATFORMS,
             "consent_required": True,
             "dependencies": (), "configuration": "Kodi repository trust/install confirmation",
             "update": "SlyGuy repository", "recovery": "Re-enable repository and refresh Kodi repositories"},
            {"id": "slyguy.dependencies", "minimum": "0.0.30", "source": "repository.slyguy",
             "license": "upstream metadata; no AcTweeteR redistribution", "platforms": ALL_TARGET_PLATFORMS,
             "consent_required": True,
             "dependencies": ("repository.slyguy",), "configuration": "None verified",
             "update": "SlyGuy repository", "recovery": "Kodi native reinstall from repository.slyguy"},
            {"id": "script.module.slyguy", "minimum": "0.86.96", "source": "repository.slyguy",
             "license": "upstream metadata; no AcTweeteR redistribution", "platforms": ALL_TARGET_PLATFORMS,
             "consent_required": True,
             "dependencies": ("slyguy.dependencies", "repository.slyguy"), "configuration": "None verified",
             "update": "SlyGuy repository", "recovery": "Kodi native reinstall from repository.slyguy"},
            {"id": "slyguy.trailers", "minimum": "0.2.1", "source": "repository.slyguy",
             "license": "upstream metadata; no AcTweeteR redistribution", "platforms": ALL_TARGET_PLATFORMS,
             "consent_required": True,
             "dependencies": ("script.module.slyguy", "inputstream.adaptive"), "configuration": "Provider availability; no shared credentials",
             "update": "SlyGuy repository", "recovery": "Rerun trailer repair in AcTweeteR"},
        ),
    },
    {
        "id": "media",
        "name": "Media and search",
        "required": True,
        "addons": (
            {"id": "plugin.video.youtube", "minimum": "", "source": "Kodi official repository",
             "license": "upstream metadata", "platforms": ALL_TARGET_PLATFORMS,
             "dependencies": (), "configuration": "Google/API authorization is external and not inferred",
             "update": "Kodi official repository", "recovery": "Kodi native reinstall; retain add-on profile"},
            {"id": "script.trakt", "minimum": "3.9.0", "source": "Kodi official repository",
             "license": "GPL-2.0-only", "platforms": ALL_TARGET_PLATFORMS,
             "consent_required": True,
             "dependencies": (), "configuration": "Official device-code authorization is user-owned; account tokens stay in script.trakt",
             "update": "Kodi official repository", "recovery": "Kodi native reinstall; retain add-on profile"},
            {"id": "inputstream.adaptive", "minimum": "21.0.0", "source": "Kodi official or platform-bundled",
             "consent_required": True,
             "license": "GPL-2.0-or-later", "platforms": ALL_TARGET_PLATFORMS,
             "dependencies": (), "configuration": "Platform binary used by SlyGuy DASH playback",
             "update": "Kodi official/platform binary update channel",
             "recovery": "Enable compatible platform package through Kodi"},
        ),
    },
    {
        "id": "extensions",
        "name": "Extensions",
        "required": True,
        "addons": (
            {"id": "repository.rivulet", "minimum": "1.0.2", "source": "official Rivulet repository package, pinned bootstrap from AcTweeteR Testing",
             "license": "MIT", "platforms": ALL_TARGET_PLATFORMS,
             "dependencies": (), "configuration": "Official repository metadata; no user data changed",
             "update": "AcTweeteR Testing bootstrap; Rivulet add-on updates remain upstream",
             "recovery": "Kodi native reinstall from AcTweeteR Testing"},
            {"id": "plugin.video.rivulet", "minimum": "0.36.0", "source": "repository.rivulet",
             "license": "MIT AND GPL-3.0-only", "platforms": ALL_TARGET_PLATFORMS,
             "dependencies": ("repository.rivulet",),
             "configuration": "Rivulet settings and Stremio account remain upstream-owned",
             "update": "Kodi add-on repository automatic updates from repository.rivulet",
             "recovery": "Kodi native reinstall; retain Rivulet add-on profile"},
            {"id": "repository.zachmorris", "minimum": "1.0.4", "source": "official Zach Morris repository bootstrap, SHA-256 pinned in Beta",
             "license": "GPL-3.0", "platforms": ALL_TARGET_PLATFORMS,
             "dependencies": (), "configuration": "Official repository metadata; no user data changed",
             "update": "AcTweeteR Testing bootstrap; upstream IAGL packages remain served by repository.zachmorris",
             "recovery": "Kodi native reinstall from AcTweeteR Testing"},
            {"id": "plugin.program.iagl", "minimum": "4.0.6", "source": "repository.zachmorris",
             "license": "GPL-3.0-only; supplementary game-list databases are CC BY-NC 4.0",
             "platforms": ALL_TARGET_PLATFORMS,
             "dependencies": ("repository.zachmorris",),
             "configuration": "IAGL first-run configuration remains user-owned; no ROMs or games are downloaded by setup",
             "update": "Kodi add-on repository automatic updates from repository.zachmorris",
             "recovery": "Kodi native reinstall; retain IAGL add-on profile"},
        ),
    },
    {"id": "diagnostics", "name": "Diagnostics", "required": True,
     "minimum": "0.4.3", "source": "Bundled with service.actweeter",
     "license": "GPL-2.0-or-later", "platforms": ALL_TARGET_PLATFORMS,
     "dependencies": (), "configuration": "Credential values excluded from exported reports",
     "update": "service.actweeter via Kodi repository updates",
     "recovery": "Rerun Diagnosticar instalación from AcTweeteR setup",
     "addons": ()},
)

# Per-component lifecycle ownership. The common test verifies the manifest
# contract; feature-specific suites exercise AcTweeteR-owned integrations.
_LIFECYCLE = {
    "skin.actweeter": {
        "migration": "service.actweeter interface_layout version migration",
        "skin_integration": "shortcuts DATA source; Kodi Skin Shortcuts generation",
        "tests": ("tests/test_interface_layout.py", "tests/test_structural_defaults.py"),
    },
    "service.actweeter": {
        "migration": "wizard state and component catalog schema migrations",
        "skin_integration": "setup, service events, diagnostics and provider adapters",
        "tests": ("tests/test_first_run.py", "tests/test_all_in_one_contract.py",
                  "tests/test_service_core.py"),
    },
    "plugin.video.xstream-pro": {
        "migration": "none; settings remain owned by XStream Pro",
        "skin_integration": "provider-backed routes and profile-neutral widgets",
        "tests": ("tests/test_home_widget_playback.py", "tests/test_xstream_setup.py",
                  "tests/test_xstream_search_route.py"),
    },
    "pvr.iptvsimple": {
        "migration": "none; Kodi/provider-owned settings are preserved",
        "skin_integration": "native Kodi PVR guide and channel navigation",
        "tests": ("tests/test_pvr_binding.py", "tests/test_module_catalog.py"),
    },
    "slyguy.trailers": {
        "migration": "none; upstream package and settings remain upstream-owned",
        "skin_integration": "explicit and automatic trailer bridge",
        "tests": ("tests/test_slyguy_trailer_return.py", "tests/test_slyguy_preview_bridge.py",
                  "tests/test_automatic_preview.py"),
    },
}

_REPOSITORIES = {
    "skin.actweeter": ("repository.actweeter",),
    "service.actweeter": ("repository.actweeter",),
    "xbmc.gui": (),
    "script.bingie.helper": ("repository.actweeter",),
    "script.bingie.toolbox": ("repository.actweeter",),
    "script.bingie.widgets": ("repository.actweeter",),
    "script.skinshortcuts": ("repository.xbmc.org",),
    "resource.images.studios.coloured": ("repository.actweeter", "repository.xbmc.org"),
    "plugin.video.tmdb.bingie.helper": ("repository.actweeter",),
    "plugin.program.autocompletion": ("repository.actweeter", "repository.xbmc.org"),
    "resource.language.es_es": ("repository.xbmc.org",),
    "plugin.video.xstream-pro": ("repository.actweeter",),
    "pvr.iptvsimple": ("repository.xbmc.org",),
    "repository.slyguy": ("repository.actweeter",),
    "slyguy.dependencies": ("repository.slyguy",),
    "script.module.slyguy": ("repository.slyguy",),
    "slyguy.trailers": ("repository.slyguy",),
    "plugin.video.youtube": ("repository.xbmc.org",),
    "script.trakt": ("repository.xbmc.org",),
    "inputstream.adaptive": ("repository.xbmc.org",),
    "repository.rivulet": ("repository.actweeter",),
    "plugin.video.rivulet": ("repository.rivulet",),
    "repository.zachmorris": ("repository.actweeter",),
    "plugin.program.iagl": ("repository.zachmorris",),
}


def _lifecycle_entry(addon):
    entry = dict(addon)
    entry["repositories"] = _REPOSITORIES.get(addon["id"], ())
    entry.update(_LIFECYCLE.get(addon["id"], {
        "migration": "none",
        "skin_integration": "none; native Kodi add-on lifecycle",
        "tests": ("tests/test_module_catalog.py",),
    }))
    return entry


def all_addons():
    """Flatten catalog entries, preserving the first canonical add-on record."""
    result = {}
    for module in MODULES:
        for addon in module["addons"]:
            entry = _lifecycle_entry(addon)
            entry["required"] = bool(module.get("required", True) and
                                    addon.get("required", True))
            entry["consent_required"] = bool(
                addon.get("consent_required", not entry["required"]))
            result.setdefault(addon["id"], entry)
    return result


def repository_sources(modules=None):
    """Map every declared add-on to its authorized Kodi repository IDs."""
    result = {}
    for module in MODULES if modules is None else modules:
        for addon in module.get("addons", ()):
            entry = _lifecycle_entry(addon)
            result[addon["id"]] = tuple(entry["repositories"])
    return result


def addon_state(addon, *, installed_version="", enabled=False, platform="unknown"):
    """Return an explicit status without equating installation with operation."""
    supported = platform in addon["platforms"] or "all" in addon["platforms"]
    if not supported:
        install_state = "UNSUPPORTED_PLATFORM"
    elif not installed_version:
        install_state = "MISSING"
    elif addon["minimum"] and not _version_satisfies(installed_version, addon["minimum"]):
        install_state = "VERSION_INCOMPATIBLE"
    elif not enabled:
        install_state = "INSTALLED_DISABLED"
    else:
        install_state = "INSTALLED_ENABLED"
    return {
        "id": addon["id"],
        "required": addon.get("required", True),
        "consent_required": addon.get("consent_required", False),
        "minimum": addon["minimum"],
        "installed_version": installed_version or "",
        "available_version": "UNKNOWN_UNQUERIED",
        "install_state": install_state,
        "runtime_state": "NOT_TESTED",
        "platform_compatibility": "NOT_RUNTIME_VERIFIED",
        "structural_compatibility": "DECLARED_SUPPORTED" if supported else "NOT_DECLARED_SUPPORTED",
        "source": addon["source"],
        "license": addon["license"],
        "platforms": list(addon["platforms"]),
        "dependencies": list(addon["dependencies"]),
        "configuration": addon["configuration"],
        "update": addon["update"],
        "recovery": addon["recovery"],
        "migration": addon.get("migration", "none"),
        "skin_integration": addon.get("skin_integration", "none"),
        "tests": list(addon.get("tests", ())),
        "repositories": list(addon.get("repositories", ())),
    }


def _version_satisfies(installed, minimum):
    # Imported lazily: first_run also consumes this catalog's installation plan.
    from first_run import addon_version_satisfies
    return addon_version_satisfies(installed, minimum)


def installation_plan(platform, modules=None, *, selected_optional=()):
    """Dependency-first plan; Kodi resolves each package's full native imports.

    Catalog edges express bootstrap order, not a replacement for addon.xml.
    Unknown edges and cycles are errors rather than silently omitted packages.
    Required modules are mandatory roots. Optional modules/add-ons enter the
    plan only when selected with consent; their dependency closure is included.
    Unsupported entries stay in the plan so callers report a blocking state.
    """
    modules = MODULES if modules is None else modules
    if isinstance(selected_optional, str):
        raise ValueError("selected_optional must be an iterable of add-on IDs")
    try:
        selected_optional = frozenset(selected_optional)
    except TypeError as exc:
        raise ValueError("selected_optional must be an iterable of add-on IDs") from exc
    if any(not isinstance(addon_id, str) or not addon_id for addon_id in selected_optional):
        raise ValueError("selected_optional contains an invalid add-on ID")
    entries = {}
    for module in modules:
        for addon in module.get("addons", ()):
            if addon["id"] in entries:
                raise ValueError("duplicate catalog add-on")
            entry = _lifecycle_entry(addon)
            entry["required"] = bool(module.get("required", True) and
                                     addon.get("required", True))
            entry["consent_required"] = bool(
                addon.get("consent_required", not entry["required"]))
            entries[addon["id"]] = entry
    unknown_selected = selected_optional.difference(entries)
    if unknown_selected:
        raise ValueError("unknown optional add-on: " + sorted(unknown_selected)[0])
    non_optional = [addon_id for addon_id in selected_optional
                    if entries[addon_id]["required"]]
    if non_optional:
        raise ValueError("selected add-on is mandatory: " + sorted(non_optional)[0])
    missing_consent = [addon_id for addon_id in selected_optional
                       if not entries[addon_id]["consent_required"]]
    if missing_consent:
        raise ValueError("optional add-on lacks consent gate: " +
                         sorted(missing_consent)[0])
    ordered, visiting, visited = [], set(), set()

    def visit(addon_id):
        if addon_id.startswith("xbmc."):
            return  # Application API imports are verified by Kodi's resolver.
        if addon_id not in entries:
            raise ValueError("unregistered dependency: " + addon_id)
        if addon_id in visiting:
            raise ValueError("catalog dependency cycle: " + addon_id)
        if addon_id in visited:
            return
        visiting.add(addon_id)
        addon = entries[addon_id]
        for dependency in addon["dependencies"]:
            visit(dependency)
        visiting.remove(addon_id)
        visited.add(addon_id)
        addon["supported"] = platform in addon["platforms"] or "all" in addon["platforms"]
        ordered.append(addon)

    # Add-ons in optional modules are present in the graph but are roots only
    # after explicit selection. Dependencies of a selected root are still
    # traversed recursively, even if they belong to that optional module.
    for addon_id, addon in entries.items():
        if addon.get("required", True) or addon_id in selected_optional:
            visit(addon_id)
    return tuple(ordered)


def valid_catalog(modules=None):
    """Validate stable IDs and required lifecycle fields for automated tests."""
    seen = set()
    for module in MODULES if modules is None else modules:
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", module.get("id", "")):
            return False
        for addon in module.get("addons", ()):
            addon_id = addon.get("id", "")
            required_fields = ("minimum", "source", "license", "platforms",
                               "dependencies", "configuration", "update", "recovery")
            if (not re.fullmatch(r"[A-Za-z0-9._-]+", addon_id) or addon_id in seen
                    or any(key not in addon or addon[key] is None for key in required_fields)
                    or not addon.get("source") or not addon.get("license")
                    or not addon.get("platforms") or not addon.get("update")
                    or not addon.get("recovery")):
                return False
            lifecycle = _lifecycle_entry(addon)
            if (not lifecycle.get("migration") or not lifecycle.get("skin_integration")
                    or not lifecycle.get("tests")):
                return False
            repositories = lifecycle.get("repositories")
            if not isinstance(repositories, (tuple, list)) or any(
                    not isinstance(repo, str) or not repo for repo in repositories):
                return False
            if not addon_id.startswith("xbmc.") and not repositories:
                return False
            if "required" in addon and not isinstance(addon["required"], bool):
                return False
            if "consent_required" in addon and not isinstance(addon["consent_required"], bool):
                return False
            if (not module.get("required", True) or not addon.get("required", True)) and \
                    addon.get("consent_required") is not True:
                return False
            if not isinstance(addon["dependencies"], (tuple, list)) or any(
                    not isinstance(dep, str) or not dep for dep in addon["dependencies"]):
                return False
            seen.add(addon_id)
        if module["id"] == "diagnostics":
            required = ("minimum", "source", "license", "platforms", "dependencies",
                        "configuration", "update", "recovery")
            if any(key not in module or module[key] is None or module[key] == ""
                   for key in required):
                return False
    return True
