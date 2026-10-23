"""Apply PKCE UI integration to a staged XStream addon directory, not live Kodi."""
from pathlib import Path
import shutil

REDIRECT = 'https://github.com/AcTweeteR/TwT-Actualizador'


def apply(addon):
    lib = Path(addon) / 'resources/lib'
    trakt = lib / 'trakt.py'
    routes = lib / 'tmdb_routes.py'
    source = Path(__file__).with_name('trakt_pkce.py')
    if not trakt.is_file() or not routes.is_file():
        raise ValueError('Not an XStream addon')
    old = trakt.read_text('utf-8')
    marker = '\ndef pkce_exchange_callback(callback_url, session):\n'
    if marker not in old:
        old += '''\n\ndef pkce_exchange_callback(callback_url, session):
    import trakt_pkce
    return trakt_pkce.exchange(client_id(), session, callback_url,
                               _session().post, _write_tokens)
'''
    original = routes.read_text('utf-8')
    start = original.index('def trakt_authorize_route(params):')
    end = original.index('\ndef trakt_revoke_route(params):', start)
    replacement = '''def trakt_authorize_route(params):
    if not trakt.enabled() or not trakt.auth_configured():
        xbmcgui.Dialog().notification("Xstream Pro", _t(31228))
        xbmcplugin.endOfDirectory(c("addon_handle"), succeeded=False)
        return
    try:
        import trakt_pkce
        session = trakt_pkce.begin(trakt.client_id(), "''' + REDIRECT + '''")
        xbmcgui.Dialog().textviewer("Trakt PKCE: open this URL", session['url'])
        callback = xbmcgui.Dialog().input(
            "Paste the FULL redirected URL from your browser", type=xbmcgui.INPUT_ALPHANUM)
        if callback:
            trakt.pkce_exchange_callback(callback.strip(), session)
            xbmcgui.Dialog().notification("Xstream Pro", _t(31257))
            xbmc.executebuiltin("Container.Refresh")
    except Exception as exc:
        c("_log")("Trakt PKCE authorization error: {0}".format(type(exc).__name__))
        xbmcgui.Dialog().notification("Xstream Pro", _label("Trakt authorization failed"))
    xbmcplugin.endOfDirectory(c("addon_handle"), succeeded=False)

'''
    revised = original[:start] + replacement + original[end:]
    trakt.write_text(old, encoding='utf-8')
    routes.write_text(revised, encoding='utf-8')
    shutil.copyfile(source, lib / 'trakt_pkce.py')


if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:
        raise SystemExit('usage: apply_trakt_pkce.py STAGED_XSTREAM_ADDON_DIR')
    apply(sys.argv[1])
