#!/usr/bin/env python3
"""Audit public repository metadata offline; never install or read a profile."""
import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source/0.4.32/addons/service.actweeter/resources/lib"))
from first_run import addon_version_satisfies
from module_catalog import all_addons


def audit(feeds):
    available, evidence, rows = {}, [], {}
    for name, path in feeds:
        payload = Path(path).read_bytes()
        evidence.append({"source": name, "sha256": hashlib.sha256(payload).hexdigest()})
        root = ET.fromstring(gzip.decompress(payload) if payload[:2] == b"\x1f\x8b" else payload)
        for addon in ([root] if root.tag == "addon" else root.findall("addon")):
            available.setdefault(addon.get("id"), []).append((name, addon))

    def visit(addon_id, minimum, required):
        if addon_id.startswith(("xbmc.", "kodi.")):
            return  # Application APIs are validated by Kodi's native resolver.
        if addon_id in rows and addon_version_satisfies(rows[addon_id]["minimum"] or "0", minimum or "0"):
            rows[addon_id]["required"] |= required
            return
        candidates = [(name, addon) for name, addon in available.get(addon_id, [])
                      if not minimum or addon_version_satisfies(addon.get("version"), minimum)]
        row = {"id": addon_id, "minimum": minimum, "required": required,
               "status": "AVAILABLE_METADATA" if candidates else "NOT_IN_FETCHED_FEEDS",
               "candidates": [{"source": name, "version": addon.get("version"),
                               "platform": addon.findtext("extension[@point='xbmc.addon.metadata']/platform"),
                               "license": addon.findtext("extension[@point='xbmc.addon.metadata']/license")}
                              for name, addon in candidates]}
        rows[addon_id] = row
        # Traverse all acceptable candidates, not an assumed platform binary.
        for _, addon in candidates:
            for dep in addon.findall("requires/import"):
                visit(dep.get("addon", ""), dep.get("version", ""),
                      required and dep.get("optional") != "true")

    for addon_id, entry in all_addons().items():
        visit(addon_id, entry["minimum"], entry.get("required", True))
    return {"feeds": evidence, "runtime": "NOT_TESTED", "dependencies": list(rows.values())}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feed", action="append", required=True, help="public source label=local XML/gzip file")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit([item.split("=", 1) for item in args.feed])
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"dependencies": len(report["dependencies"]),
                      "missing": [x["id"] for x in report["dependencies"]
                                  if x["status"] != "AVAILABLE_METADATA"],
                      "runtime": report["runtime"]}))
