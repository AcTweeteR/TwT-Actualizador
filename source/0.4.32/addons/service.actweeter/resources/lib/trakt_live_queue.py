"""Durable local hand-off for verified Trakt deltas; no network or Kodi API."""
import hashlib
import json
import os
import re
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit


def _stamp(value):
    if type(value) in (int, float) and value > 0:
        return float(value)
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.timestamp() if parsed.tzinfo else None
    except (ValueError, OverflowError):
        return None


def provider_fingerprint(profile, source_type, xtream_url='', username='', m3u_url=''):
    """Bind a queue to a provider profile without persisting credentials."""
    endpoint = (xtream_url or '').strip()
    user = (username or '').strip()
    if m3u_url:
        try:
            parsed = urlsplit(m3u_url)
            endpoint = endpoint or (parsed.hostname or '').casefold()
            query = parse_qs(parsed.query)
            user = user or next((query[k][0] for k in ('username', 'user', 'u')
                                 if query.get(k)), '')
            user = user or unquote(parsed.username or '')
            if not user:
                parts = [part for part in parsed.path.split('/') if part]
                if len(parts) >= 3 and parts[-1].casefold() in ('m3u8', 'm3u', 'm3u_plus', 'ts'):
                    user = parts[-3]
        except ValueError:
            return ''
    if endpoint:
        try:
            parsed = urlsplit(endpoint if '://' in endpoint else 'http://' + endpoint)
            endpoint = (parsed.hostname or '').casefold()
            if parsed.port:
                endpoint += ':' + str(parsed.port)
        except ValueError:
            return ''
    if not str(profile).isdigit() or not source_type or not endpoint or not user:
        return ''
    payload = json.dumps([str(profile), str(source_type).casefold(), endpoint, user],
                         separators=(',', ':'), ensure_ascii=True).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def _identity(item, kind):
    identity = item.get('identity')
    if (not isinstance(identity, dict) or identity.get('kind') != kind
            or not isinstance(identity.get('ids'), dict) or not identity['ids']
            or not all((re.fullmatch(r'[0-9]+', str(value)) if key != 'imdb'
                        else re.fullmatch(r'tt[0-9]+', str(value).casefold()))
                       for key, value in identity['ids'].items())):
        raise ValueError('exact typed content identity required')
    return identity


