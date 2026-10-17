"""Factory-only defaults that never replace explicit Kodi user choices."""

from __future__ import annotations

import xml.etree.ElementTree as ET


FACTORY_LANGUAGE = "resource.language.en_gb"
ACTWEETER_LANGUAGE = "resource.language.es_es"


def preferred_factory_language(guisettings_xml, current_language):
    """Return Spanish only for Kodi's untouched English factory default."""
    if current_language != FACTORY_LANGUAGE:
        return None
    try:
        root = ET.fromstring(guisettings_xml)
        setting = root.find(".//setting[@id='locale.language']")
    except (ET.ParseError, TypeError, ValueError):
        return None
    if (setting is not None and setting.get("default") == "true"
            and (setting.text or "").strip() == FACTORY_LANGUAGE):
        return ACTWEETER_LANGUAGE
    return None
