"""Kodi-facing opt-in and scheduler routes; authentication stays in XStream."""
import json
import sqlite3
import sys
from pathlib import Path


def _binding(context, trakt, xbmcaddon, xbmcvfs):
    from trakt_live_queue import provider_fingerprint
    from profiles import ProfileManager
    manager = ProfileManager(context('addon'))
    profile = str(manager.active)
    creds = manager.get_credentials()
    scope = provider_fingerprint(profile, creds.get('source_type'),
        creds.get('xtream_url'), creds.get('xtream_username'), creds.get('m3u_url'))
    read_tokens = getattr(trakt, '_read_tokens', lambda: {})
    tokens_before = read_tokens()
    current, _ = trakt.snapshot_request('/users/settings', {})
    account = str(current.get('user', {}).get('ids', {}).get('slug', ''))
    service = xbmcaddon.Addon('service.actweeter')
    service_root = Path(xbmcvfs.translatePath(service.getAddonInfo('profile')))
    if tokens_before.get('access_token') and tokens_before == read_tokens() and account and scope:
        import trakt_local_journal
        trakt_local_journal.remember_binding(context('addon'), account, profile, scope, tokens_before, xbmcvfs)
    return account, profile, scope, service_root


def consent_route(context, guard, trakt, xbmcaddon, xbmcgui, xbmcplugin, xbmcvfs, params=None):
    if not guard(auth=True) or not trakt.authorized():
        return
    account, profile, scope, root = _binding(context, trakt, xbmcaddon, xbmcvfs)
    if not account or not scope:
        raise PermissionError('verified Trakt account and provider scope required')
    operation = (params or {}).get('operation', '')
    if isinstance(operation, list):
        operation = operation[0] if operation else ''
    if operation == 'collection_map':
        service_path = Path(xbmcvfs.translatePath(xbmcaddon.Addon('service.actweeter').getAddonInfo('path'))) / 'resources'
        if str(service_path) not in sys.path:
            sys.path.insert(0,str(service_path))
        from lib.collection_catalog import Catalog, _runtime_scope
        catalog=Catalog(root/'collections_catalog.db')
        with catalog._db() as db:
            rows=db.execute('SELECT local_id,name FROM lists ORDER BY name').fetchall()
        from favorites import Favorites
        from lang import _t
        native = [(label, folder, media) for label, folder, media in (
            ('Favoritos de películas', _t(30009) or 'Favorites', 'movie'),
            ('Favoritos de series', _t(30009) or 'Favorites', 'series'),
            ('Pendientes de películas', 'AcTweeteR Pending - Movies', 'movie'),
            ('Pendientes de series', 'AcTweeteR Pending - Series', 'series'))]
        selected=xbmcgui.Dialog().select('Colección local', [row[1] for row in rows]+[row[0] for row in native])
        native_source = None
        if len(rows) <= selected < len(rows)+len(native):
            import hashlib
            label,folder,media=native[selected-len(rows)]
            native_source=dict(folder_sha256=hashlib.sha256(folder.encode()).hexdigest(),media_type=media,folder=folder)
            selected=len(rows)
            rows.append((None,label))
        if 0 <= selected < len(rows):
            targets=['watchlist','collection','favorites','list']
            chosen=xbmcgui.Dialog().select('Destino Trakt', ['Watchlist','Colección Trakt','Favoritos Trakt','Lista personal por ID'])
            if 0 <= chosen < len(targets):
                destination=targets[chosen]
                if destination == 'list':
                    identifier=xbmcgui.Dialog().input('ID numérico de tu lista Trakt').strip()
                    if not identifier.isdigit() or int(identifier) <= 0:
                        raise ValueError('numeric list ID required')
                    remote,_=trakt.snapshot_request('/users/me/lists/'+identifier,{})
                    if str(remote.get('ids',{}).get('trakt')) != identifier:
                        raise ValueError('remote list identity not verified')
                    destination='list.'+identifier
                binding=_runtime_scope()
                if not binding or binding['account'] != account or binding['provider_scope'] != scope:
                    raise PermissionError('mapping scope changed')
                if xbmcgui.Dialog().yesno('Vincular colección', 'Aplicar a cambios futuros: '+destination+'. No se migrarán ni borrarán elementos remotos existentes.'):
                    local_id=rows[selected][0]
                    if native_source:
                        with catalog._db() as db:
                            existing=[ident for ident,raw in db.execute('SELECT local_id,mappings FROM lists')
                                      if json.loads(raw).get('xstream_source') == native_source
                                      and json.loads(raw).get('trakt_sync',{}).get('scope') == binding]
                        local_id=existing[0] if len(existing)==1 else catalog.create_local(rows[selected][1],kind='movie' if native_source['media_type']=='movie' else 'show',origin='mis_colecciones')
                    catalog.configure_destination(local_id,scope=binding,destination=destination,verified=True,confirmed=True)
                    if native_source:
                        with catalog._db() as db:
                            value=json.loads(db.execute('SELECT mappings FROM lists WHERE local_id=?',(local_id,)).fetchone()[0])
                            value['xstream_source']=native_source
                            db.execute('UPDATE lists SET mappings=? WHERE local_id=?',(json.dumps(value),local_id))
        xbmcplugin.endOfDirectory(context('addon_handle'),cacheToDisc=False)
        return
    if operation in ('export_grant', 'export_revoke'):
        service_path = Path(xbmcvfs.translatePath(xbmcaddon.Addon('service.actweeter').getAddonInfo('path'))) / 'resources'
        if str(service_path) not in sys.path:
            sys.path.insert(0, str(service_path))
        from lib.trakt_sync_consent import grant, revoke
        target = root / 'trakt_live' / 'export_consent.json'
        message = 'Exportación sin cambios'
        if operation == 'export_revoke':
            revoke(target)
            message = 'Exportación automática revocada'
        elif xbmcgui.Dialog().yesno('Autorizar exportación automática',
                'Enviar a esta cuenta desmarcados y cambios de listas identificados de este perfil. '
                'Los vistos capturados siguen retenidos para evitar duplicar script.trakt. '
                'Los desmarcados pueden eliminar el historial remoto del contenido. '
                'Las operaciones ambiguas o inciertas no se enviarán. '
                'Esta autorización es independiente de la importación. ¿Autorizar?'):
            grant(target, account=account, profile=profile, provider_scope=scope)
            message = 'Exportación automática autorizada para esta cuenta y proveedor'
        item = context('_new_listitem')(message)
        xbmcplugin.addDirectoryItem(context('addon_handle'), '', item, isFolder=False)
        xbmcplugin.endOfDirectory(context('addon_handle'), cacheToDisc=False)
        return
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
    import_allowed = authorized(consent_path, account=account, profile=profile, provider_scope=scope)
    export_path = service_root / 'trakt_live' / 'export_consent.json'
    export_allowed = authorized(export_path, account=account, profile=profile, provider_scope=scope)
    if not one_shot and not import_allowed:
        suspend(consent_path)
        if not export_allowed:
            suspend(export_path)
            return

    if not one_shot:
        try:
            retry_due_manual_actions(context, trakt, xbmcaddon, xbmcvfs,
                                     account=account, profile=profile, scope=scope, root=service_root,
                                     player=player)
        except (OSError, ValueError, sqlite3.Error):
            xbmc.log('[AcTweeteR] TRAKT_PENDING_RETRY unavailable', xbmc.LOGWARNING)

    if not one_shot and not import_allowed:
        return

    addon = context('addon')
    xstream_root = Path(xbmcvfs.translatePath(addon.getAddonInfo('profile')))
    import history
    import trakt_live_consumer
    import trakt_snapshot
    from lib.trakt_auto_cycle import run_cycle

    def activity_get():
        user, _ = trakt.snapshot_request('/users/settings', {})
        activity, _ = trakt.snapshot_request('/sync/last_activities', {})
        slug = str(user.get('user', {}).get('ids', {}).get('slug', ''))
        if not isinstance(activity, dict) or not isinstance(activity.get('all'), str):
            raise ValueError('invalid Trakt activity response')
        return slug, activity

    def export_snapshot():
        folder = xstream_root / 'trakt_exports'
        before = {path.name for path in folder.glob('snapshot-*')} if folder.exists() else set()
        trakt_snapshot.export_snapshot(
            lambda path, query: trakt.snapshot_request(path, query), folder, profile,
            cancelled=lambda: not local_binding_valid())
        created = [path for path in folder.glob('snapshot-*')
                   if path.is_dir() and path.name not in before]
        if len(created) != 1:
            raise OSError('snapshot output is ambiguous')
        return created[0]

    def local_binding_valid():
        from profiles import ProfileManager
        from trakt_live_queue import provider_fingerprint
        manager = ProfileManager(addon)
        credentials = manager.get_credentials()
        current_scope = provider_fingerprint(str(manager.active), credentials.get('source_type'),
            credentials.get('xtream_url'), credentials.get('xtream_username'), credentials.get('m3u_url'))
        return str(manager.active) == profile and current_scope == scope and not player.isPlaying()

    def binding_valid():
        if not local_binding_valid():
            return False
        current_account, _ = trakt.snapshot_request('/users/settings', {})
        return (current_account.get('user', {}).get('ids', {}).get('slug') == account
                and local_binding_valid())

    applied_count = 0

    def apply_batch(*args, **kwargs):
        nonlocal applied_count
        from lib.trakt_outbox import Outbox
        outbox = Outbox(service_root / 'trakt_explicit_outbox.sqlite')
        with outbox.import_guard(account=account, profile=profile, provider_scope=scope) as conflicts:
            ack = trakt_live_consumer.apply_batch(*args, pending_conflict=conflicts, **kwargs)
        applied_count += sum(row.get('status') == 'applied'
                             for row in ack.get('results', []))
        return ack

    try:
        sync_configured_collections(context, trakt, xbmcaddon, xbmcvfs, account=account,
                                    profile=profile, scope=scope, root=service_root)
        result = run_cycle(service_root, xstream_root, account=account, profile=profile,
            provider_scope=scope, activity_get=activity_get,
            export_snapshot=export_snapshot, apply_batch=apply_batch,
            addon=addon, history=history, playing_file=playing, consent_path=consent_path,
            one_shot=one_shot, binding_valid=binding_valid)
        # One-shot restoration must drain its bounded, durable queue; the
        # scheduler keeps the original three-cycle limit per invocation.
        max_cycles = 100 if one_shot else 3
        for _ in range(max_cycles):
            if result.get('status') not in ('queued', 'pending'):
                break
            if one_shot and player.isPlaying():
                result = {'status': 'deferred', 'reason': 'playback_started'}
                break
            result = run_cycle(service_root, xstream_root, account=account, profile=profile,
                provider_scope=scope, activity_get=activity_get,
                export_snapshot=export_snapshot,
                apply_batch=apply_batch, addon=addon,
                history=history, playing_file=playing, consent_path=consent_path,
                one_shot=one_shot, binding_valid=binding_valid)
        if not one_shot:
            record_result(service_root / 'trakt_live' / 'scheduler.json',
                          success=result.get('status') in ('applied', 'unchanged', 'deferred', 'busy', 'pending'),
                          now=__import__('time').time())
    except Exception as exc:
        if not one_shot:
            record_result(service_root / 'trakt_live' / 'scheduler.json',
                          success=False, now=__import__('time').time())
        xbmc = __import__('xbmc')
        xbmc.log('[AcTweeteR] TRAKT_SYNC_CYCLE failed error_type=%s' %
                 type(exc).__name__, xbmc.LOGWARNING)
        result = {'status': 'failed', 'error_type': type(exc).__name__}
    # A later deferred batch or failed GET must not hide earlier durable writes.
    if applied_count:
        xbmc.executebuiltin(
            'RunPlugin(plugin://service.actweeter/?action=trakt_continue_refresh)', False)
    status = result['status']
    if result.get('reason') == 'operations_deferred':
        status = 'parcial: %d aplicadas, %d ya aplicadas' % (
            result.get('applied', 0), result.get('already_applied', 0),
        )
    item = context('_new_listitem')('AcTweeteR Trakt sync: ' + status)
    item.setProperty('actweeter.trakt.sync', json.dumps(result, sort_keys=True))
    xbmcplugin.addDirectoryItem(context('addon_handle'), '', item, isFolder=False)
    if result.get('reason') == 'operations_deferred':
        detail = 'Último lote: %d aplazadas; %d lotes pendientes' % (
            len(result.get('deferred_operations', [])), result.get('remaining_batches', 0))
        xbmcplugin.addDirectoryItem(context('addon_handle'), '', context('_new_listitem')(detail), isFolder=False)
    reasons = {
        'provider_identity_not_verified_in_catalog': 'identidad no verificada en el catálogo',
        'exact_playback_reference_missing': 'falta una referencia exacta de reproducción',
        'local_action_unreconciled': 'existe un cambio local pendiente',
        'provider_catalog_scope_changed': 'el catálogo no corresponde al proveedor activo',
    }
    for operation in result.get('deferred_operations', []):
        identity = operation.get('identity', {})
        ids = identity.get('ids', {})
        identifiers = next(('%s:%s' % (key, ids[key]) for key in ('tmdb', 'imdb', 'tvdb', 'trakt')
                            if ids.get(key)), '')
        if identity.get('kind') == 'episode':
            identifiers += ' S%sE%s' % (identity.get('season', '?'), identity.get('episode', '?'))
        label = '%s — %s' % (identifiers or 'Identidad pendiente',
                            reasons.get(operation.get('reason'), operation.get('reason', 'motivo desconocido')))
        xbmcplugin.addDirectoryItem(context('addon_handle'), '', context('_new_listitem')(label), isFolder=False)
    xbmcplugin.endOfDirectory(context('addon_handle'), cacheToDisc=False)


