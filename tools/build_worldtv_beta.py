#!/usr/bin/env python3
"""Build independent WorldTV (LauncherM3U) and publish only the Kodi Beta feed."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from build_test_channel import zip_tree, addon_from_zip

ROOT = Path(__file__).resolve().parents[1]
ADDONS = ROOT / "source/0.4.32/addons"
FEED = ROOT / "docs/testing/repo"
UPSTREAM = ROOT / "source/0.4.32/third_party/worldtv/launcherM3U-1.3.3-upstream.zip"
UPSTREAM_SHA = "4fe218d404218f2f65b46ee6d2307c53fbebd936fe91e232f4e4cdc109edbcd1"
PLAYLIST = "https://iptv-org.github.io/iptv/index.country.m3u"
EPG = "https://raw.githubusercontent.com/teleonline/listas/main/epg.xml.gz"
RELEASES = (
    ("plugin.video.launcherm3u", "1.3.3~beta1", UPSTREAM),
    ("service.actweeter", "0.4.103~beta1",
     ROOT / "repo/service.actweeter/service.actweeter-0.4.102.zip"),
    ("skin.actweeter", "1.2.43~beta1",
     ROOT / "docs/testing/repo/skin.actweeter/skin.actweeter-1.2.41~beta10.zip"),
)
DEFAULTS = {
    "m3u_type": "1", "m3u_url": PLAYLIST,
    "epg_enabled": "true", "epg_type": "1", "epg_url": EPG,
    "auto_url_tvg": "false", "auto_refresh_hours": "12",
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def alter_launcher(tree):
    settings_path = tree / "resources/settings.xml"
    settings = ET.parse(settings_path)
    seen = set()
    for key, value in DEFAULTS.items():
        matches = settings.findall(".//setting[@id='%s']/default" % key)
        if len(matches) != 1:
            raise ValueError("Launcher setting missing or ambiguous: " + key)
        matches[0].text = value
        seen.add(key)
    assert seen == set(DEFAULTS)
    settings.write(settings_path, encoding="utf-8", xml_declaration=True)
    cache_file = tree / "resources/lib/cache.py"
    original = cache_file.read_text()
    anchor = '    for text in candidates:\n        low = text.lower()\n'
    replacement = (
        '    # IPTV-org quality tags are not part of the XMLTV channel identity.\n'
        '    # Keep the original identifier first and try the exact base ID next.\n'
        '    for candidate in tuple(candidates):\n'
        '        if "@" in candidate:\n'
        '            base = candidate.rsplit("@", 1)[0]\n'
        '            if base and base not in candidates:\n'
        '                candidates.insert(candidates.index(candidate) + 1, base)\n'
        + anchor
    )
    if original.count(anchor) != 1:
        raise ValueError("Launcher XMLTV resolver changed upstream")
    cache_file.write_text(original.replace(anchor, replacement))
    addon = ET.parse(tree / "addon.xml")
    if addon.getroot().get("version") != "1.3.3":
        raise ValueError("unexpected Launcher upstream version")
    addon.getroot().set("version", "1.3.3~beta1")
    news = addon.find("./extension[@point='xbmc.addon.metadata']/news")
    if news is not None:
        news.text = "AcTweeteR WorldTV Beta: IPTV-org por países y XMLTV externo preconfigurados."
    addon.write(tree / "addon.xml", encoding="utf-8", xml_declaration=True)


def alter_service(tree):
    for relative in ("service.py", "resources/lib/interface_layout.py",
                     "resources/lib/worldtv_setup.py", "resources/lib/module_catalog.py"):
        dest = tree / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ADDONS / "service.actweeter" / relative, dest)
    addon = ET.parse(tree / "addon.xml")
    required = addon.find("requires")
    if required is None:
        raise ValueError("service requires missing")
    if required.find("import[@addon='plugin.video.launcherm3u']") is not None:
        raise ValueError("duplicate WorldTV dependency")
    ET.SubElement(required, "import", {
        "addon": "plugin.video.launcherm3u", "version": "1.3.3~beta1"})
    addon.getroot().set("version", "0.4.103~beta1")
    news = addon.find("./extension[@point='xbmc.addon.metadata']/news")
    if news is None:
        raise ValueError("service news missing")
    news.text = "changelog-0.4.103~beta1.txt"
    addon.write(tree / "addon.xml", encoding="utf-8", xml_declaration=True)
    (tree / "changelog-0.4.103~beta1.txt").write_text(
        "WorldTV: instala LauncherM3U como dependencia independiente, configura IPTV-org "
        "y XMLTV en perfiles existentes sin sobrescribir listas personalizadas. "
        "Migración segura del submenú de TV, sin widgets ni cambios de PVR.\n"
    )


def alter_skin(tree):
    relative = "shortcuts/livetv.DATA.xml"
    shutil.copyfile(ADDONS / "skin.actweeter" / relative, tree / relative)
    addon = ET.parse(tree / "addon.xml")
    required = addon.find("requires")
    service = required.find("import[@addon='service.actweeter']")
    if service is None:
        raise ValueError("skin service dependency missing")
    service.set("version", "0.4.103~beta1")
    addon.getroot().set("version", "1.2.43~beta1")
    news = addon.find("./extension[@point='xbmc.addon.metadata']/news")
    if news is None:
        raise ValueError("skin news missing")
    news.text = "changelog-1.2.43~beta1.txt"
    addon.write(tree / "addon.xml", encoding="utf-8", xml_declaration=True)
    (tree / "changelog-1.2.43~beta1.txt").write_text(
        "WorldTV: acceso independiente desde el submenu de TV. "
        "Sin cambios en Home, widgets, proveedor IPTV o TV PVR.\n"
    )


def build():
    if digest(UPSTREAM) != UPSTREAM_SHA:
        raise ValueError("upstream LauncherM3U archive does not match SHA256 pin")
    index_path = FEED / "addons.xml"
    root = ET.parse(index_path).getroot()
    expected = {
        "skin.actweeter": "1.2.41~beta10",
        "service.actweeter": "0.4.101~beta6",
    }
    for addon_id, previous in expected.items():
        node = next((a for a in root if a.get("id") == addon_id), None)
        if node is None or node.get("version") != previous:
            raise ValueError("Beta feed changed: " + addon_id)
    if any(a.get("id") == "plugin.video.launcherm3u" for a in root):
        raise ValueError("LauncherM3U already published")
    output = []
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        for addon_id, version, source in RELEASES:
            dest = FEED / addon_id / (addon_id + "-" + version + ".zip")
            if dest.exists():
                raise FileExistsError("refusing to replace Beta ZIP " + str(dest))
            tree = stage / addon_id
            with zipfile.ZipFile(source) as archive:
                if archive.testzip() is not None:
                    raise ValueError("source ZIP damaged")
                for entry in archive.infolist():
                    p = Path(entry.filename)
                    if (not p.parts or p.parts[0] != addon_id or
                            ".." in p.parts or p.is_absolute()):
                        raise ValueError("unsafe archive path")
                    if entry.is_dir():
                        continue
                    target = stage / p
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(entry))
            if addon_id == "plugin.video.launcherm3u":
                alter_launcher(tree)
            elif addon_id == "service.actweeter":
                alter_service(tree)
            else:
                alter_skin(tree)
            for file in tree.rglob("*.py"):
                compile(file.read_bytes(), str(file), "exec")
            for file in tree.rglob("*.xml"):
                ET.parse(file)
            package = stage / "packages" / dest.name
            zip_tree(tree, package, addon_id)
            addon = addon_from_zip(package, addon_id, version)
            output.append((addon_id, version, package, dest, addon))
        for addon_id, version, package, dest, addon in output:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(package, dest)
            existing = next((a for a in root if a.get("id") == addon_id), None)
            if existing is not None:
                idx = list(root).index(existing)
                root.remove(existing)
                root.insert(idx, addon)
            else:
                root.append(addon)
            metadata = addon.find("./extension[@point='xbmc.addon.metadata']")
            assets = metadata.find("assets") if metadata is not None else None
            with zipfile.ZipFile(dest) as z:
                if assets is not None:
                    for elem in assets:
                        asset = (elem.text or "").strip()
                        if asset and not asset.startswith(("http:", "https:")):
                            p = Path(asset)
                            if p.is_absolute() or ".." in p.parts:
                                raise ValueError("unsafe metadata asset")
                            target = dest.parent / p
                            target.parent.mkdir(parents=True, exist_ok=True)
                            target.write_bytes(z.read(addon_id + "/" + asset))
                news = metadata.findtext("news", "") if metadata is not None else ""
                if news.startswith("changelog-"):
                    target = dest.parent / news
                    data = z.read(addon_id + "/" + news)
                    if target.exists() and target.read_bytes() != data:
                        raise ValueError("refusing to replace changelog")
                    target.write_bytes(data)
        payload = ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"
        payload = b"\n".join(line.rstrip() for line in payload.split(b"\n"))
        index_path.write_bytes(payload)
        (FEED / "addons.xml.md5").write_text(hashlib.md5(payload).hexdigest() + "\n")
        print(json.dumps({
            "packages": [{"id": a, "version": v, "size": dst.stat().st_size,
                          "sha256": digest(dst)} for a, v, _, dst, _ in output],
            "feed_sha256": hashlib.sha256(payload).hexdigest(),
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    build()
