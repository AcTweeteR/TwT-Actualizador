#!/usr/bin/env python3
"""Create a deterministic, Kodi-rooted AcTweeteR skin ZIP."""
from __future__ import annotations

import hashlib
import argparse
import stat
import unicodedata
import zipfile
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
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(p for p in SOURCE.rglob("*") if p.is_file()):
            if path.suffix in ('.pyc','.pyo') or path.name=='.DS_Store':continue
            name = (Path("skin.actweeter") / path.relative_to(SOURCE)).as_posix()
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            payload = bootstrap_includes(SOURCE) if path.relative_to(SOURCE).as_posix()=='1080i/script-skinshortcuts-includes.xml' else path.read_bytes()
            archive.writestr(info, payload, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    print(f"{output}\nSHA-256 {digest}")


if __name__ == "__main__":
    main()
