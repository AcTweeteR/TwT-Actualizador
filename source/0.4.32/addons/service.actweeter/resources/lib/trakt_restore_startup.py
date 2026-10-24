"""Fail closed at startup if a watched restore was interrupted.

Recovery requires a separate stopped-Kodi operator action; never overwrite
XStream watched stores while Kodi is running.
"""
from .trakt_restore_guard import pending_restores


def startup_restore_status(xstream_profile):
    """Return whether Kodi should block further restores, without writing files."""
    try:
        pending = pending_restores(xstream_profile)
    except (OSError, ValueError) as exc:
        return {'safe': False, 'pending': -1, 'reason': type(exc).__name__}
    return {'safe': not bool(pending), 'pending': len(pending),
            'reason': 'recovery_required' if pending else 'ready'}
