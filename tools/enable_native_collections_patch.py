"""Narrow, assertive Trakt default-list integration for the existing XStream routes."""


def replace_once(source, before, after):
    if source.count(before) != 1:
        raise ValueError('unexpected upstream XStream route; no unsafe patch')
    return source.replace(before, after, 1)


def patch(source):
    source = replace_once(source, 'def _binding(context, trakt, xbmcaddon, xbmcvfs):', '''def _native_favorites_folder(addon, profile):
    """Use the real XStream favorites folder, never a guessed translated title."""
    from favorites import Favorites
    from lang import _t
    store = Favorites(addon, profile)
    existing = [name for name in ('Favorites', 'Favoritos')
                if any(row.get('stype') in ('movie', 'series')
                       for row in store.items.get(name, []))]
    if len(existing) > 1:
        raise PermissionError('two native favorites folders need manual review')
    if existing:
        return existing[0]
    translated = _t(30009) or 'Favorites'
    return translated if translated in ('Favorites', 'Favoritos') else 'Favorites'


def _stage_first_native_additions(context, catalog, identifier, source, mapping,
                                   binding, items, service_root, xbmcvfs):
    """Union-only first sync, exact TMDb IDs, never infer remote deletions."""
    from favorites import Favorites
    from trakt_provider_index import verified_vod_records
    from trakt_series_index import verified_show_records
    from trakt_live_consumer import _catalog_scope_verified
    from lib.trakt_outbox import Outbox, manual_event
    import hashlib
    addon = context('addon')
    root = Path(xbmcvfs.translatePath(addon.getAddonInfo('profile')))
    media = source['media_type']
    kind = 'movie' if media == 'movie' else 'show'
    if mapping.get('scope') != binding or not _catalog_scope_verified(
            [{'kind': kind}], root, binding['profile'], binding['provider_scope'], addon):
        raise PermissionError('native first sync catalog scope not verified')
    local = [row for row in Favorites(addon, binding['profile']).get_all(source['folder'])
             if row.get('stype') == media and not row.get('actweeter_trakt_origin')]
    if len(local) > 50:
        raise PermissionError('initial native collection exceeds safe export limit')
    if not local:
        return 0
    ids = sorted({str(row.get('id')) for row in local})
    records = (verified_vod_records(root, profile=binding['profile'], provider_ids=ids)
               if media == 'movie' else verified_show_records(root, profile=binding['profile']))
    matched = {}
    for row in records:
        matched.setdefault(str(row.get('provider_id')), []).append(row)
    already = {(row['kind'], row['tmdb_id']) for row in items}
    outbox = Outbox(service_root / 'trakt_explicit_outbox.sqlite')
    staged = 0
    for local_item in local:
        provider_id = str(local_item.get('id'))
        matches = matched.get(provider_id, [])
        if len(matches) != 1:
            continue  # No guessed title, no unverified provider identity.
        tmdb = matches[0].get('ids', {}).get('tmdb')
        if type(tmdb) is not int or tmdb < 1 or (kind, tmdb) in already:
            continue
        nonce = hashlib.sha256((mapping['revision'] + ':' + kind + ':' + str(tmdb)).encode()).hexdigest()[:32]
        event = manual_event(binding['account'], binding['profile'],
                             mapping['destination'] + '.add',
                             {'kind': kind, 'ids': {'tmdb': tmdb}}, nonce,
                             provider_scope=binding['provider_scope'])
        outbox.enqueue_manual(event, held=True)
        already.add((kind, tmdb))
        staged += 1
    return staged


def _binding(context, trakt, xbmcaddon, xbmcvfs):''')

    source = replace_once(source, '''                binding=_runtime_scope()
                if not binding or binding['account'] != account or binding['provider_scope'] != scope:
                    raise PermissionError('mapping scope changed')''', '''                import trakt_local_journal as journal
                from lib.collection_catalog import _runtime_scope
                addon = context('addon')
                store = (Path(xbmcvfs.translatePath(addon.getAddonInfo('profile')))
                         / ('favorites_%s.json' % profile))
                with journal.runtime_scope(store):
                    binding = _runtime_scope()
                if not binding or binding['account'] != account or binding['profile'] != profile or binding['provider_scope'] != scope:
                    raise PermissionError('mapping scope changed')''')

    source = replace_once(source, '''        sync_configured_collections(context, trakt, xbmcaddon, xbmcvfs, account=account,
                                    profile=profile, scope=scope, root=service_root)
        result = run_cycle(''', '''        # Native collections are optional. A failed/partial Trakt list GET
        # must never block the separately verified watched/resume cycle.
        if import_allowed:
            try:
                import trakt_local_journal as journal
                from lib.collection_catalog import Catalog, _runtime_scope
                native_store = xstream_root / ('favorites_%s.json' % profile)
                with journal.runtime_scope(native_store):
                    verified = _runtime_scope()
                    if not verified or (verified['account'], verified['profile'],
                                        verified['provider_scope']) != (account, profile, scope):
                        raise PermissionError('native collection account binding not verified')
                    if export_allowed:
                        folder = _native_favorites_folder(addon, profile)
                        Catalog(service_root / 'collections_catalog.db').ensure_native_defaults(
                            scope=verified, favorites_folder=folder, approved=True)
                    with Catalog(service_root / 'collections_catalog.db')._db() as db:
                        targets=[row[0] for row in db.execute('SELECT local_id FROM lists ORDER BY local_id')]
                    for target_id in targets:
                        try:
                            sync_configured_collections(context, trakt, xbmcaddon, xbmcvfs,
                                account=account, profile=profile, scope=scope,
                                root=service_root, stage_initial=export_allowed,
                                only_id=target_id)
                        except (OSError, ValueError, PermissionError, sqlite3.Error, RuntimeError) as exc:
                            xbmc.log('[AcTweeteR] TRAKT_NATIVE_LIST status=deferred type=%s' %
                                     type(exc).__name__, xbmc.LOGWARNING)
                if export_allowed and not one_shot:
                    retry_due_manual_actions(context, trakt, xbmcaddon, xbmcvfs,
                        account=account, profile=profile, scope=scope,
                        root=service_root, player=player)
            except (OSError, ValueError, PermissionError, sqlite3.Error, RuntimeError) as exc:
                xbmc.log('[AcTweeteR] TRAKT_NATIVE_COLLECTIONS status=deferred type=%s' %
                         type(exc).__name__, xbmc.LOGWARNING)
        result = run_cycle(''')

    source = replace_once(source, '''def sync_configured_collections(context, trakt, xbmcaddon, xbmcvfs, *, account, profile, scope, root):''', '''def sync_configured_collections(context, trakt, xbmcaddon, xbmcvfs, *, account, profile, scope, root, stage_initial=False, only_id=None):''')

    source = replace_once(source, '''        result=catalog.apply_remote(identifier,scope=binding,revision=mapping['revision'],items=items,
                                    observed_at=observed,complete=True,confirmed=confirmed)
        source=catalog.get(identifier)['mappings'].get('xstream_source')''', '''        native_source=catalog.get(identifier)['mappings'].get('xstream_source')
        if native_source and stage_initial:
            # Only once, before the first committed complete remote baseline.
            # Never turn a later Trakt removal into a re-add from an old cache.
            with catalog._db() as db:
                baseline=db.execute('SELECT 1 FROM remote_state WHERE local_id=?',
                                    (identifier,)).fetchone()
            if baseline is None:
                _stage_first_native_additions(context, catalog, identifier, native_source,
                                              mapping, binding, items, root, xbmcvfs)
        result=catalog.apply_remote(identifier,scope=binding,revision=mapping['revision'],items=items,
                                    observed_at=observed,complete=True,confirmed=confirmed)
        source=catalog.get(identifier)['mappings'].get('xstream_source')''')
    source = replace_once(source, "    desired=[]\n    for item in items:\n        matches=[row for row in records if str(row['ids'].get('tmdb'))==str(item['tmdb_id'])]\n        if len(matches)!=1:\n            # An unresolved remote member must not become an inferred deletion.\n            raise ValueError('native remote identity unresolved')\n        provider_id=str(matches[0]['provider_id'])\n        row=members.get(provider_id)\n        if not row:\n            raise ValueError('native provider member missing')\n        desired.append(dict(id=provider_id,stype=media,name=row.get('name') or item['title'],\n                            icon=row.get('stream_icon') or row.get('cover') or ''))\n    favorites=Favorites(addon,binding['profile'])", "    desired=[]\n    incomplete=False\n    for item in items:\n        matches=[row for row in records if str(row['ids'].get('tmdb'))==str(item['tmdb_id'])]\n        if len(matches)!=1:\n            incomplete=True  # Never guess a provider match.\n            continue\n        provider_id=str(matches[0]['provider_id'])\n        row=members.get(provider_id)\n        if not row:\n            incomplete=True\n            continue\n        desired.append(dict(id=provider_id,stype=media,name=row.get('name') or item['title'],\n                            icon=row.get('stream_icon') or row.get('cover') or ''))\n    favorites=Favorites(addon,binding['profile'])")
    source = replace_once(source, "        blocked={str(change['identity'][1]) for event in events if event.get('kind')=='Favorites'\n                 and event.get('origin')=='local' for change in event.get('changes',[])\n                 if change.get('folder_sha256')==source['folder_sha256'] and change.get('media_type')==media}\n        def commit_acknowledgements():", "        blocked={str(change['identity'][1]) for event in events if event.get('kind')=='Favorites'\n                 and event.get('origin')=='local' for change in event.get('changes',[])\n                 if change.get('folder_sha256')==source['folder_sha256'] and change.get('media_type')==media}\n        if incomplete:\n            # An incomplete provider match can still import exact matches, but\n            # must not remove previously imported entries.\n            blocked.update(str(item.get('id')) for item in favorites.get_all(source['folder'])\n                           if item.get('stype')==media and item.get('actweeter_trakt_origin')==mapping['revision'])\n        def commit_acknowledgements():")
    source = replace_once(source, "    for identifier,local_kind,mapping in mappings:\n        if not isinstance(mapping,dict) or mapping.get('scope') != binding:\n            continue", "    for identifier,local_kind,mapping in mappings:\n        if only_id is not None and identifier != only_id:\n            continue\n        if not isinstance(mapping,dict) or mapping.get('scope') != binding:\n            continue")
    source = replace_once(source, "        if incomplete:\n            # An incomplete provider match can still import exact matches, but\n            # must not remove previously imported entries.\n            blocked.update(str(item.get('id')) for item in favorites.get_all(source['folder'])\n                           if item.get('stype')==media and item.get('actweeter_trakt_origin')==mapping['revision'])\n        def commit_acknowledgements():", "        # A verified remote identity already present locally is safe to adopt\n        # even if it was originally in the native folder before sync was enabled.\n        # A pending local removal remains blocked from re-import or adoption.\n        adopted.update(str(item.get('id')) for item in favorites.get_all(source['folder'])\n                       if item.get('stype')==media and str(item.get('id')) in desired_ids)\n        if incomplete:\n            # An incomplete provider match can still import exact matches, but\n            # must not remove previously imported entries.\n            blocked.update(str(item.get('id')) for item in favorites.get_all(source['folder'])\n                           if item.get('stype')==media and item.get('actweeter_trakt_origin')==mapping['revision'])\n        def commit_acknowledgements():")
    return source