def sync_once_route(context, guard, trakt, xbmcaddon, xbmc, xbmcplugin, xbmcvfs):
    return cycle_route(context, guard, trakt, xbmcaddon, xbmc, xbmcplugin,
                       xbmcvfs, one_shot=True)


def _offline_binding(context, xbmcaddon, xbmcvfs):
    """Use a previously verified binding only to stage, never to send."""
    from profiles import ProfileManager
    from trakt_live_queue import provider_fingerprint
    manager = ProfileManager(context('addon'))
    profile = str(manager.active)
    creds = manager.get_credentials()
    scope = provider_fingerprint(profile, creds.get('source_type'),
        creds.get('xtream_url'), creds.get('xtream_username'), creds.get('m3u_url'))
    service = xbmcaddon.Addon('service.actweeter')
    root = Path(xbmcvfs.translatePath(service.getAddonInfo('profile')))
    service_path = Path(xbmcvfs.translatePath(service.getAddonInfo('path'))) / 'resources'
    if str(service_path) not in sys.path:
        sys.path.insert(0, str(service_path))
    from lib.trakt_sync_consent import authorized
    path = root / 'trakt_live' / 'consent.json'
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
        raise PermissionError('no verified offline account binding')
    data = json.loads(path.read_text('utf-8'))
    account = data.get('account') if isinstance(data, dict) else None
    if not account or not authorized(path, account=account, profile=profile, provider_scope=scope):
        raise PermissionError('offline binding does not match active profile')
    return account, profile, scope, root


