"""Startup-only safety check: do not modify watched history in a running Kodi."""
from pathlib import Path
from .trakt_restore_startup import startup_restore_status


def inspect_all_profiles(xstream_profile, logger=None):
    root = Path(xstream_profile)
    status = startup_restore_status(root)
    if not status['safe'] and logger is not None:
        logger('Trakt restore blocked: %s (%s)' % (status['reason'], status['pending']))
    return status
