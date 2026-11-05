#!/usr/bin/env python3
"""Create-only, deterministic skin-only Beta3 to fix nonfunctional touch clicks."""
from __future__ import annotations
import argparse,hashlib,json,stat,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"source/0.4.32/addons/skin.actweeter"
ADDON="skin.actweeter"
BASE_VERSION="1.2.41~beta2"
BETA_VERSION="1.2.41~beta3"
BASE_SHA256="81004dc11b5e697f2e4dada7899002d32c80243278718ff2d844f86d9c7fd986"
TIME=(2026,11,5,0,0,0)
OVERLAY=(
"1080i/IncludesTouchInfoActions.xml",
"1080i/IncludesTouchVideoNavigation.xml",
"1080i/DialogVideoInfo.xml",
)
NOTES=("AcTweeteR 1.2.41~beta3 - Fix nonresponsive touch actions in native information pages.\n"
       "Mirror original Kodi action scripts in touch buttons, with conditions for both info layouts.\n"
       "Resolve modal drawer on Home and focus current media list rather than container group.\n"
       "Stable/remote controls, Service, XStream, Trakt, Rivulet and EPG unchanged.\n")

def sha(data):
    return hashlib.sha256(data).hexdigest()

def build(output):
    output=Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Refusing to overwrite Beta3 ZIP: {output}")
    base=ROOT/"docs/testing/repo/skin.actweeter"/f"{ADDON}-{BASE_VERSION}.zip"
    if sha(base.read_bytes())!=BASE_SHA256:
        raise ValueError("Published Beta2 source ZIP was modified")
    with zipfile.ZipFile(base) as z:
        if z.testzip() is not None: raise ValueError("Beta2 source CRC mismatch")
        content={x:z.read(x) for x in z.namelist() if x and not x.endswith("/")}
    previous=dict(content)
    for name in OVERLAY:
        file=SRC/name
        if file.is_symlink() or not file.is_file():
            raise ValueError(f"Missing skin source: {name}")
        data=file.read_bytes()
        if name.endswith(".xml"):ET.fromstring(data)
        content[f"{ADDON}/{name}"]=data
    addon_name=f"{ADDON}/addon.xml"
    manifest=ET.fromstring(content[addon_name])
    if manifest.get("id")!=ADDON or manifest.get("version")!=BASE_VERSION:
        raise ValueError("Unexpected Beta2 ID/version")
    news=manifest.find("./extension[@point='xbmc.addon.metadata']/news")
    if news is None or news.text!=f"changelog-{BASE_VERSION}.txt":
        raise ValueError("Unexpected Beta2 changelog")
    news.text=f"changelog-{BETA_VERSION}.txt"
    manifest.set("version",BETA_VERSION)
    content[addon_name]=ET.tostring(manifest,encoding="utf-8",xml_declaration=True)+b"\n"
    content[f"{ADDON}/{news.text}"]=NOTES.encode()
    modified={n for n,b in content.items() if previous.get(n)!=b}
    expected={f"{ADDON}/{name}" for name in OVERLAY}
    expected.update({addon_name,f"{ADDON}/{news.text}"})
    if modified!=expected:
        raise ValueError(f"Unexpected payload differences: {modified^expected}")
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,b in sorted(content.items()):
            if not name.startswith(ADDON+"/") or ".." in Path(name).parts:
                raise ValueError(f"Unsafe ZIP path {name}")
            info=zipfile.ZipInfo(name,TIME)
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(stat.S_IFREG|0o644)<<16
            z.writestr(info,b,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    with zipfile.ZipFile(output) as z:
        if z.testzip() is not None:raise ValueError("Beta3 CRC failure")
        if ET.fromstring(z.read(addon_name)).get("version")!=BETA_VERSION:
            raise ValueError("Beta3 manifest mismatch")
    return {"version":BETA_VERSION,"sha256":sha(output.read_bytes()),
            "bytes":output.stat().st_size,"members":len(content),
            "overlay":sorted(modified)}

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=ROOT/"build/touch-beta3/skin.actweeter-1.2.41~beta3.zip")
    print(json.dumps(build(parser.parse_args().output),indent=2))