def coordinated_manual_action(context, trakt, tmdb_type, tmdb_id, season, episode,
                              action_type, action):
    """Persist explicit actions before attempting one account-bound Trakt request."""
    import datetime
    import time
    import uuid
    import xbmc
    import xbmcaddon
    import xbmcvfs
    offline = False
    try:
        account, profile, scope, root = _binding(context, trakt, xbmcaddon, xbmcvfs)
    except (OSError, RuntimeError):
        account, profile, scope, root = _offline_binding(context, xbmcaddon, xbmcvfs)
        offline = True
    if not account or not scope:
        raise PermissionError('verified account and provider profile required')
    if tmdb_type == 'movie':
        kind = 'movie'
    elif tmdb_type in ('tv', 'show', 'tvshow', 'episode'):
        if bool(str(season)) != bool(str(episode)):
            raise ValueError('season and episode must both be supplied')
        kind = 'episode' if str(season) and str(episode) else 'show'
    else:
        raise ValueError('unsupported media type')
    operations = {'mark_watched': 'history.add', 'mark_unwatched': 'history.remove',
                  'checkin': 'checkin'}
    operation = operations.get(action_type) or ('%s.%s' % (action_type, action))
    service_path = Path(xbmcvfs.translatePath(
        xbmcaddon.Addon('service.actweeter').getAddonInfo('path'))) / 'resources'
    if str(service_path) not in sys.path:
        sys.path.insert(0, str(service_path))
    from lib.trakt_outbox import Outbox, RetryLater, manual_event
    content = {'kind': kind, 'ids': {'tmdb': tmdb_id}, 'season': season, 'episode': episode}
    watched_at = (datetime.datetime.now(datetime.timezone.utc).isoformat()
                  if operation == 'history.add' else None)
    if operation == 'checkin' and offline:
        return 'blocked_offline'
    if operation == 'checkin' and xbmc.Player().isPlaying():
        return 'blocked_playback'
    event = manual_event(account, profile, operation, content, uuid.uuid4().hex, watched_at, provider_scope=scope)
    queue = Outbox(root / 'trakt_explicit_outbox.sqlite')
    identifier = queue.enqueue_manual(event)
    if offline:
        return 'pending'
    def post(path, payload):
        if path == '/sync/history' and xbmc.Player().isPlaying():
            raise RetryLater(60)
        try:
            latest = _binding(context, trakt, xbmcaddon, xbmcvfs)
        except OSError:
            raise RetryLater(60) from None
        if latest[:3] != (account, profile, scope):
            raise PermissionError('account or provider profile changed')
        try:
            return trakt.post(path, payload, auth=True)
        except RuntimeError as exc:
            if str(exc) == 'Trakt rate limited. Try again later.':
                raise RetryLater(60) from None
            raise
    return queue.send_manual(identifier, account=account, profile=profile, provider_scope=scope,
                             approved=identifier, post=post, now=time.time())


