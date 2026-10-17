"""Verify XStream's pinned local PVR sources without reading stream credentials."""

import os
import re
from xml.etree import ElementTree as ET


def instance_matches(payload, expected_m3u, expected_epg, translate):
    try:
        root = ET.fromstring(payload)
        values = {node.get("id"): node.text or "" for node in root.iter("setting")}
        return (values.get("m3uPathType") == "0"
                and os.path.normpath(translate(values.get("m3uPath", ""))) == os.path.normpath(expected_m3u)
                and (not values.get("epgPath") or (values.get("epgPathType") == "0"
                     and os.path.normpath(translate(values["epgPath"])) == os.path.normpath(expected_epg))))
    except (ET.ParseError, TypeError, ValueError, OSError):
        return False


def profile_is_bound(xstream_profile, profile_number, pvr_profile, vfs):
    """Inspect only instance metadata; M3U/XMLTV contents are never read."""
    if type(profile_number) is not int or not 1 <= profile_number <= 10:
        return False
    expected_m3u = os.path.join(xstream_profile, "pvr_live_xstream_pro_p%d.m3u8" % profile_number)
    expected_epg = os.path.join(xstream_profile, "pvr_epg_xstream_pro_p%d.xml" % profile_number)
    if not vfs.exists(expected_m3u):
        return False
    try:
        _directories, filenames = vfs.listdir(pvr_profile)
        for filename in filenames:
            if not re.fullmatch(r"instance-settings-[0-9]+\.xml", filename):
                continue
            handle = vfs.File(os.path.join(pvr_profile, filename))
            try:
                if instance_matches(handle.read(), expected_m3u, expected_epg, vfs.translatePath):
                    return True
            finally:
                handle.close()
    except Exception:
        return False
    return False
