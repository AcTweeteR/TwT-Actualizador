"""Read-only Kodi Trakt restoration entrypoint; never commits on click."""
import json
import tempfile
from urllib.parse import quote
from .trakt_restore_transaction import stage_restore
from pathlib import Path
from .trakt_restore_importer import prepare_restore

ROOT = 'plugin://service.actweeter/?action=trakt_restore'


def summarize_exports(xstream_profile, *, profile):
    root = Path(xstream_profile)
    exports = root / 'trakt_exports'
    if exports.is_symlink() or not exports.is_dir():
        return []
    results = []
    for folder in sorted(exports.glob('snapshot-*')):
        if folder.is_symlink() or not folder.is_dir():
            continue
        try:
            raw = json.loads((folder / 'snapshot.json').read_text('utf-8'))
            account = raw['snapshot']['account']
            if str(raw['profile']) != str(profile):
                continue
            plan = prepare_restore(folder, root, profile=profile, account=account)
            results.append({'name': folder.name, 'account': account,
                            'watched_movies': sum(x.get('watched') is True and x['identity']['kind']=='movie' for x in plan['items']),
                            'watched_episodes': sum(x.get('watched') is True and x['identity']['kind']=='episode' for x in plan['items']),
                            'resume_pending': sum('position' in x for x in plan['items'])})
        except (ValueError, TypeError, KeyError, OSError, PermissionError):
            continue
    return results


def render(handle, *, gui, plugin, vfs, xstream_addon, params=None):
    profile_path = vfs.translatePath(xstream_addon.getAddonInfo('profile'))
    plugin.setPluginCategory(handle, 'Sincronizar biblioteca con Trakt')
    plugin.setContent(handle, 'files')
    exports = summarize_exports(profile_path, profile='1')
    action = (params or {}).get('operation', [''])[0]
    staged_message = None
    if action == 'prepare' and exports:
        newest = exports[-1]
        plan = prepare_restore(Path(profile_path) / 'trakt_exports' / newest['name'],
                               profile_path, profile='1', account=newest['account'])
        with tempfile.TemporaryDirectory(prefix='actweeter-trakt-preview-') as folder:
            result = stage_restore(plan, profile='1', account=newest['account'],
                movie_source=Path(profile_path) / 'watched_movies_p1.json',
                episode_source=Path(profile_path) / 'watched_episodes_p1.json',
                staging_directory=folder)
            staged_message = 'Preparación comprobada: %d películas, %d episodios (sin modificar Kodi)' % (result['movies'], result['episodes'])
    if not exports:
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
    if exports:
        item = gui.ListItem(label='Comprobar preparación segura de la restauración')
        item.setProperty('IsPlayable', 'false')
        plugin.addDirectoryItem(handle, ROOT + '&operation=prepare', item, True)
    plugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)