def retry_due_manual_actions(context, trakt, xbmcaddon, xbmcvfs, *, account, profile, scope, root, player):
    """Retry a bounded set of previously authorized actions; uncertain POSTs stay held."""
    import time
    service_path = Path(xbmcvfs.translatePath(
        xbmcaddon.Addon('service.actweeter').getAddonInfo('path'))) / 'resources'
    if str(service_path) not in sys.path:
        sys.path.insert(0, str(service_path))
    from lib.trakt_outbox import Outbox, RetryLater
    queue_path = root / 'trakt_explicit_outbox.sqlite'
    # Recover handoffs interrupted after the native store was committed.
    addon = context('addon')
    raw_profile = addon.getAddonInfo('profile') if addon is not None else None
    if isinstance(raw_profile, str) and raw_profile:
        xstream_root = Path(xbmcvfs.translatePath(raw_profile))
        journal_path = xstream_root / 'trakt_local_changes.sqlite'
        if journal_path.is_file() and not journal_path.is_symlink():
            import trakt_local_journal
            for prefix in ('favorites_', 'watched_movies_p', 'watched_episodes_p', 'resume_points_p'):
                store = xstream_root / (prefix + profile + '.json')
                if store.is_file() and not store.is_symlink():
                    trakt_local_journal.runtime_handoff(store)
    catalog_path = root / 'collections_catalog.db'
    if catalog_path.is_file() and not catalog_path.is_symlink():
        from lib.collection_catalog import Catalog
        Catalog(catalog_path).handoff_changes(Outbox(queue_path))
    if queue_path.is_symlink() or not queue_path.is_file():
        return []
    queue = Outbox(queue_path)
    now = time.time()
    from lib.trakt_sync_consent import authorized
    export_path = root / 'trakt_live' / 'export_consent.json'
    export_allowed = authorized(export_path, account=account, profile=profile, provider_scope=scope)
    pending = queue.pending_manual(account=account, profile=profile, provider_scope=scope, now=now, include_held=export_allowed)
    outcomes = []
    requires_export = False
    def post(path, payload):
        if player.isPlaying():
            raise RetryLater(60)
        try:
            latest = _binding(context, trakt, xbmcaddon, xbmcvfs)
        except OSError:
            raise RetryLater(60) from None
        if latest[:3] != (account, profile, scope):
            raise PermissionError('account or provider profile changed')
        if requires_export and not authorized(export_path, account=account, profile=profile, provider_scope=scope):
            raise RetryLater(60)
        try:
            return trakt.post(path, payload, auth=True)
        except RuntimeError as exc:
            if str(exc) == 'Trakt rate limited. Try again later.':
                raise RetryLater(60) from None
            raise
    for identifier in pending:
        if player.isPlaying():
            break
        requires_export = queue.status(identifier)['state'] == 'held'
        if requires_export and not authorized(export_path, account=account, profile=profile, provider_scope=scope):
            continue
        outcomes.append(queue.send_manual(identifier, account=account, profile=profile,
            provider_scope=scope, approved=identifier, post=post, now=now))
    return outcomes


