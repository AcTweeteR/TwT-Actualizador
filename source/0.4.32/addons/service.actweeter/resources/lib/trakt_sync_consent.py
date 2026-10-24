"""Durable, scoped opt-in for Trakt-to-XStream automatic imports."""
import json
import os
import re
import tempfile
from pathlib import Path

POLICY_VERSION = 1


def _target(path):
    path = Path(path)
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError('unsafe synchronization consent path')
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.parent.stat().st_mode & 0o077:
        raise PermissionError('consent directory must be private')
    return path


def grant(path, *, account, profile, provider_scope):
    account, profile = str(account), str(profile)
    if (not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', account)
            or not re.fullmatch(r'[1-9][0-9]?', profile)
            or not re.fullmatch(r'[0-9a-f]{64}', str(provider_scope))):
        raise ValueError('verified account, profile and provider scope required')
    target = _target(path)
    data = {'schema': 1, 'enabled': True, 'policy': POLICY_VERSION,
            'account': account, 'profile': profile,
            'provider_scope': provider_scope}
    fd, temporary = tempfile.mkstemp(prefix='.consent-', dir=str(target.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, sort_keys=True, separators=(',', ':'))
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
    return data


def revoke(path):
    target = _target(path)
    if target.exists():
        target.unlink()
        directory_fd = os.open(str(target.parent), os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    return True


def suspend(path):
    target = Path(path)
    if target.is_symlink() or not target.is_file() or target.stat().st_size > 4096:
        return False
    try:
        data = json.loads(target.read_text('utf-8'))
    except (OSError, ValueError, UnicodeError):
        return False
    if not isinstance(data, dict) or data.get('schema') != 1:
        return False
    data['enabled'] = False
    _target(target)
    fd, temporary = tempfile.mkstemp(prefix='.consent-', dir=str(target.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, sort_keys=True, separators=(',', ':'))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    return True


def authorized(path, *, account, profile, provider_scope):
    target = Path(path)
    if target.is_symlink() or not target.is_file() or target.stat().st_size > 4096:
        return False
    try:
        data = json.loads(target.read_text('utf-8'))
    except (OSError, ValueError, UnicodeError):
        return False
    return (isinstance(data, dict) and data.get('schema') == 1
            and data.get('enabled') is True and data.get('policy') == POLICY_VERSION
            and data.get('account') == str(account)
            and data.get('profile') == str(profile)
            and data.get('provider_scope') == provider_scope)


def enabled(path):
    target = Path(path)
    if target.is_symlink() or not target.is_file() or target.stat().st_size > 4096:
        return False
    try:
        data = json.loads(target.read_text('utf-8'))
    except (OSError, ValueError, UnicodeError):
        return False
    return (isinstance(data, dict) and data.get('schema') == 1
            and data.get('enabled') is True and data.get('policy') == POLICY_VERSION)
