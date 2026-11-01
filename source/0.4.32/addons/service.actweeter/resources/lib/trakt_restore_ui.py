"""Read-only Kodi Trakt restoration entrypoint; never commits on click."""
import hashlib
import json
import uuid
import re
import shutil
import tempfile
from datetime import datetime
from .trakt_restore_transaction import stage_complete_restore
from .trakt_restore_plan import prepare as persist_restore_plan
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


def sync_status_labels(service_profile):
    """Show only persisted scheduler and queue facts, never infer sync success."""
    root = Path(service_profile) / 'trakt_live'
    if root.is_symlink():
        return ['Estado de sincronización no disponible']
    labels = []
    scheduler = root / 'scheduler.json'
    try:
        if scheduler.is_symlink() or scheduler.stat().st_size > 4096:
            raise ValueError('unsafe scheduler')
        state = json.loads(scheduler.read_text('utf-8'))
        if not isinstance(state, dict):
            raise ValueError('invalid scheduler')
        next_at = state.get('next_at')
        failures = state.get('failures')
        if isinstance(next_at, (int, float)) and 0 < next_at < 253402300800:
            labels.append('Próxima ejecución prevista: ' + datetime.fromtimestamp(next_at).strftime('%Y-%m-%d %H:%M'))
        if isinstance(failures, int) and failures >= 0:
            labels.append('Fallos consecutivos del planificador: %d' % failures)
    except (OSError, ValueError, TypeError, OverflowError):
        labels.append('Planificación de sincronización no disponible')
    queue = root / 'queue'
    try:
        if queue.is_symlink():
            raise ValueError('unsafe queue')
        if queue.is_dir():
            labels.append('Lotes pendientes de importar (todos los perfiles): %d' %
                          sum(1 for path in queue.glob('*.json') if path.is_file() and not path.is_symlink()))
    except (OSError, ValueError):
        labels.append('Cola de importación no disponible')
    return labels


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
    if action in ('prepare', 'confirm') and exports and status['safe']:
        newest = exports[-1]
        plan = prepare_restore(Path(profile_path) / 'trakt_exports' / newest['name'],
                               profile_path, profile=profile, account=newest['account'],
                               include_candidates=True)
        active = [Path(profile_path) / ('watched_movies_p%s.json' % profile),
                  Path(profile_path) / ('watched_episodes_p%s.json' % profile),
                  Path(profile_path) / ('resume_points_p%s.json' % profile)]
        hashes = [hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() and not p.is_symlink()
                  else None for p in active]
        plan = preview_changes(plan, profile_path, profile=profile)['plan']
        identity_summary = plan.get('identity_resolution', {})
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
                if identity_summary.get('candidate_trakt_items') is not None:
                    staged_message += ('; %d coincidencias textuales siguen sin verificar, '
                                       '%d conflictos requieren revisión' % (
                                           identity_summary['candidate_trakt_items'],
                                           identity_summary['conflicts']))
                if action == 'confirm' and service_addon is not None:
                    if gui.Dialog().yesno('Trakt', staged_message +
                            '\n¿Guardar este plan para una futura aplicación segura?'):
                        try:
                            service_root = Path(vfs.translatePath(service_addon.getAddonInfo('profile')))
                            plans = service_root / 'trakt_restore_plans'
                            if service_root.is_symlink() or plans.is_symlink():
                                raise ValueError('unsafe restore plan directory')
                            plans.mkdir(mode=0o700, parents=True, exist_ok=True)
                            if plans.stat().st_mode & 0o077:
                                raise PermissionError('restore plan directory must be private')
                            persist_restore_plan(plans / ('plan-' + uuid.uuid4().hex),
                                staged=[result['movie_path'], result['episode_path'], result['resume_path']],
                                active=active, expected_active_sha256=hashes,
                                account=newest['account'], profile=profile, confirmed=True)
                        except (OSError, ValueError, RuntimeError):
                            staged_message = 'No se guardó el plan: datos cambiados o no disponibles; vuelve a preparar la vista previa'
                        else:
                            staged_message = 'Plan confirmado y guardado; todavía no se ha aplicado'
                    else:
                        staged_message = 'Plan no guardado; Kodi no se modificó'
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
    if service_addon is not None:
        labels.extend(sync_status_labels(vfs.translatePath(service_addon.getAddonInfo('profile'))))
    plans_root = None
    plans = []
    if service_addon is not None:
        plans_root = Path(vfs.translatePath(service_addon.getAddonInfo('profile'))) / 'trakt_restore_plans'
        if not plans_root.is_symlink() and plans_root.is_dir():
            for folder in sorted(plans_root.glob('plan-*')):
                manifest = folder / 'plan.json'
                if (not re.fullmatch(r'plan-[0-9a-f]{32}', folder.name) or folder.is_symlink()
                        or not folder.is_dir() or manifest.is_symlink() or not manifest.is_file()):
                    continue
                try:
                    if manifest.stat().st_size > 8192:
                        continue
                    saved = json.loads(manifest.read_text('utf-8'))
                    if saved.get('schema') == 1 and saved.get('profile') == profile:
                        plans.append(folder)
                except (OSError, ValueError, TypeError, AttributeError):
                    continue
        plan_id = (params or {}).get('plan', [''])[0]
        if action == 'cancel_plan' and any(folder.name == plan_id for folder in plans):
            folder = next(folder for folder in plans if folder.name == plan_id)
            if gui.Dialog().yesno('Trakt', '¿Eliminar este plan guardado sin aplicar?'):
                shutil.rmtree(folder)
                plans.remove(folder)
                labels.append('Plan eliminado; no se modificó el historial')
        if plans:
            labels.append('Planes guardados: %d; aplicación aún no disponible' % len(plans))
    for label in labels:
        item = gui.ListItem(label=label)
        item.setProperty('IsPlayable', 'false')
        plugin.addDirectoryItem(handle, '', item, False)
    for folder in plans:
        item = gui.ListItem(label='Eliminar plan guardado %s…' % folder.name[-8:])
        item.setProperty('IsPlayable', 'false')
        plugin.addDirectoryItem(handle, ROOT + '&operation=cancel_plan&plan=' + folder.name, item, True)
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
    if service_addon is not None:
        export_path = Path(vfs.translatePath(service_addon.getAddonInfo('profile'))) / 'trakt_live' / 'export_consent.json'
        item = gui.ListItem(label=('Permiso de exportación guardado; cuenta y proveedor se verifican al enviar' if sync_enabled(export_path) else 'Exportación automática sin autorización'))
        item.setProperty('IsPlayable', 'false')
        plugin.addDirectoryItem(handle, '', item, False)
    for operation, label in (('collection_map', 'Configurar destinos de colecciones Trakt…'), ('export_grant', 'Autorizar exportación automática…'), ('export_revoke', 'Revocar exportación automática')):
        item = gui.ListItem(label=label)
        item.setProperty('IsPlayable', 'false')
        plugin.addDirectoryItem(handle, XSTREAM_SYNC_CONSENT + '&operation=' + operation, item, True)
    item = gui.ListItem(label='Operaciones explícitas de todos los perfiles (solo lectura)')
    item.setProperty('IsPlayable', 'false')
    plugin.addDirectoryItem(handle, 'plugin://service.actweeter/?action=trakt_actions', item, True)
    item = gui.ListItem(label='Actualizar estado de exportaciones')
    item.setProperty('IsPlayable', 'false')
    plugin.addDirectoryItem(handle, ROOT + '&operation=refresh', item, True)
    if exports and status['safe']:
        item = gui.ListItem(label='Comprobar preparación segura de la restauración')
        item.setProperty('IsPlayable', 'false')
        plugin.addDirectoryItem(handle, ROOT + '&operation=prepare', item, True)
        if service_addon is not None:
            item = gui.ListItem(label='Confirmar y guardar un plan de restauración…')
            item.setProperty('IsPlayable', 'false')
            plugin.addDirectoryItem(handle, ROOT + '&operation=confirm', item, True)
    plugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)
