"""Read-only recursive verification of installed Kodi addon.xml imports."""

from __future__ import annotations

import re
from xml.etree import ElementTree as ET

from first_run import addon_version_satisfies

VALID_ID = re.compile(r"^[A-Za-z0-9._-]+$")


def inspect_graph(roots, read_manifest, probe):
    """Return secret-free dependency evidence; never install or edit files.

    ``probe`` returns (version, enabled). Kodi's application API imports are
    left to the native resolver. Optional addon.xml imports remain optional;
    mandatory catalog roots are inspected independently even if such an import
    exists elsewhere in the graph.
    """
    records, visiting, visited = {}, set(), set()

    def visit(addon_id, minimum=""):
        if not isinstance(addon_id, str) or not VALID_ID.fullmatch(addon_id):
            raise ValueError("invalid dependency identifier")
        if addon_id.startswith("xbmc.") or addon_id.startswith("kodi."):
            return
        version, enabled = probe(addon_id)
        row = records.setdefault(addon_id, {"id": addon_id, "minimum": minimum,
            "installed_version": version or "", "status": "READY", "dependencies": []})
        if minimum and (not row["minimum"] or addon_version_satisfies(minimum, row["minimum"])):
            row["minimum"] = minimum
        if not version:
            row["status"] = "MISSING"
            return
        if row["minimum"] and not addon_version_satisfies(version, row["minimum"]):
            row["status"] = "VERSION_INCOMPATIBLE"
        elif not enabled:
            row["status"] = "DISABLED"
        if addon_id in visiting:
            row["status"] = "DEPENDENCY_CYCLE"
            return
        if addon_id in visited:
            return
        try:
            manifest = ET.fromstring(read_manifest(addon_id))
            if manifest.tag != "addon" or manifest.get("id") != addon_id or manifest.get("version") != version:
                raise ValueError("manifest identity mismatch")
        except (ET.ParseError, OSError, TypeError, ValueError):
            row["status"] = "INVALID_MANIFEST"
            return
        visiting.add(addon_id)
        for dependency in manifest.findall("requires/import"):
            if (dependency.get("optional") or "false").lower() == "true":
                continue
            child = dependency.get("addon", "")
            if not VALID_ID.fullmatch(child):
                row["status"] = "INVALID_MANIFEST"
                continue
            row["dependencies"].append(child)
            visit(child, dependency.get("version", ""))
        visiting.remove(addon_id)
        visited.add(addon_id)

    for addon_id, minimum in roots:
        visit(addon_id, minimum)
    return tuple(records.values())
