"""Read the local Trakt queue; pending retries require confirmation in XStream."""
import json
import os
import re
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
    unavailable = os.path.islink(path) or (os.path.lexists(path) and not os.path.isfile(path))
    # Opening the screen must never create a queue or mutate a profile.
    if os.path.isfile(path) and not os.path.islink(path):
        connection = None
        try:
            connection = sqlite3.connect('file:' + quote(path, safe='/') + '?mode=ro', uri=True, timeout=2)
            rows = connection.execute('SELECT id,state,attempts,event FROM events ORDER BY rowid DESC LIMIT 100').fetchall()
        except (sqlite3.Error, OSError):
            unavailable = True
        finally:
            if connection is not None:
                connection.close()
    message = ('Estado de operaciones explícitas no disponible' if unavailable else
               'Sin operaciones explícitas registradas' if not rows else
               'Operaciones locales (solo lectura)')
    header = gui.ListItem(label=message)
    header.setProperty('IsPlayable', 'false')
    plugin.addDirectoryItem(handle, '', header, False)
    for operation, state, attempts, raw in rows:
        if state not in ('retained', 'held', 'pending', 'inflight', 'unknown', 'confirmed'):
            continue
        item = gui.ListItem(label='%s · %s · intentos %s' % (str(operation)[:12], state, attempts))
        item.setProperty('IsPlayable', 'false')
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            data = {}
        if state == 'retained':
            item = gui.ListItem(label='Captura retenida: identidad, ámbito o autoridad sin verificar')
            item.setProperty('IsPlayable', 'false')
        retry = (state in ('held', 'pending') and isinstance(data, dict) and data.get('schema') == 2
                 and isinstance(operation, str) and re.fullmatch(r'[0-9a-f]{64}', operation))
        url = ('plugin://plugin.video.xstream-pro/?mode=xstream_trakt_retry_manual&operation=' + operation
               if retry else '')
        plugin.addDirectoryItem(handle, url, item, bool(retry))
    info = gui.ListItem(label='Las operaciones inciertas no se reenvían sin verificación')
    info.setProperty('IsPlayable', 'false')
    plugin.addDirectoryItem(handle, '', info, False)
    plugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)
