"""Create-only Beta TV widget packages based on exact current Beta ZIPs."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from build_test_channel import zip_tree

ROOT = Path(__file__).resolve().parents[1]
STEMS = {
    "service.actweeter": {
        "old": "0.4.101~beta2", "new": "0.4.101~beta3",
        "paths": ("service.py", "resources/lib/diagnostic_plugin.py",
                  "resources/lib/interface_layout.py", "resources/lib/tv_recent.py"),
    },
    "skin.actweeter": {
        "old": "1.2.41~beta5", "new": "1.2.41~beta6",
        "paths": ("shortcuts/inicio-1.DATA.xml", "shortcuts/10000-1.DATA.xml",
                  "shortcuts/template.xml", "1080i/IncludesHomeWidgets.xml",
                  "1080i/IncludesBingie.xml"),
    },
}


def build_one(addon_id, directory):
    detail = STEMS[addon_id]
    old, new = detail["old"], detail["new"]
    source = ROOT / "docs/testing/repo" / addon_id / (addon_id + "-" + old + ".zip")
    target = directory / (addon_id + "-" + new + ".zip")
    if target.exists():
        raise FileExistsError(target)
    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        with zipfile.ZipFile(source) as archive:
            names = archive.namelist()
            if (archive.testzip() is not None or len(names) != len(set(names)) or
                    any(not name.startswith(addon_id + "/") or
                        ".." in Path(name).parts for name in names)):
                raise ValueError("Unsafe baseline ZIP")
            baseline = {name: archive.read(name) for name in names
                        if not name.endswith("/")}
            for name, data in baseline.items():
                location = stage / name
                location.parent.mkdir(parents=True, exist_ok=True)
                location.write_bytes(data)
        tree = stage / addon_id
        for relative in detail["paths"]:
            origin = ROOT / "source/0.4.32/addons" / addon_id / relative
            wanted = tree / relative
            wanted.parent.mkdir(parents=True, exist_ok=True)
            wanted.write_bytes(origin.read_bytes())
        xml_path = tree / "addon.xml"
        addon = ET.parse(xml_path)
        if addon.getroot().get("version") != old:
            raise ValueError("Baseline version has changed")
        addon.getroot().set("version", new)
        news = "changelog-" + new + ".txt"
        node = addon.find("./extension[@point='xbmc.addon.metadata']/news")
        if node is None:
            raise ValueError("Missing changelog property")
        node.text = news
        addon.write(xml_path, encoding="utf-8", xml_declaration=True)
        (tree / news).write_text(
            ("Beta: historial de canales TV vistos en Inicio; iconos, programa EPG, "
             "historial único MRU de 19 canales; actualización sin reconstruir "
             "el resto de widgets.\n"), encoding="utf-8")
        for path in tree.rglob("*.py"):
            compile(path.read_bytes(), str(path), "exec")
        for path in tree.rglob("*.xml"):
            ET.parse(path)
        zip_tree(tree, target, addon_id)
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC failed")
        actual = {name: archive.read(name) for name in archive.namelist()
                  if not name.endswith("/")}
        manifest = ET.fromstring(actual[addon_id + "/addon.xml"])
        if manifest.get("version") != new:
            raise ValueError("Candidate manifest version mismatch")
        modified = {name for name in baseline if baseline[name] != actual.get(name)}
        added = set(actual) - set(baseline)
        expected = {addon_id + "/addon.xml"}
        expected.update(addon_id + "/" + item for item in detail["paths"]
                        if item != "resources/lib/tv_recent.py")
        expected_added = {addon_id + "/" + news}
        if addon_id == "service.actweeter":
            expected_added.add(addon_id + "/resources/lib/tv_recent.py")
        if modified != expected or added != expected_added:
            raise ValueError("Unexpected package delta: %s %s" %
                             (sorted(modified), sorted(added)))
        return {"addon": addon_id, "version": new, "sha256":
                hashlib.sha256(target.read_bytes()).hexdigest(),
                "changed": sorted(modified), "added": sorted(added)}


def build(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    return [build_one(addon, directory) for addon in STEMS]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    print(json.dumps(build(parser.parse_args().output), indent=2))
