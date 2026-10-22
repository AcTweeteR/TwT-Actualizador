"""Kodi-native Mis Colecciones screen, with offline-first local list creation.

No remote API calls are made here. The account sync engine must later use
verified mappings and explicit opt-in before remote list creation.
"""
import os
from urllib.parse import urlencode
from collection_catalog import Catalog

ROOT = 'plugin://service.actweeter/'


def _catalog(addon, vfs):
    directory = vfs.translatePath(addon.getAddonInfo('profile'))
    os.makedirs(directory, mode=0o700, exist_ok=True)
    return Catalog(os.path.join(directory, 'collections_catalog.db'))


def render(handle, *, addon, vfs, gui, plugin, params, dialog):
    """Handle only scoped actions; reject forged remote-write requests."""
    action = params.get('action', ['collections'])[0]
    if action not in ('collections', 'collection_create', 'collection_open', 'collection_add', 'collection_rename'):
        raise ValueError('unsupported collections action')
    store = _catalog(addon, vfs)
    if action == 'collection_create':
        name = dialog.input('Nombre de la nueva colección')
        if name and name.strip():
            try:
                store.create_local(name, origin='mis_colecciones')
            except ValueError:
                dialog.ok('Mis Colecciones', 'Nombre no válido (máximo 120 caracteres).')
    elif action == 'collection_add':
        # A typed numeric ID alone is not a verified movie/TV identity.
        # Keep this action fail-closed until TMDb lookup and readback exist.
        dialog.ok('Mis Colecciones',
                  'La selección de contenido estará disponible tras verificar el catálogo TMDb.')
        plugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)
        return
    elif action == 'collection_rename':
        identifier = params.get('id', [''])[0]
        try:
            current = store.get(identifier)
        except ValueError:
            plugin.endOfDirectory(handle, succeeded=False, cacheToDisc=False)
            return
        title = dialog.input('Nuevo nombre de colección', defaultt=current['name'])
        if title and title.strip() and title.strip() != current['name']:
            try:
                store.rename_local(identifier, title)
            except ValueError:
                dialog.ok('Mis Colecciones', 'Nombre no válido.')
    elif action == 'collection_open':
        identifier = params.get('id', [''])[0]
        try:
            entry = store.get(identifier)
        except ValueError:
            plugin.endOfDirectory(handle, succeeded=False, cacheToDisc=False)
            return
        plugin.setPluginCategory(handle, entry['name'])
        for member in store.members(identifier):
            item = gui.ListItem(label=member['title'])
            item.setProperty('AcTweeteR.TMDbId', str(member['tmdb_id']))
            item.setProperty('AcTweeteR.MediaType', member['kind'])
            item.setProperty('IsPlayable', 'false')
            plugin.addDirectoryItem(handle, ROOT + '?' + urlencode({'action': 'collection_open', 'id': identifier}), item, False)
        plugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)
        return
    plugin.setPluginCategory(handle, 'Mis Colecciones')
    plugin.setContent(handle, 'videos')
    create = gui.ListItem(label='+ Crear colección')
    create.addContextMenuItems([('Trakt · Operaciones explícitas',
        'ActivateWindow(Videos,' + ROOT + '?' + urlencode({'action': 'trakt_actions'}) + ',return)')])
    plugin.addDirectoryItem(handle, ROOT + '?' + urlencode({'action': 'collection_create'}), create, True)
    with store._db() as db:
        rows = db.execute('SELECT local_id,name FROM lists ORDER BY name COLLATE NOCASE,local_id').fetchall()
    for identifier, name in rows:
        item = gui.ListItem(label=name)
        item.setArt({'icon': 'DefaultFolder.png', 'thumb': 'DefaultFolder.png'})
        item.addContextMenuItems([('Renombrar colección',
            'RunPlugin(' + ROOT + '?' + urlencode({'action': 'collection_rename', 'id': identifier}) + ')')])
        plugin.addDirectoryItem(handle, ROOT + '?' + urlencode({'action': 'collection_open', 'id': identifier}), item, True)
    plugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)
