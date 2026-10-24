"""Kodi screen for explicit Trakt operations, fail-closed until account transport exists.

Never reads script.trakt secrets, accepts credentials in URLs, or sends POSTs.
"""
import os
import sqlite3
from urllib.parse import quote

ROOT = 'plugin://service.actweeter/'


def render(handle, *, addon, vfs, gui, plugin, params):
    if params.get('action', [''])[0] != 'trakt_actions':
        raise ValueError('unsupported Trakt action')
    if handle < 0:
        return
    plugin.setPluginCategory(handle, 'Trakt - Operaciones explícitas')
    plugin.setContent(handle, 'files')
    folder = vfs.translatePath(addon.getAddonInfo('profile'))
    path = os.path.join(folder, 'trakt_explicit_outbox.sqlite')
    rows = []
    # Opening the screen must never create a queue or mutate a profile.
    if os.path.isfile(path) and not os.path.islink(path):
        connection = None
        try:
            connection = sqlite3.connect('file:' + quote(path, safe='/') + '?mode=ro', uri=True, timeout=2)
            rows = connection.execute('SELECT id,state,attempts FROM events ORDER BY rowid DESC LIMIT 100').fetchall()
        except (sqlite3.Error, OSError):
            rows = []
        finally:
            if connection is not None:
                connection.close()
    message = ('Sin operaciones explícitas registradas' if not rows else
               'Operaciones locales (solo lectura)')
    header = gui.ListItem(label=message)
    header.setProperty('IsPlayable', 'false')
    plugin.addDirectoryItem(handle, '', header, False)
    for operation, state, attempts in rows:
        if state not in ('pending', 'inflight', 'unknown', 'confirmed'):
            continue
        item = gui.ListItem(label='%s · %s · intentos %s' % (str(operation)[:12], state, attempts))
        item.setProperty('IsPlayable', 'false')
        plugin.addDirectoryItem(handle, '', item, False)
    info = gui.ListItem(label='Envíos desactivados hasta verificar la cuenta Trakt')
    info.setProperty('IsPlayable', 'false')
    plugin.addDirectoryItem(handle, '', info, False)
    plugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)