def retry_manual_route(context, guard, trakt, xbmcaddon, xbmcgui, xbmcplugin, xbmcvfs, params):
    """Retry only a known pending explicit action after renewed user confirmation."""
    import re
    import time
    import xbmc
    operation = params.get('operation', '')
    if isinstance(operation, list):
        operation = operation[0] if operation else ''
    if not isinstance(operation, str) or not re.fullmatch(r'[0-9a-f]{64}', operation):
        raise ValueError('valid operation required')
    if not guard(auth=True) or not trakt.authorized():
        xbmcplugin.endOfDirectory(context('addon_handle'), succeeded=False)
        return
    account, profile, scope, root = _binding(context, trakt, xbmcaddon, xbmcvfs)
    service_path = Path(xbmcvfs.translatePath(
        xbmcaddon.Addon('service.actweeter').getAddonInfo('path'))) / 'resources'
    if str(service_path) not in sys.path:
        sys.path.insert(0, str(service_path))
    from lib.trakt_outbox import Outbox, RetryLater
    queue_path = root / 'trakt_explicit_outbox.sqlite'
    if queue_path.is_symlink() or not queue_path.is_file():
        raise ValueError('pending queue unavailable')
    queue = Outbox(queue_path)
    with queue.connect() as db:
        row = db.execute('SELECT event,state FROM events WHERE id=?', (operation,)).fetchone()
    if row is None:
        raise ValueError('unknown operation')
    if row[1] not in ('held', 'pending'):
        xbmcplugin.endOfDirectory(context('addon_handle'), succeeded=False)
        return
    event = json.loads(row[0])
    if (event.get('account') != account or event.get('profile') != profile
            or event.get('provider_scope') != scope):
        raise PermissionError('export scope changed')
    description = 'Enviar a Trakt: %s (%s). ' % (event.get('operation'), event.get('identity', {}).get('kind'))
    if event.get('operation') == 'history.remove':
        description += 'Esto elimina el historial remoto del contenido. '
    description += 'Esta autorización solo corresponde a esta operación; no activa exportaciones automáticas.'
    if not xbmcgui.Dialog().yesno('Autorizar exportación Trakt', description):
        xbmcplugin.endOfDirectory(context('addon_handle'), succeeded=False)
        return
    def post(path, payload):
        if path in ('/sync/history', '/checkin') and xbmc.Player().isPlaying():
            raise RetryLater(60)
        try:
            latest = _binding(context, trakt, xbmcaddon, xbmcvfs)
        except OSError:
            raise RetryLater(60) from None
        if latest[:3] != (account, profile, scope):
            raise PermissionError('account or provider profile changed')
        try:
            return trakt.post(path, payload, auth=True)
        except RuntimeError as exc:
            if str(exc) == 'Trakt rate limited. Try again later.':
                raise RetryLater(60) from None
            raise
    state = queue.send_manual(operation, account=account, profile=profile, provider_scope=scope,
                              approved=operation, post=post, now=time.time())
    item = context('_new_listitem')('Operación Trakt: ' + state)
    xbmcplugin.addDirectoryItem(context('addon_handle'), '', item, isFolder=False)
    xbmcplugin.endOfDirectory(context('addon_handle'), cacheToDisc=False)


