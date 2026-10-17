#!/usr/bin/env python3
"""Create a deterministic Kodi ZIP for the AcTweeteR repository add-on."""
from __future__ import annotations

import argparse
import hashlib
import stat
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "addons" / "repository.actweeter"
FIXED_TIME = (2026, 10, 3, 0, 0, 0)


def main() -> None:
    addon = ET.parse(SOURCE / "addon.xml").getroot()
    version = addon.get("version", "")
    if addon.get("id") != "repository.actweeter" or not version:
        raise SystemExit("invalid repository add-on metadata")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path,
        default=ROOT / "dist" / f"repository.actweeter-{version}.zip",
    )
    output = parser.parse_args().output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as archive:
        for path in sorted(p for p in SOURCE.rglob("*") if p.is_file()):
            name = (Path("repository.actweeter") / path.relative_to(SOURCE)).as_posix()
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, path.read_bytes(),
                             compress_type=zipfile.ZIP_DEFLATED,
                             compresslevel=9)
    print(f"{output}\nSHA-256 {hashlib.sha256(output.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