def build_batch(plan, *, provider_scope, consent=False, batch_id=None, target='provider',
                activity_fingerprint=None, catalog_generation=None, source_export=None):
    """Convert additions-only import plan to a bounded, credential-free batch."""
    if consent is not True:
        raise PermissionError('explicit synchronization consent required')
    profile, account = str(plan.get('profile', '')), str(plan.get('account', ''))
    if (not re.fullmatch(r'[1-9][0-9]?', profile)
            or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', account)
            or not re.fullmatch(r'[0-9a-f]{64}', str(provider_scope))):
        raise ValueError('account, profile and provider binding required')
    if target not in ('provider', 'tmdb'):
        raise ValueError('unsupported projection target')
    items = plan.get('items')
    if not isinstance(items, list) or len(items) > 5000:
        raise ValueError('invalid or oversized import plan')
    operations = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError('invalid import item')
        kind = item.get('identity', {}).get('kind')
        if kind not in ('movie', 'episode'):
            raise ValueError('unsupported content kind')
        identity = _identity(item, kind)
        provider_id = str(item.get('provider_id', ''))
        common = {'target': target, 'kind': kind,
                  'identity': identity, 'confidence': 'exact'}
        if target == 'provider':
            if not re.fullmatch(r'[0-9]+', provider_id):
                raise ValueError('verified provider ID required')
            common['provider_id'] = provider_id
        else:
            tmdb_id = identity.get('ids', {}).get('tmdb')
            if (not isinstance(tmdb_id, str) or not re.fullmatch(r'[1-9][0-9]*', tmdb_id)
                    or item.get('watched') is not True or 'position' in item):
                raise ValueError('exact TMDb watched identity required')
        if kind == 'episode':
            series_id = str(item.get('provider_series_id', ''))
            episode_id = str(item.get('provider_episode_id', ''))
            if (type(identity.get('season')) is not int
                    or type(identity.get('episode')) is not int):
                raise ValueError('exact episode coordinates required')
            common.update(season=identity['season'], episode=identity['episode'])
            if target == 'provider':
                if not re.fullmatch(r'[0-9]+', series_id) or episode_id != provider_id:
                    raise ValueError('exact provider episode reference required')
                common.update(series_id=series_id, episode_id=episode_id)
        if item.get('watched') is True:
            watched_at = _stamp(item.get('watched_at'))
            if watched_at is None:
                if target != 'tmdb':
                    raise ValueError('reliable watched timestamp required')
                watched_at = 0.0  # Unknown Trakt date: preserve watched state without inventing a date.
            op = dict(common, action='watched', timestamp=watched_at)
            operations[hashlib.sha256(_json(op)).hexdigest()] = op
        if 'position' in item:
            stamp = _stamp(item.get('paused_at'))
            position, duration = item.get('position'), item.get('duration')
            if (stamp is None or type(position) not in (int, float)
                    or type(duration) not in (int, float) or duration < 120
                    or position < 60 or position > duration * .93):
                raise ValueError('verified resume timestamp and bounds required')
            op = dict(common, action='resume', timestamp=stamp,
                      position=float(position), duration=float(duration))
            operations[hashlib.sha256(_json(op)).hexdigest()] = op
    if len(operations) > 200:
        raise ValueError('split the plan into batches of at most 200 operations')
    identifier = batch_id or uuid.uuid4().hex
    if not re.fullmatch(r'[0-9a-f]{32}', identifier):
        raise ValueError('invalid batch ID')
    envelope = {'schema': 1, 'target': target, 'batch_id': identifier, 'account': account,
                'profile': profile, 'provider_scope': provider_scope,
                'operations': [{'id': key, **operations[key]}
                               for key in sorted(operations)]}
    if activity_fingerprint is not None:
        if not re.fullmatch(r'[0-9a-f]{64}', str(activity_fingerprint)):
            raise ValueError('invalid remote activity checkpoint')
        envelope['activity_fingerprint'] = activity_fingerprint
    if catalog_generation is not None:
        if not re.fullmatch(r'[0-9a-f]{64}', str(catalog_generation)):
            raise ValueError('invalid catalog generation')
        envelope['catalog_generation'] = catalog_generation
    if source_export is not None:
        if (not isinstance(source_export, str) or len(source_export) > 512
                or Path(source_export).is_absolute() or '..' in Path(source_export).parts
                or not re.fullmatch(r'[A-Za-z0-9_./-]+', source_export)):
            raise ValueError('unsafe export reference')
        envelope['source_export'] = source_export
    envelope['sha256'] = hashlib.sha256(_json(envelope)).hexdigest()
    return envelope


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('utf-8')


def write_batch(directory, batch):
    root = Path(directory)
    if root.is_symlink():
        raise ValueError('unsafe queue directory')
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.stat().st_mode & 0o077:
        raise PermissionError('queue directory must be private')
    target = root / (batch['batch_id'] + '.json')
    if target.exists() or target.is_symlink():
        raise FileExistsError('batch already exists')
    fd, temporary = tempfile.mkstemp(prefix='.pending-', dir=str(root))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(_json(batch))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        directory_fd = os.open(str(root), os.O_RDONLY)
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
    return target


def verify_batch(batch, *, profile, account, provider_scope):
    if not isinstance(batch, dict):
        raise ValueError('invalid batch')
    supplied = batch.get('sha256')
    unsigned = dict(batch)
    unsigned.pop('sha256', None)
    if supplied != hashlib.sha256(_json(unsigned)).hexdigest():
        raise ValueError('batch checksum mismatch')
    target = batch.get('target', 'provider')
    if (target not in ('provider', 'tmdb') or batch.get('schema') != 1 or str(batch.get('profile')) != str(profile)
            or batch.get('account') != account
            or batch.get('provider_scope') != provider_scope
            or not re.fullmatch(r'[0-9a-f]{32}', str(batch.get('batch_id', '')))
            or not isinstance(batch.get('operations'), list)):
        raise PermissionError('batch scope mismatch')
    if ('activity_fingerprint' in batch and not re.fullmatch(
            r'[0-9a-f]{64}', str(batch['activity_fingerprint']))):
        raise ValueError('invalid remote activity checkpoint')
    if ('catalog_generation' in batch and not re.fullmatch(
            r'[0-9a-f]{64}', str(batch['catalog_generation']))):
        raise ValueError('invalid catalog generation')
    if ('source_export' in batch and (not isinstance(batch['source_export'], str)
            or len(batch['source_export']) > 512 or Path(batch['source_export']).is_absolute()
            or '..' in Path(batch['source_export']).parts
            or not re.fullmatch(r'[A-Za-z0-9_./-]+', batch['source_export']))):
        raise ValueError('unsafe export reference')
    for operation in batch['operations']:
        content = dict(operation)
        operation_id = content.pop('id', None)
        if (not isinstance(operation_id, str)
                or operation_id != hashlib.sha256(_json(content)).hexdigest()):
            raise ValueError('operation checksum mismatch')
        if content.get('target', target) != target:
            raise ValueError('projection target mismatch')
    return batch


