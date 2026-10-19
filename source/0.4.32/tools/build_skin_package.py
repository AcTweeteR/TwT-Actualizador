#!/usr/bin/env python3
"""Create a deterministic, Kodi-rooted AcTweeteR skin ZIP."""
from __future__ import annotations

import hashlib
import argparse
import stat
import unicodedata
import zipfile
from package_safety import publish_zip
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "addons" / "skin.actweeter"
FIXED_TIME = (2026, 10, 3, 0, 0, 0)


def addon_version(source: Path) -> str:
    return ET.parse(source / "addon.xml").getroot().get("version", "")


def bootstrap_includes(source: Path) -> bytes:
    """Ship a profile-neutral starter menu, never a generated Mac menu cache."""
    root = ET.Element('includes')
    names_path = ROOT / 'tools' / 'skinshortcuts_include_names.txt'
    names = {line.strip() for line in names_path.read_text(encoding='utf-8').splitlines()
             if line.strip() and 'Master user' not in line}
    names.add('skinshortcuts-mainmenu')
    for name in sorted(names):
        include = ET.SubElement(root, 'include', name=name)
        if name != 'skinshortcuts-mainmenu':continue
        defaults = ET.parse(source / 'shortcuts/mainmenu.DATA.xml').getroot()
        for number, shortcut in enumerate(defaults.findall('shortcut'), 1):
            item = ET.SubElement(include, 'item', id=str(number))
            label = shortcut.findtext('label') or ''
            action = shortcut.findtext('action') or 'noop'
            for tag in ('label','label2','icon','thumb'):
                ET.SubElement(item,tag).text=shortcut.findtext(tag) or ''
            slug = ''.join(c for c in unicodedata.normalize('NFKD',label.lower())
                           if not unicodedata.combining(c)).replace(' ','')
            for key,value in (('id',str(number)),('mainmenuid',str(number)),
                              ('labelID',slug),('submenuVisibility',slug),('path',action)):
                ET.SubElement(item,'property',name=key).text=value
            ET.SubElement(item,'onclick').text=action
    return ET.tostring(root,encoding='utf-8',xml_declaration=True)+b'\n'


def main() -> None:
    parser = argparse.ArgumentParser()
    version = addon_version(SOURCE)
    if not version:
        raise SystemExit("skin addon.xml has no version")
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / f"skin.actweeter-{version}.zip")
    args = parser.parse_args()
    output = args.output.expanduser().absolute()
    if ET.parse(SOURCE / "addon.xml").getroot().get("id") != "skin.actweeter":
        raise ValueError("skin addon identity mismatch")
    digest = publish_zip(SOURCE, output, "skin.actweeter", version, FIXED_TIME,
                         lambda path: bootstrap_includes(SOURCE) if path.relative_to(SOURCE).as_posix() == "1080i/script-skinshortcuts-includes.xml" else path.read_bytes(),
                         lambda path: path.suffix in (".pyc", ".pyo") or "__pycache__" in path.parts or path.name == ".DS_Store")
    print(f"{output}\nSHA-256 {digest}")


if __name__ == "__main__":
    main()
