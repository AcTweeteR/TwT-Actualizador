#!/usr/bin/env python3
"""Create a deterministic Kodi ZIP for the AcTweeteR service add-on."""
from __future__ import annotations

import argparse
import hashlib
import stat
import xml.etree.ElementTree as ET
import zipfile
from package_safety import publish_zip
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "addons" / "service.actweeter"
FIXED_TIME = (2026, 10, 3, 0, 0, 0)


def main() -> None:
    addon = ET.parse(SOURCE / "addon.xml").getroot()
    version = addon.get("version", "")
    if addon.get("id") != "service.actweeter" or not version:
        raise SystemExit("invalid service add-on metadata")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path,
                        default=ROOT / "dist" / f"service.actweeter-{version}.zip")
    output = parser.parse_args().output.expanduser().absolute()
    digest = publish_zip(SOURCE, output, "service.actweeter", version, FIXED_TIME,
                         lambda path: path.read_bytes(),
                         lambda path: "__pycache__" in path.parts or path.suffix in (".pyc", ".pyo") or path.name == ".DS_Store")
    print(f"{output}\nSHA-256 {digest}")


if __name__ == "__main__":
    main()
