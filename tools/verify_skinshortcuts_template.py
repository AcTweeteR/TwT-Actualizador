#!/usr/bin/env python3
"""Exercise the installed 2.0.3 property resolver on anonymous template fixtures.

The implementation argument is public add-on source, never profile data. Only
the get_properties method is compiled; no Kodi entry point or import executes.
No third-party source is redistributed by this script.
"""
import argparse
import ast
import hashlib
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree as ET


def verify(implementation, template):
    data = Path(implementation).read_bytes()
    parsed = ast.parse(data)
    cls = next(n for n in parsed.body if isinstance(n, ast.ClassDef) and n.name == "Template")
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                  and n.name in ("get_properties", "getProperties"))
    namespace = {"log": lambda *_: None}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(implementation), "exec"), namespace)
    root = ET.parse(template).getroot()
    instance = SimpleNamespace(tree=root)
    cases = 0
    for group in root.iter():
        if not group.findall("property[@name='widgetExpandable']"):
            continue
        for supplied, expected in ((None, "false"), ("", "false"),
                                   ("false", "false"), ("true", "true")):
            item = ET.Element("item", id="100")
            if supplied is not None:
                ET.SubElement(item, "property", name="widgetExpandable").text = supplied
            properties = namespace[method.name](instance, group, item)
            assert properties["widgetExpandable"] == expected, (group.tag, supplied, expected)
            for flag in group.iterfind(".//param[@name='widgetExpandable']"):
                assert flag.get("value") == "$SKINSHORTCUTS[widgetExpandable]"
                expanded = flag.get("value").replace("$SKINSHORTCUTS[widgetExpandable]",
                                                      properties["widgetExpandable"])
                assert expanded in ("true", "false")
            cases += 1
    assert cases == 12, cases
    return cases, hashlib.sha256(data).hexdigest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--implementation", required=True, type=Path)
    parser.add_argument("--template", required=True, type=Path)
    args = parser.parse_args()
    count, sha = verify(args.implementation, args.template)
    print(f"INSTALLED_SKINSHORTCUTS_PROPERTY_RESOLVER=PASS cases={count} source_sha256={sha}")
