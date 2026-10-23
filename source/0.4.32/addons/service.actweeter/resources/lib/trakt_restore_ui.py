"""Read-only Kodi Trakt restoration entrypoint; never commits on click."""
import json
import re
import tempfile
from .trakt_restore_transaction import stage_complete_restore
from pathlib import Path
from .trakt_restore_importer import prepare_restore, preview_changes
from .trakt_restore_startup import startup_restore_status
from .first_run import addon_version_satisfies
from .trakt_sync_consent import enabled as sync_enabled

ROOT = 'plugin://service.actweeter/?action=trakt_restore'
XSTREAM_SNAPSHOT = 'plugin://plugin.video.xstream-pro/?mode=xstream_trakt_snapshot'
XSTREAM_SYNC_ONCE = 'plugin://plugin.video.xstream-pro/?mode=xstream_trakt_sync_once'
XSTREAM_SYNC_CONSENT = 'plugin://plugin.video.xstream-pro/?mode=xstream_trakt_sync_consent'
SYNC_CONSENT = 'plugin://service.actweeter/?action=trakt_sync_consent&operation=revoke'


def active_xstream_profile(addon):
    # Match XStream ProfileManager's public add-on setting and fallback.
    raw = addon.getSetting('active_pvr_profile') or 'Profile 1'
    match = re.search(r'(\d+)$', str(raw))
    return match.group(1) if match else '1'


def summarize_exports(xstream_profile, *, profile):
    root = Path(xstream_profile)
    exports = root / 'trakt_exports'
    if exports.is_symlink() or not exports.is_dir():
        return []
    results = []
    for folder in sorted(exports.glob('snapshot-*'),
                         key=lambda path: (path.stat().st_mtime_ns, path.name)):
        if folder.is_symlink() or not folder.is_dir():
            continue
        try:
            raw = json.loads((folder / 'snapshot.json').read_text('utf-8'))
            account = raw['snapshot']['account']
            if str(raw['profile']) != str(profile):
                continue
            plan = prepare_restore(folder, root, profile=profile, account=account)
            plan = preview_changes(plan, root, profile=profile)['plan']
            results.append({'name': folder.name, 'account': account,
                            'watched_movies': sum(x.get('watched') is True and x['identity']['kind']=='movie' for x in plan['items']),
                            'watched_episodes': sum(x.get('watched') is True and x['identity']['kind']=='episode' for x in plan['items']),
                            'resume_pending': sum('position' in x for x in plan['items'])})
        except (ValueError, TypeError, KeyError, OSError, PermissionError):
            continue
    return results


def render(handle, *, gui, plugin, vfs, xstream_addon, service_addon=None, params=None):
    profile_path = vfs.translatePath(xstream_addon.getAddonInfo('profile'))
    profile = active_xstream_profile(xstream_addon)
    snapshot_supported = addon_version_satisfies(
        xstream_addon.getAddonInfo('version'), '1.1.2.20')
    plugin.setPluginCategory(handle, 'Sincronizar biblioteca con Trakt')
    plugin.setContent(handle, 'files')
    status = startup_restore_status(profile_path)
    pending = status["pending"]
    exports = summarize_exports(profile_path, profile=profile)
    action = (params or {}).get('operation', [''])[0]
    staged_message = None
    if action == 'prepare' and exports and status['safe']:
        newest = exports[-1]
        plan = prepare_restore(Path(profile_path) / 'trakt_exports' / newest['name'],
                               profile_path, profile=profile, account=newest['account'])
        plan = preview_changes(plan, profile_path, profile=profile)['plan']
        with tempfile.TemporaryDirectory(prefix='actweeter-trakt-preview-') as folder:
            result = stage_complete_restore(plan, profile=profile, account=newest['account'],
                xstream_profile=profile_path,
                movie_source=Path(profile_path) / ('watched_movies_p%s.json' % profile),
                episode_source=Path(profile_path) / ('watched_episodes_p%s.json' % profile),
                staging_directory=folder)
            if result['resume_error']:
                staged_message = 'Avances no preparados: el almacén local no pudo validarse; Kodi no se modificó'
            else:
                staged_message = ('Preparación comprobada: %d películas, %d episodios, '
                    '%d avances nuevos, %d actualizados y %d omitidos (sin modificar Kodi)') % (
                        result['movies'], result['episodes'], result['resumes_added'],
                        result['resumes_updated'], result['resumes_deferred'])
    if not status['safe']:
        labels = ['Restauración bloqueada: transacciones pendientes (%d)' % pending,
                  'Recupera los originales con Kodi detenido antes de continuar']
    elif not exports:
        labels = ['Sin exportación verificada de Trakt para este perfil',
                  'Vincula Trakt y realiza primero una exportación completa']
    else:
        newest = exports[-1]
        labels = ['Historial verificado: ' + newest['name'],
                  'Películas vistas recuperables: %d' % newest['watched_movies'],
                  'Episodios vistos recuperables: %d' % newest['watched_episodes'],
                  'Avances pendientes de verificar: %d' % newest['resume_pending'],
                  'Vista previa solamente: la restauración aún no se aplica']
        if staged_message:
            labels.append(staged_message)
    for label in labels:
        item = gui.ListItem(label=label)
        item.setProperty('IsPlayable', 'false')
        plugin.addDirectoryItem(handle, '', item, False)
    if snapshot_supported:
        item = gui.ListItem(label='Obtener snapshot Trakt (solo lectura)')
        item.setProperty('IsPlayable', 'false')
        plugin.addDirectoryItem(handle, XSTREAM_SNAPSHOT, item, True)
    else:
        item = gui.ListItem(label='Actualiza XStream para habilitar la exportación segura')
        item.setProperty('IsPlayable', 'false')
        plugin.addDirectoryItem(handle, '', item, False)
    item = gui.ListItem(label='Sincronizar una vez desde Trakt…')
    item.setProperty('IsPlayable', 'false')
    plugin.addDirectoryItem(handle, XSTREAM_SYNC_ONCE, item, True)
    if service_addon is not None:
        consent_path = (Path(vfs.translatePath(service_addon.getAddonInfo('profile'))) /
                        'trakt_live' / 'consent.json')
        item = gui.ListItem(label=('Revocar sincronización automática Trakt' if
                                   sync_enabled(consent_path) else
                                   'Autorizar sincronización automática Trakt…'))
        item.setProperty('IsPlayable', 'false')
        plugin.addDirectoryItem(handle,
            SYNC_CONSENT if sync_enabled(consent_path) else XSTREAM_SYNC_CONSENT,
            item, True)
    item = gui.ListItem(label='Actualizar estado de exportaciones')
    item.setProperty('IsPlayable', 'false')
    plugin.addDirectoryItem(handle, ROOT + '&operation=refresh', item, True)
    if exports and status['safe']:
        item = gui.ListItem(label='Comprobar preparación segura de la restauración')
        item.setProperty('IsPlayable', 'false')
        plugin.addDirectoryItem(handle, ROOT + '&operation=prepare', item, True)
    plugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)
