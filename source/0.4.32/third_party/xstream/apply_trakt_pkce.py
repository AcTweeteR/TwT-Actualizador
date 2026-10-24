"""Preserve XStream's native Device Code flow in a staged add-on, not live Kodi."""
from pathlib import Path
import shutil

def apply(addon):
    lib = Path(addon) / 'resources/lib'
    trakt = lib / 'trakt.py'
    routes = lib / 'tmdb_routes.py'
    source = Path(__file__).with_name('trakt_pkce.py')
    if not trakt.is_file() or not routes.is_file():
        raise ValueError('Not an XStream addon')
    old = trakt.read_text('utf-8')
    original = routes.read_text('utf-8')
    start = original.index('def trakt_authorize_route(params):')
    end = original.index('\ndef trakt_revoke_route(params):', start)
    replacement = '''def trakt_authorize_route(params):
    if not trakt.enabled() or not trakt.auth_configured():
        xbmcgui.Dialog().notification("Xstream Pro", _t(31228))
        xbmcplugin.endOfDirectory(c("addon_handle"), succeeded=False)
        return
    try:
        import time
        session = trakt.device_code()
        user_code = str(session.get("user_code") or "")
        verification_url = str(session.get("verification_url") or "https://trakt.tv/activate")
        device_code = str(session.get("device_code") or "")
        interval = max(5, int(session.get("interval") or 5))
        expires_in = max(1, int(session.get("expires_in") or 600))
        expires = time.monotonic() + expires_in
        xbmcgui.Dialog().ok("Autorizar Trakt",
            "Abre " + verification_url + " e introduce el código " + user_code)
        progress = xbmcgui.DialogProgress()
        progress.create("Autorizando Trakt", "Introduce el código en " + verification_url)
        authorized = False
        try:
            monitor = xbmc.Monitor()
            while (time.monotonic() < expires and not progress.iscanceled()
                   and not monitor.abortRequested()):
                if monitor.waitForAbort(interval):
                    break
                if progress.iscanceled():
                    break
                if trakt.poll_device_token(device_code):
                    authorized = True
                    break
                remaining = max(0, int(expires - time.monotonic()))
                progress.update(min(99, int(100 * (1 - remaining / float(expires_in)))),
                                "Introduce " + user_code + " en " + verification_url)
        finally:
            progress.close()
        if authorized:
            # Grant auto-sync only after authorization and exact provider binding.
            try:
                import sys
                import xbmcaddon, xbmcvfs
                from pathlib import Path
                from trakt_auto_routes import _binding
                account, profile, scope, root = _binding(c, trakt, xbmcaddon, xbmcvfs)
                if account and scope:
                    service_path = Path(xbmcvfs.translatePath(
                        xbmcaddon.Addon("service.actweeter").getAddonInfo("path"))) / "resources"
                    if str(service_path) not in sys.path:
                        sys.path.insert(0, str(service_path))
                    from lib.trakt_sync_consent import grant
                    grant(root / "trakt_live" / "consent.json", account=account,
                          profile=profile, provider_scope=scope)
            except Exception as sync_exc:
                c("_log")("Trakt auto-sync activation unavailable: " + type(sync_exc).__name__)
            xbmcgui.Dialog().notification("Xstream Pro", _t(31257))
            xbmc.executebuiltin("Container.Refresh")
        else:
            xbmcgui.Dialog().notification("Xstream Pro", "Autorización cancelada o caducada")
    except Exception as exc:
        c("_log")("Trakt authorization error: {0}".format(type(exc).__name__))
        xbmcgui.Dialog().notification("Xstream Pro", _label("Trakt authorization failed"))
    xbmcplugin.endOfDirectory(c("addon_handle"), succeeded=False)

'''
    revised = original[:start] + replacement + original[end:]
    routes.write_text(revised, encoding='utf-8')
    shutil.copyfile(source, lib / 'trakt_pkce.py')


if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:
        raise SystemExit('usage: apply_trakt_pkce.py STAGED_XSTREAM_ADDON_DIR')
    apply(sys.argv[1])
