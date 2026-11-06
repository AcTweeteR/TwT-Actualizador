"""WorldTV is a stand-alone add-on, preconfigured without touching PVR."""
from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
WORLDTV_ID = "plugin.video.launcherm3u"
PLAYLIST = "https://iptv-org.github.io/iptv/index.country.m3u"
EPG = "https://raw.githubusercontent.com/teleonline/listas/main/epg.xml.gz"


def get_configure():
    filename = (ROOT / "source/0.4.32/addons/service.actweeter/"
                "resources/lib/worldtv_setup.py")
    spec = importlib.util.spec_from_file_location("worldtv_setup", filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.configure


class FakeAddon:
    def __init__(self, **settings):
        self.settings = dict(settings)
        self.writes = []

    def getSetting(self, key):
        return self.settings.get(key, "")

    def setSetting(self, key, value):
        self.settings[key] = value
        self.writes.append((key, value))


def test_new_profile_has_worldtv_configuration():
    addon = FakeAddon()
    assert get_configure()(lambda name: addon) == "configured"
    assert addon.settings["m3u_url"] == PLAYLIST
    assert addon.settings["m3u_type"] == "1"
    assert addon.settings["epg_url"] == EPG
    assert addon.settings["epg_type"] == "1"
    assert addon.settings["epg_enabled"] == "true"
    assert addon.settings["auto_url_tvg"] == "false"


def test_existing_custom_playlist_preserved_without_changes():
    addon = FakeAddon(m3u_url="https://example.com/personal.m3u",
                      epg_url="https://example.com/private.xml")
    assert get_configure()(lambda name: addon) == "custom_source_preserved"
    assert addon.writes == []


def test_existing_epg_preserved():
    addon = FakeAddon(m3u_url=PLAYLIST, epg_url="https://example.com/my.xml")
    assert get_configure()(lambda name: addon) == "already_configured"
    assert addon.settings["epg_url"] == "https://example.com/my.xml"


def test_absent_addon_does_not_fail_service_boot():
    def missing(_):
        raise RuntimeError("Addon not installed")
    assert get_configure()(missing) == "not_installed"


def test_beta_packages_are_separate_from_provider_pvr():
    folder = ROOT / "docs/testing/repo"
    versions = {
        WORLDTV_ID: "1.3.3~beta1",
        "service.actweeter": "0.4.103~beta1",
        "skin.actweeter": "1.2.43~beta3",
    }
    index = ET.parse(folder / "addons.xml").getroot()
    indexed = {addon.get("id"): addon for addon in index}
    for addon_id, version in versions.items():
        assert indexed[addon_id].get("version") == version
        path = folder / addon_id / f"{addon_id}-{version}.zip"
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
            manifest = ET.fromstring(archive.read(f"{addon_id}/addon.xml"))
            assert manifest.get("version") == version
            if addon_id == "service.actweeter":
                requirements = {i.get("addon") for i in manifest.findall("./requires/import")}
                assert WORLDTV_ID in requirements
                assert "pvr.iptvsimple" in requirements
            elif addon_id == "skin.actweeter":
                menu = ET.fromstring(archive.read("skin.actweeter/shortcuts/livetv.DATA.xml"))
                world = [n for n in menu.findall("shortcut")
                         if n.findtext("defaultID") == "worldtv-launcher"]
                assert len(world) == 1
                assert world[0].findtext("action") == "RunAddon(plugin.video.launcherm3u)"
                assert len(menu.findall("shortcut")) == 6
            else:
                settings = ET.fromstring(archive.read(
                    f"{WORLDTV_ID}/resources/settings.xml"))
                defaults = {
                    n.get("id"): n.findtext("default") for n in settings.findall(".//setting")}
                assert defaults["m3u_url"] == PLAYLIST
                assert defaults["epg_url"] == EPG
                assert defaults["auto_refresh_hours"] == "12"
                resolver = archive.read(f"{WORLDTV_ID}/resources/lib/cache.py").decode()
                assert "candidates.insert(candidates.index(candidate) + 1, base)" in resolver


def test_existing_custom_tv_submenu_is_extended_not_replaced():
    import sys
    import tempfile
    sys.path.insert(0, str(ROOT / "source/0.4.32/addons/service.actweeter/resources/lib"))
    import interface_layout as layout
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        profile = directory / "shortcuts"
        service = directory / "service"
        profile.mkdir()
        service.mkdir()
        filename = "skin.actweeter-livetv.DATA.xml"
        existing = (
            b"<shortcuts><shortcut><defaultID>custom-entry</defaultID>"
            b"<label>Mi TV</label><label2 /><action>ActivateWindow(TVRecordings)"
            b"</action></shortcut></shortcuts>"
        )
        (profile / filename).write_bytes(existing)
        skin = ROOT / "source/0.4.32/addons/skin.actweeter"
        result = layout.apply_layout(profile, service, skin, layout.SETTINGS)
        assert result["status"] == "APPLIED"
        assert (service / "interface_backups" / result["backup"] / filename).read_bytes() == existing
        items = ET.fromstring((profile / filename).read_bytes()).findall("shortcut")
        assert [x.findtext("defaultID") for x in items] == ["custom-entry", "worldtv-launcher"]
        assert layout.apply_layout(profile, service, skin, layout.SETTINGS)["status"] == "CURRENT"
        again = ET.fromstring((profile / filename).read_bytes()).findall("shortcut")
        assert len(again) == 2
