"""Extensible account integration registry; never stores or exports credentials.

An integration must implement its own authorization and transport. Registry
status is a UI capability declaration, not proof of an authorized session.
"""

SERVICES = {
    'trakt': {'name': 'Trakt', 'auth': 'existing_xstream_oauth',
              'features': ('watched', 'resume', 'pending', 'favorites'),
              'scrobbler': 'script.trakt'},
    'tmdb': {'name': 'TMDb', 'auth': 'user_session_required',
             'features': ('pending', 'favorites', 'watched_lists'),
             'scrobbler': None},
}


def accounts_view(states=None):
    """Return safe settings UI data with no credential material."""
    states = states or {}
    result = []
    for service, definition in SERVICES.items():
        state = states.get(service, {})
        status = state.get('status', 'not_connected')
        if status not in ('not_connected', 'connected', 'needs_authorization', 'error'):
            status = 'error'
        result.append({'id': service, 'name': definition['name'], 'status': status,
                       'authorization': definition['auth'],
                       'features': list(definition['features']),
                       'scrobbler': definition['scrobbler']})
    return result


def validate_extension(service_id, descriptor):
    """Validate future services without granting permissions or sharing tokens."""
    if (not isinstance(service_id, str) or not service_id.isascii() or
            not service_id.replace('_', '').isalnum() or service_id in SERVICES or
            not isinstance(descriptor, dict) or
            not isinstance(descriptor.get('name'), str) or not descriptor['name'].strip() or
            not isinstance(descriptor.get('features'), (list, tuple)) or
            any(feature not in ('watched', 'resume', 'pending', 'favorites', 'watched_lists')
                for feature in descriptor['features'])):
        raise ValueError('invalid integration descriptor')
    if any(k in descriptor for k in ('token', 'password', 'secret', 'api_key')):
        raise ValueError('credentials must not enter account registry')
    return {'id': service_id, 'name': descriptor['name'],
            'features': tuple(descriptor['features']), 'status': 'not_connected'}
