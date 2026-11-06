"""Contracts for the current Beta touch-to-native action path."""
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[3]
UI=ROOT/'source/0.4.32/addons/skin.actweeter/1080i'


def test_touch_primary_actions_execute_actual_modal_native_buttons():
    root=ET.parse(UI/'IncludesTouchInfoActions.xml').getroot()
    for control_id,native_id in ((44001,80),(44002,90),(44003,51),
                                 (44004,8181),(44005,53),(44006,54)):
        control=root.find(f".//control[@id='{control_id}']")
        assert control.findtext('visible')==f'Control.IsVisible({native_id})'
        assert [n.text for n in control.findall('onclick')]==[
            f'SetFocus({native_id})','Action(Select)']
    for control_id,native_id in ((44100,80),(44101,90),(44102,51),
                                 (44103,8181),(44104,52),(44105,53),(44106,54)):
        control=root.find(f".//control[@id='{control_id}']")
        assert control.findtext('visible')==f'Control.IsVisible({native_id})'
        assert [n.text for n in control.findall('onclick')]==[
            f'SetFocus({native_id})','Action(Select)',
            'ClearProperty(AcTweeteRTouchInfoActions,Home)']


def test_original_trailer_playback_path_is_not_reimplemented():
    info=ET.parse(UI/'IncludesDialogVideoInfo.xml').getroot()
    funcs=ET.parse(UI/'IncludesFunctions.xml').getroot()
    native=funcs.find("include[@name='AcTweeteR_Primary_Trailer_Action']")
    assert native is not None
    assert any('RunScript(slyguy.trailers' in (n.text or '') for n in native.findall('onclick'))
    for layout in ('BingieInfo','BingieAltInfo'):
        control=info.find(f"include[@name='{layout}']//control[@id='54']")
        assert control is not None
        assert any((n.text or '').strip()=='AcTweeteR_Primary_Trailer_Action'
                   for n in control.findall('include'))


def test_automatic_preview_settings_are_selectable_with_slyguy_alone():
    root=ET.parse(UI/'IncludesSkinSettings.xml').getroot()
    for action in ('Skin.ToggleSetting(SpotLightTrailers)',
                   'Skin.ToggleSetting(BingieAutoTrailer)'):
        nodes=[n for n in root.iter('onclick') if (n.text or '').strip()==action]
        assert len(nodes)==1
        assert 'System.HasAddon(slyguy.trailers) | ' in nodes[0].get('condition','')


def test_remote_controls_and_normal_widget_bodies_are_unmodified():
    import zipfile
    archive=ROOT/'docs/testing/repo/skin.actweeter/skin.actweeter-1.2.44~beta1.zip'
    with zipfile.ZipFile(archive) as z:
        for filename in ('IncludesDialogVideoInfo.xml','IncludesHomeWidgets.xml',
                         'IncludesBingie.xml','Home.xml'):
            assert z.read('skin.actweeter/1080i/'+filename)==(UI/filename).read_bytes()