def write_ack(path, batch, results):
    """Durably acknowledge only the outcomes XStream reports after store save."""
    expected = {operation['id'] for operation in batch['operations']}
    if (not isinstance(results, list) or len(results) != len(expected)
            or any(not isinstance(row, dict) for row in results)
            or {row.get('id') for row in results} != expected
            or any(row.get('status') not in ('applied', 'already_applied', 'superseded', 'deferred')
                   for row in results)):
        raise ValueError('incomplete or invalid operation results')
    payload = {'schema': 1, 'target': batch.get('target', 'provider'),
               'batch_id': batch['batch_id'],
               'account': batch['account'], 'profile': batch['profile'],
               'provider_scope': batch['provider_scope'], 'results': results}
    payload['sha256'] = hashlib.sha256(_json(payload)).hexdigest()
    target = Path(path)
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if target.parent.is_symlink() or target.parent.stat().st_mode & 0o077:
        raise PermissionError('ack directory must be private')
    fd, temporary = tempfile.mkstemp(prefix='.ack-', dir=str(target.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(_json(payload)); stream.flush(); os.fsync(stream.fileno())
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
    return payload


def verify_ack(ack, batch):
    if not isinstance(ack, dict) or ack.get('schema') != 1:
        raise ValueError('invalid acknowledgement')
    supplied = ack.get('sha256')
    unsigned = dict(ack); unsigned.pop('sha256', None)
    if supplied != hashlib.sha256(_json(unsigned)).hexdigest():
        raise ValueError('ack checksum mismatch')
    if any(ack.get(key) != batch.get(key) for key in
           ('batch_id', 'account', 'profile', 'provider_scope')) or ack.get(
               'target', 'provider') != batch.get('target', 'provider'):
        raise PermissionError('ack scope mismatch')
    expected = {operation['id'] for operation in batch['operations']}
    rows = ack.get('results', [])
    if (not isinstance(rows, list) or len(rows) != len(expected)
            or any(not isinstance(row, dict) for row in rows)
            or {row.get('id') for row in rows} != expected
            or any(row.get('status') not in
                   ('applied', 'already_applied', 'superseded', 'deferred') for row in rows)):
        raise RuntimeError('batch has unconfirmed operations')
    return rows


def checkpoint_from_ack(ack, batch):
    rows = verify_ack(ack, batch)
    if any(row['status'] == 'deferred' for row in rows):
        raise RuntimeError('batch has unconfirmed operations')
    expected = {operation['id'] for operation in batch['operations']}
    return {'account': batch['account'], 'profile': batch['profile'],
            'provider_scope': batch['provider_scope'],
            'batch_id': batch['batch_id'],
            'operation_ids': sorted(expected)}


def persist_checkpoint(path, checkpoint):
    """Advance only after a complete ack; refuse cross-account/profile reuse."""
    target = Path(path)
    if target.is_symlink() or target.parent.is_symlink():
        raise ValueError('unsafe checkpoint path')
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if target.parent.stat().st_mode & 0o077:
        raise PermissionError('checkpoint directory must be private')
    scope = {key: checkpoint[key] for key in ('account', 'profile', 'provider_scope')}
    previous = {'schema': 1, **scope, 'batches': []}
    if target.exists():
        previous = json.loads(target.read_text('utf-8'))
        if previous.get('schema') != 1 or any(previous.get(k) != v for k, v in scope.items()):
            raise PermissionError('checkpoint scope changed; explicit rebind required')
    batches = [row for row in previous.get('batches', [])
               if row.get('batch_id') != checkpoint['batch_id']]
    batches.append({'batch_id': checkpoint['batch_id'],
                    'operation_ids': checkpoint['operation_ids']})
    payload = {'schema': 1, **scope, 'batches': batches[-32:], 'updated_at': time.time()}
    if target.exists() and previous.get('batches', []) == payload['batches']:
        return previous
    fd, temporary = tempfile.mkstemp(prefix='.checkpoint-', dir=str(target.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(_json(payload)); stream.flush(); os.fsync(stream.fileno())
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
    return payload