def sync_configured_collections(context, trakt, xbmcaddon, xbmcvfs, *, account, profile, scope, root):
    """Complete, stable remote snapshots; writes only the bound local catalog."""
    import time
    from lib.collection_catalog import Catalog, _runtime_scope
    from lib.trakt_sync import _pages
    path=root/'collections_catalog.db'
    if not path.is_file() or path.is_symlink():
        return
    catalog=Catalog(path)
    with catalog._db() as db:
        mappings=[(identifier,kind,json.loads(raw).get('trakt_sync')) for identifier,kind,raw in db.execute('SELECT local_id,kind,mappings FROM lists')]
    if not any(mapping for _,_,mapping in mappings):
        return
    binding=_runtime_scope()
    if not binding or (binding['account'],binding['profile'],binding['provider_scope']) != (account,profile,scope):
        raise PermissionError('collection import binding unavailable')
    for identifier,local_kind,mapping in mappings:
        if not isinstance(mapping,dict) or mapping.get('scope') != binding:
            continue
        destination=mapping['destination']
        if destination.startswith('list.'):
            remote_id=destination.split('.')[1]
            if not remote_id.isdigit():
                raise ValueError('invalid configured list')
            paths=['/users/me/lists/'+remote_id+'/items']
        elif destination in ('watchlist','collection','favorites'):
            paths=['/sync/'+destination+'/'+kind for kind in ('movies','shows')
                   if local_kind == 'mixed' or kind == local_kind+'s']
        else:
            raise ValueError('unsupported configured destination')
        from lib.trakt_outbox import Outbox
        queue_path=root/'trakt_explicit_outbox.sqlite'
        confirmed=catalog.confirmed_changes(Outbox(queue_path)) if queue_path.is_file() else set()
        native_source=catalog.get(identifier)['mappings'].get('xstream_source')
        native_confirmed=(_confirmed_native_events(context, binding, root, xbmcaddon, xbmcvfs)
                          if native_source else set())
        before,_=trakt.snapshot_request('/sync/last_activities',{})
        items=[]
        observed=time.time()
        for endpoint in paths:
            if destination == 'collection':
                # Trakt collection is an unpaginated complete response.
                remote_rows,_=trakt.snapshot_request(endpoint, {})
                if not isinstance(remote_rows,list):
                    raise ValueError('invalid complete collection response')
            else:
                remote_rows=_pages(lambda route,query: trakt.snapshot_request(route,query),endpoint,
                                   lambda: False,20,require_page_metadata=True)
            for row in remote_rows:
                if not isinstance(row, dict):
                    raise ValueError('invalid remote collection item')
                if not any(key in row for key in ('movie', 'show', 'season', 'episode', 'person')):
                    raise ValueError('unknown remote collection item')
                kind='movie' if 'movie' in row else 'show' if 'show' in row else None
                if kind is None or local_kind not in ('mixed',kind):
                    continue
                media=row[kind];tmdb=media.get('ids',{}).get('tmdb')
                if type(tmdb) is not int or tmdb<1:
                    raise ValueError('remote collection identity unresolved')
                items.append({'kind':kind,'tmdb_id':tmdb,'title':media.get('title')})
        after,_=trakt.snapshot_request('/sync/last_activities',{})
        latest=_binding(context,trakt,xbmcaddon,xbmcvfs)
        if not isinstance(before,dict) or not before.get('all') or before != after or latest[:3] != (account,profile,scope) or _runtime_scope()!=binding:
            raise ValueError('remote collection changed during snapshot')
        result=catalog.apply_remote(identifier,scope=binding,revision=mapping['revision'],items=items,
                                    observed_at=observed,complete=True,confirmed=confirmed)
        source=catalog.get(identifier)['mappings'].get('xstream_source')
        if source and not result['stale']:
            sync_native_collection(context, catalog, identifier, source, mapping, binding,
                                   items, root, xbmcaddon, xbmcvfs, observed, native_confirmed)


