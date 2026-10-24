"""Prepare and dispatch one consented Trakt-to-XStream delta batch."""
import json
from pathlib import Path

from .trakt_live_queue import (build_batch, checkpoint_from_ack, persist_checkpoint,
                               provider_fingerprint, verify_batch, write_batch)
from .trakt_restore_importer import (prepare_restore, prepare_tmdb_restore,
                                     preview_changes)


def prepare_batch(export_directory, xstream_profile, *, profile, account,
                  provider_scope, consent=False, activity_fingerprint=None, catalog_generation=None, source_export=None):
    batches = prepare_batches(export_directory, xstream_profile, profile=profile,
        account=account, provider_scope=provider_scope, consent=consent,
        activity_fingerprint=activity_fingerprint, catalog_generation=catalog_generation, source_export=source_export)
    if len(batches) != 1:
        raise ValueError('plan exceeds a single bounded batch')
    return batches[0]


def prepare_batches(export_directory, xstream_profile, *, profile, account,
                    provider_scope, consent=False, activity_fingerprint=None, catalog_generation=None, source_export=None):
    common = dict(provider_scope=provider_scope, consent=consent,
                  activity_fingerprint=activity_fingerprint,
                  catalog_generation=catalog_generation, source_export=source_export)
    tmdb = prepare_tmdb_restore(export_directory, profile=profile, account=account)
    batches = []
    for offset in range(0, len(tmdb['items']), 100):
        batches.append(build_batch(dict(tmdb, items=tmdb['items'][offset:offset + 100]),
                                   target='tmdb', **common))
    try:
        plan = prepare_restore(export_directory, xstream_profile,
                               profile=profile, account=account)
        plan = preview_changes(plan, xstream_profile, profile=profile)['plan']
        safe_items = plan['items']
    except (OSError, ValueError):
        # TMDb-native watched state remains importable without a local provider catalog.
        safe_items = []
        plan = {'profile': str(profile), 'account': account, 'items': []}
    for offset in range(0, len(safe_items), 100):
        batches.append(build_batch(dict(plan, items=safe_items[offset:offset + 100]),
                                   target='provider', **common))
    return batches


def provider_scope_from_addon(addon, profile):
    """Read current XStream profile identity into a non-reversible scope hash."""
    prefix = 'profile_%s_' % profile
    return provider_fingerprint(
        profile, addon.getSetting(prefix + 'source_type'),
        addon.getSetting(prefix + 'xtream_url'),
        addon.getSetting(prefix + 'xtream_username'),
        addon.getSetting(prefix + 'm3u'))


def dispatch_batch(kodi, service_addon, vfs, batch, *, player_active=False):
    if player_active:
        return {'status': 'deferred', 'reason': 'playback_active'}
    root = Path(vfs.translatePath(service_addon.getAddonInfo('profile')))
    queue = root / 'trakt_live' / 'queue'
    target = write_batch(queue, batch)
    url = ('plugin://plugin.video.xstream-pro/?mode=xstream_trakt_apply&batch=' +
           batch['batch_id'])
    kodi.executebuiltin('RunPlugin(%s)' % url, False)
    return {'status': 'dispatched', 'batch_id': batch['batch_id'],
            'queue_path': str(target)}


def confirm_batch(service_addon, vfs, batch):
    root = Path(vfs.translatePath(service_addon.getAddonInfo('profile')))
    path = root / 'trakt_live' / 'acks' / (batch['batch_id'] + '.json')
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1_000_000:
        return None
    try:
        ack = json.loads(path.read_text('utf-8'))
        checkpoint = checkpoint_from_ack(ack, batch)
        return persist_checkpoint(root / 'trakt_live' / 'checkpoints' /
                                 ('profile_' + str(batch['profile']) + '.json'), checkpoint)
    except (OSError, ValueError, PermissionError, RuntimeError, TypeError):
        return None


def load_batch(path, *, profile, account, provider_scope):
    target = Path(path)
    if target.is_symlink() or not target.is_file() or target.stat().st_size > 2_000_000:
        raise ValueError('unsafe queued batch')
    return verify_batch(json.loads(target.read_text('utf-8')), profile=profile,
                        account=account, provider_scope=provider_scope)
