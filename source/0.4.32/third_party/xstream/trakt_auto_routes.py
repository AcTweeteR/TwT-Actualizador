"""Kodi-facing opt-in and scheduler routes; authentication stays in XStream."""
import json
import sys
from pathlib import Path


def _binding(context, trakt, xbmcaddon, xbmcvfs):
    from trakt_live_queue import provider_fingerprint
    profile = str(context('pm').active)
    creds = context('pm').get_credentials()
    scope = provider_fingerprint(profile, creds.get('source_type'),
        creds.get('xtream_url'), creds.get('xtream_username'), creds.get('m3u_url'))
    current, _ = trakt.request('/users/settings', {}, auth=True)
    account = str(current.get('user', {}).get('ids', {}).get('slug', ''))
    service = xbmcaddon.Addon('service.actweeter')
    service_root = Path(xbmcvfs.translatePath(service.getAddonInfo('profile')))
    return account, profile, scope, service_root


def consent_route(context, guard, trakt, xbmcaddon, xbmcgui, xbmcplugin, xbmcvfs):
    if not guard(auth=True) or not trakt.authorized():
        return
    account, profile, scope, root = _binding(context, trakt, xbmcaddon, xbmcvfs)
    if not account or not scope:
        raise PermissionError('verified Trakt account and provider scope required')
    accepted = xbmcgui.Dialog().yesno(
        'AcTweeteR Trakt',
        'Autorizar la sincronización automática de vistos y avances de Trakt '
        'en el perfil XStream activo? Puedes revocarla desde AcTweeteR.')
    if accepted:
        service_path = Path(xbmcvfs.translatePath(
            xbmcaddon.Addon('service.actweeter').getAddonInfo('path'))) / 'resources'
        if str(service_path) not in sys.path:
            sys.path.insert(0, str(service_path))
        from lib.trakt_sync_consent import grant
        grant(root / 'trakt_live' / 'consent.json', account=account,
              profile=profile, provider_scope=scope)
        message = 'Sincronización automática autorizada para el perfil activo'
    else:
        message = 'No se modificó la autorización de sincronización'
    item = context('_new_listitem')(message)
    xbmcplugin.addDirectoryItem(context('addon_handle'), '', item, isFolder=False)
    xbmcplugin.endOfDirectory(context('addon_handle'), cacheToDisc=False)


def cycle_route(context, guard, trakt, xbmcaddon, xbmc, xbmcplugin, xbmcvfs,
                *, one_shot=False):
    if not guard(auth=True) or not trakt.authorized():
        return
    player = xbmc.Player()
    playing = player.getPlayingFile() if player.isPlaying() else ''
    if playing:
        return
    if one_shot and not __import__('xbmcgui').Dialog().yesno(
            'AcTweeteR Trakt',
            'Aplicar una sola vez los estados vistos y avances de Trakt al perfil XStream activo? '
            'No se activará la sincronización automática ni se enviarán cambios a Trakt.'):
        return
    account, profile, scope, service_root = _binding(
        context, trakt, xbmcaddon, xbmcvfs)
    service_path = Path(xbmcvfs.translatePath(
        xbmcaddon.Addon('service.actweeter').getAddonInfo('path'))) / 'resources'
    if str(service_path) not in sys.path:
        sys.path.insert(0, str(service_path))
    from lib.trakt_sync_consent import authorized, suspend
    from lib.trakt_sync_scheduler import record_result
    consent_path = service_root / 'trakt_live' / 'consent.json'
    if not one_shot and not authorized(consent_path, account=account, profile=profile,
                                       provider_scope=scope):
        suspend(consent_path)
        return

    addon = context('addon')
    xstream_root = Path(xbmcvfs.translatePath(addon.getAddonInfo('profile')))
    import history
    import trakt_live_consumer
    import trakt_snapshot
    from lib.trakt_auto_cycle import run_cycle

    def activity_get():
        user, _ = trakt.request('/users/settings', {}, auth=True)
        activity, _ = trakt.request('/sync/last_activities', {}, auth=True)
        slug = str(user.get('user', {}).get('ids', {}).get('slug', ''))
        if not isinstance(activity, dict) or not isinstance(activity.get('all'), str):
            raise ValueError('invalid Trakt activity response')
        return slug, activity

    def export_snapshot():
        folder = xstream_root / 'trakt_exports'
        before = {path.name for path in folder.glob('snapshot-*')} if folder.exists() else set()
        trakt_snapshot.export_snapshot(
            lambda path, query: trakt.request(path, query, auth=True), folder, profile)
        created = [path for path in folder.glob('snapshot-*')
                   if path.is_dir() and path.name not in before]
        if len(created) != 1:
            raise OSError('snapshot output is ambiguous')
        return created[0]

    try:
        result = run_cycle(service_root, xstream_root, account=account, profile=profile,
            provider_scope=scope, activity_get=activity_get,
            export_snapshot=export_snapshot, apply_batch=trakt_live_consumer.apply_batch,
            addon=addon, history=history, playing_file=playing, consent_path=consent_path,
            one_shot=one_shot)
        for _ in range(3):
            if result.get('status') not in ('queued', 'pending'):
                break
            result = run_cycle(service_root, xstream_root, account=account, profile=profile,
                provider_scope=scope, activity_get=activity_get,
                export_snapshot=export_snapshot,
                apply_batch=trakt_live_consumer.apply_batch, addon=addon,
                history=history, playing_file=playing, consent_path=consent_path,
                one_shot=one_shot)
        if not one_shot:
            record_result(service_root / 'trakt_live' / 'scheduler.json',
                          success=result.get('status') in ('applied', 'unchanged', 'deferred', 'busy', 'pending'),
                          now=__import__('time').time())
        if result.get('status') == 'applied' and result.get('operations', 0):
            xbmc.executebuiltin(
                'RunPlugin(plugin://service.actweeter/?action=trakt_continue_refresh)', False)
    except Exception as exc:
        if not one_shot:
            record_result(service_root / 'trakt_live' / 'scheduler.json',
                          success=False, now=__import__('time').time())
        xbmc = __import__('xbmc')
        xbmc.log('[AcTweeteR] TRAKT_SYNC_CYCLE failed error_type=%s' %
                 type(exc).__name__, xbmc.LOGWARNING)
        result = {'status': 'failed', 'error_type': type(exc).__name__}
    item = context('_new_listitem')('AcTweeteR Trakt sync: ' + result['status'])
    item.setProperty('actweeter.trakt.sync', json.dumps(result, sort_keys=True))
    xbmcplugin.addDirectoryItem(context('addon_handle'), '', item, isFolder=False)
    xbmcplugin.endOfDirectory(context('addon_handle'), cacheToDisc=False)


def sync_once_route(context, guard, trakt, xbmcaddon, xbmc, xbmcplugin, xbmcvfs):
    return cycle_route(context, guard, trakt, xbmcaddon, xbmc, xbmcplugin,
                       xbmcvfs, one_shot=True)