def sync_native_collection(context, catalog, identifier, source, mapping, binding, items, service_root, xbmcaddon, xbmcvfs, observed, native_confirmed):
    from favorites import Favorites
    from trakt_provider_index import verified_vod_records, catalog_members
    from trakt_series_index import verified_show_records
    from trakt_live_consumer import _catalog_scope_verified
    import trakt_local_journal as journal
    addon=context('addon')
    root=Path(xbmcvfs.translatePath(addon.getAddonInfo('profile')))
    media=source['media_type']
    kind='movie' if media=='movie' else 'show'
    if media not in ('movie','series') or not _catalog_scope_verified([{'kind':kind}],root,binding['profile'],binding['provider_scope'],addon):
        raise PermissionError('native catalog scope unavailable')
    records=(verified_vod_records(root,profile=binding['profile']) if media=='movie'
             else verified_show_records(root,profile=binding['profile']))
    members=catalog_members(root,binding['profile'],media)
    desired=[]
    for item in items:
        matches=[row for row in records if str(row['ids'].get('tmdb'))==str(item['tmdb_id'])]
        if len(matches)!=1:
            # An unresolved remote member must not become an inferred deletion.
            raise ValueError('native remote identity unresolved')
        provider_id=str(matches[0]['provider_id'])
        row=members.get(provider_id)
        if not row:
            raise ValueError('native provider member missing')
        desired.append(dict(id=provider_id,stype=media,name=row.get('name') or item['title'],
                            icon=row.get('stream_icon') or row.get('cover') or ''))
    favorites=Favorites(addon,binding['profile'])
    def protected():
        from lib.collection_catalog import _runtime_scope
        if _runtime_scope()!=binding or catalog.get(identifier)['mappings'].get('trakt_sync')!=mapping:
            raise PermissionError('native import scope changed')
        with catalog._db() as db:
            state=db.execute('SELECT revision,timestamp FROM remote_state WHERE local_id=?',(identifier,)).fetchone()
        if state != (mapping['revision'],observed):
            raise PermissionError('newer native snapshot already reconciled')
        database,_=journal._database(favorites.file)
        with sqlite3.connect(database) as db:
            db.execute('CREATE TABLE IF NOT EXISTS changes (id TEXT PRIMARY KEY,event TEXT NOT NULL,state TEXT NOT NULL)')
            rows=db.execute("SELECT id,event FROM changes WHERE state NOT IN ('observed','confirmed')").fetchall()
            events=[(ident,json.loads(raw)) for ident,raw in rows]
            desired_ids={str(item['id']) for item in desired}
            adopted=set()
            acknowledged=[]
            for ident,event in events:
                changes=event.get('changes',[])
                if ident not in native_confirmed or event.get('scope')!=binding or event.get('kind')!='Favorites':
                    continue
                if not changes or any(change.get('destination_capture') != mapping for change in changes):
                    continue
                if all(change.get('folder_sha256')==source['folder_sha256'] and change.get('media_type')==media
                       and ((change.get('change')=='add') == (str(change['identity'][1]) in desired_ids))
                       for change in changes):
                    acknowledged.append(ident)
                    adopted.update(str(change['identity'][1]) for change in changes if change['change']=='add')
            events=[event for ident,event in events if ident not in acknowledged]
        blocked={str(change['identity'][1]) for event in events if event.get('kind')=='Favorites'
                 and event.get('origin')=='local' for change in event.get('changes',[])
                 if change.get('folder_sha256')==source['folder_sha256'] and change.get('media_type')==media}
        def commit_acknowledgements():
            with sqlite3.connect(database) as db:
                db.executemany("UPDATE changes SET state='confirmed' WHERE id=? AND state='queued'",[(ident,) for ident in acknowledged])
        return blocked, adopted-blocked, commit_acknowledgements
    favorites.apply_trakt(source['folder'],media,desired,mapping['revision'],protected)


def _confirmed_native_events(context, binding, service_root, xbmcaddon, xbmcvfs):
    """Capture acknowledgements before reading the remote snapshot."""
    import trakt_local_journal as journal
    from lib.trakt_outbox import Outbox
    addon=context('addon')
    store=Path(xbmcvfs.translatePath(addon.getAddonInfo('profile'))) / ('favorites_%s.json' % binding['profile'])
    database,_=journal._database(store)
    queue_path=service_root/'trakt_explicit_outbox.sqlite'
    if not queue_path.is_file() or queue_path.is_symlink():
        return set()
    queue=Outbox(queue_path)
    with sqlite3.connect(database) as db:
        db.execute('CREATE TABLE IF NOT EXISTS changes (id TEXT PRIMARY KEY,event TEXT NOT NULL,state TEXT NOT NULL)')
        rows=db.execute("SELECT id,event FROM changes WHERE state='queued'").fetchall()
    result=set()
    for ident,raw in rows:
        event=json.loads(raw); ids=event.get('outbox_ids',[])
        if event.get('scope')==binding and event.get('kind')=='Favorites' and ids and all((queue.status(item) or {}).get('state')=='confirmed' for item in ids):
            result.add(ident)
    return result
