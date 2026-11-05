#!/usr/bin/env python3
"""Fix touch proxies by embedding the *actual* BingieInfo/AltInfo onclick actions.

Kodi's SendClick builtin sends a GUI_MSG_CLICKED message to a window. That is
not equivalent to executing a nested radiobutton's onclick script and can
target the wrong active window when video-info is a modal dialog. Instead,
these touch controls now execute the same conditional actions that the native
remote-mode controls execute.

No original control or third-party addon is edited.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import re
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "source/0.4.32/addons/skin.actweeter/1080i"
NATIVE_SOURCE_SHA = "2396a403c220290416dda7f45dfccde0022c982958cd13c82e01b80f9957660f"
CONTROL_IDS = {
    80, 90, 51, 8181, 53, 54, 52, 541, 56, 57, 561, 562, 60, 64,
    61, 63, 62, 611, 631, 622, 14, 10, 1040, 6, 612,
    7001, 7002, 7003, 7004, 7011, 7033, 7055,
}
MODE_GATES = {
    "BingieInfo": "Skin.HasSetting(UseBingieInfoDialog)",
    "BingieAltInfo": "!Skin.HasSetting(UseBingieInfoDialog)",
}

def native_buttons():
    file = UI / "IncludesDialogVideoInfo.xml"
    if hashlib.sha256(file.read_bytes()).hexdigest() != NATIVE_SOURCE_SHA:
        raise ValueError("Original remote-mode action source was modified; stop regeneration")
    tree = ET.parse(file).getroot()
    modes = {}
    for layout in MODE_GATES:
        include = tree.find(f"./include[@name='{layout}']")
        if include is None:
            raise ValueError("Missing native info layout " + layout)
        mapping = {}
        for element in include.iter("control"):
            id_ = element.get("id")
            if id_ and id_.isdecimal() and int(id_) in CONTROL_IDS:
                if int(id_) in mapping:
                    raise ValueError(f"Duplicate control {id_} in {layout}")
                mapping[int(id_)] = element
        modes[layout] = mapping
    return modes

def expand(path: Path, *, write: bool = False):
    path = Path(path)
    tree = ET.parse(path)
    modes = native_buttons()
    count = 0
    fallbacks = []
    for button in tree.findall(".//include[@name='AcTweeteRTouchVideoInfoActions']//control[@type='button']"):
        old_clicks = list(button.findall("onclick"))
        source = [click for click in old_clicks if click.text and re.fullmatch(r"SendClick\((\d+)\)", click.text)]
        if not source:
            continue
        if len(source) != 1:
            raise ValueError("Ambiguous touch forwarding button " + str(button.get("id")))
        original_id = int(re.fullmatch(r"SendClick\((\d+)\)", source[0].text).group(1))
        if original_id not in CONTROL_IDS:
            raise ValueError("Unrecognized native action " + str(original_id))
        source_index = list(button).index(source[0])
        button.remove(source[0])
        # The popup must close *before* an action navigates away from this dialog.
        # This property uses Home so it survives Kodi's modal window routing.
        for stale in list(button.findall("onclick")):
            if stale.text == "ClearProperty(AcTweeteRTouchInfoActions)":
                button.remove(stale)
        if int(button.get("id")) >= 44100:
            clear = ET.Element("onclick")
            clear.text = "ClearProperty(AcTweeteRTouchInfoActions,Home)"
            button.insert(source_index, clear)
            source_index += 1
        for layout, gate in MODE_GATES.items():
            native = modes[layout].get(original_id)
            if native is None:
                continue
            actions = list(native.findall("onclick"))
            if not actions:
                # These are intentionally handled by the original Kodi skin
                # control (e.g. artwork / native Refresh GUI_ID). Move focus
                # then select, rather than sending a message to the active
                # *window*, which may be the wrong modal.
                actions = [ET.Element("onclick"),ET.Element("onclick")]
                actions[0].text = f"SetFocus({original_id})"
                actions[1].text = "Action(Select)"
                fallbacks.append((layout,original_id))
            for action in actions:
                clone = copy.deepcopy(action)
                original_cond = (clone.get("condition") or "").strip()
                clone.set("condition", gate + (f" + [{original_cond}]" if original_cond else ""))
                button.insert(source_index,clone)
                source_index += 1
                count+=1
    if not count:
        raise ValueError("No SendClick proxies found to expand")
    if write:
        ET.indent(tree,space="    ")
        tree.write(path,encoding="utf-8",xml_declaration=True)
    return {"native_onclicks":count,"fallbacks":sorted(set(fallbacks)),
            "proxy_ids":len(CONTROL_IDS)}

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--write",action="store_true")
    args=parser.parse_args()
    print(expand(UI/"IncludesTouchInfoActions.xml",write=args.write))
