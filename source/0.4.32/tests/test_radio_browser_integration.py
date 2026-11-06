"""Radio Browser remains official and unmodified; test only AcTweeteR-owned integration."""
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from test_menu_contract import ADDON, SERVICE_LIB, shortcuts, interface_layout

ROOT = Path(__file__).resolve().parents[3]
FEED = ROOT/'docs/testing/repo'
RADIO = 'plugin.audio.radiobrowser'
SPAIN = 'ActivateWindow(Music,plugin://plugin.audio.radiobrowser/?route=country&countrycode=ES,return)'


def test_radio_below_tv_and_native_route():
    rows = shortcuts('mainmenu.DATA.xml')
    ids = [item[2] for item in rows]
    assert ids.index('radio') == ids.index('livetv') + 1
    assert rows[ids.index('radio')][1] == SPAIN
    assert len(ids) == len(set(ids)) == 9


def test_radio_submenu_exposes_native_all_countries_favorites_search():
    items = ET.parse(ADDON/'shortcuts/radio.DATA.xml').getroot().findall('shortcut')
    assert [item.findtext('defaultID') for item in items] == [
        'radio-espana', 'radio-mundo', 'radio-favoritas', 'radio-buscar']
    assert items[0].findtext('action') == SPAIN
    assert items[1].findtext('action') == 'ActivateWindow(Music,plugin://plugin.audio.radiobrowser/,return)'
    assert '?route=mystations' in items[2].findtext('action')
    assert '?route=search' in items[3].findtext('action')
    assert 'skin.actweeter-radio.DATA.xml' in interface_layout.source_documents(ADDON)


def test_touch_remote_switch_only_in_skin_settings():
    home = ET.parse(ADDON/'1080i/IncludesBingie.xml').getroot()
    assert not any((element.text or '').strip() == 'AcTweeteRInputModeSideMenu'
                   for element in home.findall('.//include'))
    settings = ET.parse(ADDON/'1080i/IncludesSkinSettings.xml').getroot()
    assert any((element.text or '').strip() == 'AcTweeteRInputModeSettings'
               for element in settings.findall('.//include'))
    touch = ET.parse(ADDON/'1080i/IncludesTouchMode.xml').getroot()
    assert touch.find(".//control[@id='43881']") is not None
    assert touch.find(".//control[@id='43882']") is not None
    menu = home.find(".//control[@id='900'][@type='list']")
    assert int(menu.findtext('height')) >= 9 * 82
    assert int(menu.findtext('top')) + int(menu.findtext('height')) < 909


def test_existing_profile_adds_radio_without_moving_custom_items():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        profile = base/'shortcuts'; profile.mkdir()
        service = base/'service'; service.mkdir()
        root = ET.parse(ADDON/'shortcuts/mainmenu.DATA.xml').getroot()
        root.remove(root.find("shortcut[defaultID='radio']"))
        custom = ET.SubElement(root,'shortcut')
        ET.SubElement(custom,'defaultID').text = 'my-stream'
        ET.SubElement(custom,'label').text = 'Mi Radio'
        ET.SubElement(custom,'label2')
        ET.SubElement(custom,'action').text = 'ActivateWindow(Settings)'
        before_custom = ET.tostring(custom)
        old = ET.tostring(root)
        path = profile/'skin.actweeter-mainmenu.DATA.xml'
        path.write_bytes(old)
        result = interface_layout.apply_layout(profile, service, ADDON, interface_layout.SETTINGS)
        assert result['status']=='APPLIED'
        items = ET.parse(path).getroot()
        ids = [item.findtext('defaultID') for item in items]
        assert ids.index('radio') == ids.index('livetv') + 1
        assert ids[-1] == 'my-stream'
        assert ET.tostring(items.find("shortcut[defaultID='my-stream']")) == before_custom
        assert (service/'interface_backups'/result['backup']/path.name).read_bytes()==old
        assert interface_layout.apply_layout(profile,service,ADDON,interface_layout.SETTINGS)['status']=='CURRENT'


def test_native_existing_custom_radio_is_preserved():
    defaults = (ADDON/'shortcuts/mainmenu.DATA.xml').read_bytes()
    root = ET.fromstring(defaults)
    radio = root.find("shortcut[defaultID='radio']")
    radio.find('action').text = 'RunScript(personal.radio)'
    previous = ET.tostring(root)
    assert interface_layout.merge_radio_shortcut(previous, defaults) == previous
    root.remove(radio)
    custom = ET.SubElement(root,'shortcut')
    ET.SubElement(custom,'defaultID').text='radio-personal'
    ET.SubElement(custom,'action').text=SPAIN
    previous = ET.tostring(root)
    assert interface_layout.merge_radio_shortcut(previous,defaults)==previous


def test_official_addon_is_required_without_bundling():
    import sys
    sys.path.insert(0,str(SERVICE_LIB))
    from module_catalog import all_addons, installation_plan
    addon = all_addons()[RADIO]
    assert addon['minimum']=='2.0.0'
    assert addon['repositories']==('repository.xbmc.org',)
    assert RADIO in [r['id'] for r in installation_plan('android')]
    assert RADIO in [r['id'] for r in installation_plan('tvos')]
    assert not (ROOT/'docs/testing/repo'/RADIO).exists()
    assert not (ROOT/'source/0.4.32/third_party'/RADIO).exists()


def test_published_candidates_retained_worldtv_stable_and_crc():
    versions = {item.get('id'):item.get('version') for item in ET.parse(FEED/'addons.xml').getroot()}
    assert versions['skin.actweeter']=='1.2.44~beta2'
    assert versions['service.actweeter']=='0.4.104~beta1'
    assert versions['plugin.video.launcherm3u']=='1.3.3~beta1'
    assert hashlib.md5((FEED/'addons.xml').read_bytes()).hexdigest()==(FEED/'addons.xml.md5').read_text().strip()
    for addon_id in ('service.actweeter','skin.actweeter'):
        version = versions[addon_id]
        with zipfile.ZipFile(FEED/addon_id/f'{addon_id}-{version}.zip') as archive:
            assert archive.testzip() is None
            manifest = ET.fromstring(archive.read(addon_id+'/addon.xml'))
            assert manifest.get('version')==version
            if addon_id == 'service.actweeter':
                assert manifest.find("requires/import[@addon='plugin.audio.radiobrowser']").get('version')=='2.0.0'
                assert manifest.find("requires/import[@addon='plugin.video.launcherm3u']") is not None
            else:
                assert manifest.find("requires/import[@addon='service.actweeter']").get('version')=='0.4.104~beta1'
                assert 'radio.DATA.xml' in '\n'.join(archive.namelist())
