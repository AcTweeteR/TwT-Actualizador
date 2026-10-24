"""One opt-in Trakt GET → durable queue → XStream apply cycle.

The XStream route supplies its native authenticated GET/export and its own
history classes. No credentials or network transport enter this module.
"""
import hashlib
import json
import os
import tempfile
from pathlib import Path

from .trakt_live_queue import verify_batch, verify_ack, write_batch
from .trakt_live_sync import confirm_batch, prepare_batches
from .trakt_sync_consent import authorized


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def _write(path, value):
    target = Path(path)
    if target.is_symlink() or target.parent.is_symlink():
        raise ValueError('unsafe sync state path')
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if target.parent.stat().st_mode & 0o077:
        raise PermissionError('sync state directory must be private')
    fd, temporary = tempfile.mkstemp(prefix='.sync-', dir=str(target.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, sort_keys=True, separators=(',', ':'))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        directory_fd = os.open(str(target.parent), os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _checkpoint(path, *, account, profile, provider_scope):
    target = Path(path)
    if target.is_symlink() or not target.is_file() or target.stat().st_size > 4096:
        return None
    try:
        value = json.loads(target.read_text('utf-8'))
    except (OSError, ValueError, UnicodeError):
        return None
    if any(value.get(key) != expected for key, expected in (
            ('account', account), ('profile', str(profile)),
            ('provider_scope', provider_scope))):
        return None
    return value


def catalog_generation(root, profile):
    """Stat only: a changed catalog/metadata cache must retry previously unmatched IDs."""
    prefixes = ('data_cache_p%s_xtream_streams_' % profile,
                'data_cache_p%s_vod_info_' % profile,
                'data_cache_p%s_series_info_' % profile,
                'data_cache_p%s_premium_meta_' % profile)
    rows = []
    with os.scandir(root) as entries:
        for entry in entries:
            if (entry.name.startswith(prefixes) and entry.name.endswith('.json')
                    or entry.name == 'series_changes_p%s.json' % profile):
                if entry.is_symlink():
                    raise ValueError('unsafe provider evidence')
                stat = entry.stat()
                rows.append((entry.name, stat.st_size, stat.st_mtime_ns, stat.st_ino))
    return _digest(sorted(rows))


def _run_cycle(service_root, xstream_root, *, account, profile, provider_scope,
              activity_get, export_snapshot, apply_batch, addon, history, playing_file='',
              consent_path=None, one_shot=False, binding_valid=lambda: True):
    """Process one bounded batch, retaining queue data until durable confirmation."""
    profile, account = str(profile), str(account)
    root = Path(service_root)
    state_root = root / 'trakt_live'
    state_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    consent_file = Path(consent_path or state_root / 'consent.json')
    if not one_shot and not authorized(consent_file, account=account, profile=profile,
                                       provider_scope=provider_scope):
        return {'status': 'suspended', 'reason': 'consent_scope_changed'}
    if playing_file:
        return {'status': 'deferred', 'reason': 'playback_active'}

    queue = state_root / 'queue'
    ack_root = state_root / 'acks'
    cursor_path = state_root / 'remote' / ('profile_%s.json' % profile)
    if state_root.is_symlink() or queue.is_symlink():
        return {'status': 'failed', 'reason': 'unsafe_sync_state_path'}
    if not binding_valid():
        return {'status': 'suspended', 'reason': 'live_binding_or_playback_changed'}
    pending = sorted(queue.glob('*.json')) if queue.is_dir() else []
    if pending:
        # Advance fairly past unresolved batches without deleting them or
        # advancing the remote cursor. A later catalog refresh can retry them.
        rotation_path = state_root / 'cycle_rotation.json'
        rotation = _checkpoint(rotation_path, account=account, profile=profile,
                               provider_scope=provider_scope) or {}
        last = rotation.get('last_batch', '')
        if not isinstance(last, str):
            last = ''
        batch_path = next((path for path in pending if path.name > last), pending[0])
        batch = verify_batch(json.loads(batch_path.read_text('utf-8')),
                             profile=profile, account=account,
                             provider_scope=provider_scope)
        if batch.get('activity_fingerprint') is None:
            return {'status': 'deferred', 'reason': 'legacy_batch_without_remote_cursor'}
        ack = apply_batch(str(batch_path), ack_root, profile=profile,
                          account=account, provider_scope=provider_scope,
                          addon=addon, history=history,
                          catalog_root=xstream_root, playing_file=playing_file)
        # A deferred ACK is valid evidence of an attempted batch, but must
        # never advance the durable applied checkpoint or remote cursor.
        rows = verify_ack(ack, batch)
        if any(row['status'] == 'deferred' for row in rows):
            _write(rotation_path, {'account': account, 'profile': profile,
                                   'provider_scope': provider_scope,
                                   'last_batch': batch_path.name})
            return {'status': 'deferred', 'reason': 'operations_deferred',
                    'remaining_batches': len(pending)}
        if confirm_batch(_ServiceAddon(root), _VFS(), batch) is None:
            return {'status': 'deferred', 'reason': 'operations_unconfirmed'}
        _write(rotation_path, {'account': account, 'profile': profile,
                               'provider_scope': provider_scope,
                               'last_batch': batch_path.name})
        batch_path.unlink()
        remaining = sorted(queue.glob('*.json')) if queue.is_dir() else []
        if remaining:
            return {'status': 'pending', 'remaining_batches': len(remaining)}
        cursor = {'schema': 1, 'account': account, 'profile': profile,
                  'provider_scope': provider_scope,
                  'activity_fingerprint': batch['activity_fingerprint'],
                  'catalog_generation': batch.get('catalog_generation'), 'planner_contract': 2,
                  'source_export': batch.get('source_export')}
        _write(cursor_path, cursor)
        return {'status': 'applied', 'operations': len(batch['operations'])}

    remote_account, activity = activity_get()
    if remote_account != account or not isinstance(activity, dict):
        return {'status': 'suspended', 'reason': 'account_or_activity_changed'}
    fingerprint = _digest(activity)
    previous = _checkpoint(cursor_path, account=account, profile=profile,
                           provider_scope=provider_scope)
    generation = catalog_generation(xstream_root, profile)
    if (previous and previous.get('activity_fingerprint') == fingerprint
            and previous.get('catalog_generation') == generation
            and previous.get('planner_contract') == 2):
        return {'status': 'unchanged'}
    export_directory = None
    if previous and previous.get('activity_fingerprint') == fingerprint:
        relative = previous.get('source_export')
        if isinstance(relative, str) and not Path(relative).is_absolute() and '..' not in Path(relative).parts:
            candidate = Path(xstream_root) / relative
            if (candidate.is_dir() and not candidate.is_symlink()
                    and Path(xstream_root).resolve() in candidate.resolve().parents):
                export_directory = candidate
    if export_directory is None:
        export_directory = export_snapshot()
    if not binding_valid():
        return {'status': 'suspended', 'reason': 'binding_changed_during_export'}
    for attempt in range(2):
        try:
            try:
                source_export = str(Path(export_directory).resolve().relative_to(Path(xstream_root).resolve()))
            except ValueError:
                source_export = None
            batches = prepare_batches(export_directory, xstream_root, profile=profile,
                account=account, provider_scope=provider_scope, consent=True,
                activity_fingerprint=fingerprint, catalog_generation=generation, source_export=source_export)
            break
        except (OSError, ValueError):
            if attempt or not (previous and previous.get('activity_fingerprint') == fingerprint):
                raise
            # A corrupt/legacy cached proof is not an empty plan: fetch anew once.
            export_directory = export_snapshot()
            if not binding_valid():
                return {'status': 'suspended', 'reason': 'binding_changed_during_export'}
    queue.mkdir(mode=0o700, parents=True, exist_ok=True)
    targets = [write_batch(queue, batch) for batch in batches]
    return {'status': 'queued', 'batches': len(targets),
            'operations': sum(len(batch['operations']) for batch in batches)}


def run_cycle(service_root, xstream_root, **kwargs):
    """Exclude overlapping cycles and recover a lock left by a dead Kodi process."""
    root = Path(service_root) / 'trakt_live'
    if root.is_symlink():
        return {'status': 'failed', 'reason': 'unsafe_cycle_state_path'}
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.stat().st_mode & 0o077:
        return {'status': 'failed', 'reason': 'sync_state_directory_not_private'}
    lock = root / 'cycle.lock'
    if lock.is_symlink():
        return {'status': 'failed', 'reason': 'unsafe_cycle_lock'}
    try:
        fd = os.open(str(lock), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        try:
            owner = int(lock.read_text('ascii')[:20])
            if owner <= 0:
                return {'status': 'busy'}
            try:
                os.kill(owner, 0)
            except ProcessLookupError:
                lock.unlink()
                fd = os.open(str(lock), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except (PermissionError, OSError):
                return {'status': 'busy'}
            else:
                return {'status': 'busy'}
        except (OSError, FileExistsError, ValueError):
            try:
                if os.path.getmtime(lock) < __import__('time').time() - 60:
                    lock.unlink()
                    fd = os.open(str(lock), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                else:
                    return {'status': 'busy'}
            except (OSError, FileExistsError):
                return {'status': 'busy'}
    try:
        with os.fdopen(fd, 'w', encoding='ascii') as stream:
            stream.write(str(os.getpid()))
            stream.flush()
            os.fsync(stream.fileno())
        return _run_cycle(service_root, xstream_root, **kwargs)
    finally:
        try:
            if lock.read_text('ascii').strip() == str(os.getpid()):
                lock.unlink()
        except OSError:
            pass


class _ServiceAddon:
    def __init__(self, root):
        self.root = root

    def getAddonInfo(self, key):
        return str(self.root) if key == 'profile' else ''


class _VFS:
    @staticmethod
    def translatePath(path):
        return str(path)
