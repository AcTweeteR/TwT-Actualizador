"""Consent-based, reversible local integration; never redistribute SlyGuy files."""
import hashlib
import json
import re
import uuid
from pathlib import Path
from interface_layout import atomic_write,load_state

ORIGINAL_HASHES={
    'service.py':'8b15305e9c5124936d401682845d35f3517fa580f293a8a81f7f170ba454f801',
    'resources/lib/youtube.py':'dc32017643a004c89beb22ef786ab1c0ab1bab5b1702d86fba5e6bbadfdd8728',
}
HOOK=b'''
# AcTweeteR managed preview bridge; original SlyGuy settings remain unchanged.
try:
    import os
    import sys
    from kodi_six import xbmc, xbmcaddon, xbmcvfs
    actweeter = xbmcaddon.Addon("service.actweeter")
    actweeter_lib = os.path.join(xbmcvfs.translatePath(actweeter.getAddonInfo("path")), "resources", "lib")
    if actweeter_lib not in sys.path:
        sys.path.insert(0, actweeter_lib)
    from slyguy_preview_bridge import run_slyguy_service
    run_slyguy_service()
except Exception as exc:
    try:
        xbmc.log("[SlyGuy] AcTweeteR preview bridge unavailable type=%s" % type(exc).__name__, xbmc.LOGINFO)
    except Exception:
        pass
'''

def digest(data):return hashlib.sha256(data).hexdigest()

def payloads(originals,hashes=ORIGINAL_HASHES):
    for name,expected in hashes.items():
        if digest(originals[name])!=expected:raise ValueError('unrecognized official SlyGuy source')
    service=originals['service.py']+HOOK
    youtube=originals['resources/lib/youtube.py']
    old=b'def play_yt_dlp(video_id):'
    destination=b"path = 'special://temp/yt.mpd'"
    if youtube.count(old)!=1 or youtube.count(destination)!=1:raise ValueError('unexpected SlyGuy resolver layout')
    youtube=youtube.replace(old,b'def play_yt_dlp(video_id, manifest_path=None):')
    youtube=youtube.replace(destination,b"path = manifest_path or 'special://temp/yt.mpd'")
    result={'service.py':service,'resources/lib/youtube.py':youtube}
    for name,data in result.items():compile(data,name,'exec')
    return result

def install(kodi,addon_factory,vfs,dialog,*,consent=False,allow_prompt=False,writer=atomic_write):
    if kodi.getCondVisibility('Player.HasMedia'):return 'PLAYER_ACTIVE'
    service=addon_factory('service.actweeter')
    root=Path(vfs.translatePath(service.getAddonInfo('profile')))
    state_path=root/'slyguy_bridge_integration.json';state=load_state(state_path)
    addon=addon_factory('slyguy.trailers')
    # Compatibility is established by recognized source signatures, not a
    # pinned add-on version. Unknown layouts remain fail-closed.
    addon_version = addon.getAddonInfo('version')
    source=Path(vfs.translatePath(addon.getAddonInfo('path')))
    originals={name:(source/name).read_bytes() for name in ORIGINAL_HASHES}
    current={name:digest(data) for name,data in originals.items()}
    if state.get('disabled_by_user') and not consent:return 'DISABLED_BY_ROLLBACK'
    if state.get('patched_hashes')==current:return 'CURRENT'
    if not (consent or state.get('consent')):
        if not allow_prompt:return 'CONSENT_REQUIRED'
        consent=dialog.yesno('Previews de AcTweeteR',
            'Para los previews automáticos, AcTweeteR necesita conectar su bridge al servicio instalado de SlyGuy. Se guardará una copia y no se cambiarán tus preferencias. ¿Autorizar esta integración local?',
            nolabel='Ahora no',yeslabel='Autorizar')
        if not consent:return 'DECLINED'
    patched=payloads(originals)
    backup=root/'slyguy_bridge_backups'/uuid.uuid4().hex[:12]
    backup.mkdir(parents=True,mode=0o700)
    for name,data in originals.items():
        if (source/name).is_symlink():raise ValueError('SlyGuy source symlink refused')
        target=backup/name;atomic_write(target,data)
        if target.read_bytes()!=data:raise OSError('SlyGuy backup readback failed')
    atomic_write(backup/'MANIFEST.json',json.dumps({'schema':1,'status':'BACKUP_VERIFIED',
                 'original_hashes':current,'version':addon_version},sort_keys=True).encode())
    rpc=lambda enabled:json.loads(kodi.executeJSONRPC(json.dumps({'jsonrpc':'2.0','id':1,
        'method':'Addons.SetAddonEnabled','params':{'addonid':'slyguy.trailers','enabled':enabled}})))
    try:
        for name,data in patched.items():
            writer(source/name,data)
            if (source/name).read_bytes()!=data:raise OSError('SlyGuy integration readback failed')
        if rpc(False).get('result')!='OK':raise OSError('SlyGuy native restart refused')
        if rpc(True).get('result')!='OK':raise OSError('SlyGuy native enable refused')
        report={'schema':1,'version':addon_version,'status':'INSTALLED_NOT_RUNTIME_VERIFIED','consent':True,
                'backup':backup.name,'original_hashes':current,
                'patched_hashes':{name:digest(data) for name,data in patched.items()}}
        atomic_write(backup/'MANIFEST.json',json.dumps(report,sort_keys=True).encode())
        atomic_write(state_path,json.dumps(report,sort_keys=True).encode())
    except Exception:
        for name,data in originals.items():atomic_write(source/name,data)
        rpc(True)
        raise
    return 'INSTALLED_NOT_RUNTIME_VERIFIED'

def rollback(kodi,addon_factory,vfs):
    if kodi.getCondVisibility('Player.HasMedia'):return 'PLAYER_ACTIVE'
    root=Path(vfs.translatePath(addon_factory('service.actweeter').getAddonInfo('profile')))
    state_path=root/'slyguy_bridge_integration.json';state=load_state(state_path)
    backup_id=state.get('backup','')
    if not re.fullmatch(r'[a-f0-9]{12}',backup_id):return 'NO_VERIFIED_BACKUP'
    source=Path(vfs.translatePath(addon_factory('slyguy.trailers').getAddonInfo('path')))
    if any(digest((source/name).read_bytes())!=state.get('patched_hashes',{}).get(name)
           for name in ORIGINAL_HASHES):return 'USER_CHANGES_PRESERVED'
    backup=root/'slyguy_bridge_backups'/backup_id
    data={name:(backup/name).read_bytes() for name in ORIGINAL_HASHES}
    if any(digest(value)!=state.get('original_hashes',{}).get(name) for name,value in data.items()):
        raise OSError('SlyGuy backup integrity mismatch')
    for name,value in data.items():atomic_write(source/name,value)
    for enabled in (False,True):
        result=json.loads(kodi.executeJSONRPC(json.dumps({'jsonrpc':'2.0','id':1,
            'method':'Addons.SetAddonEnabled','params':{'addonid':'slyguy.trailers','enabled':enabled}})))
        if result.get('result')!='OK':raise OSError('SlyGuy restart failed after rollback')
    state.update(status='ROLLED_BACK',disabled_by_user=True,patched_hashes={})
    atomic_write(state_path,json.dumps(state,sort_keys=True).encode())
    return 'ROLLED_BACK'
