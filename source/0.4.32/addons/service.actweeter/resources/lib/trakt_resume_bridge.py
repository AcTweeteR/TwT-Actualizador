"""Offline XStream resume staging with explicit playback-reference verification.

Never derives an IPTV URL from a provider ID or title. Caller must supply a
trusted, current playback reference; missing references remain deferred.
"""
import math


def stage_resume(plan, playback_references, existing=None):
    if not isinstance(playback_references, dict) or not isinstance(existing, dict):
        raise ValueError('validated references and existing store required')
    staged = dict(existing)
    deferred = []
    added = 0
    for item in plan.get('items', []):
        if 'position' not in item:
            continue
        provider = str(item.get('provider_id', ''))
        reference = playback_references.get(provider)
        if not isinstance(reference, dict) or reference.get('provider_id') != provider:
            deferred.append(provider)
            continue
        name, url = reference.get('name'), reference.get('url')
        if not isinstance(name, str) or not name.strip() or not isinstance(url, str) or not url.startswith(('https://', 'http://')):
            deferred.append(provider)
            continue
        pos, duration = item['position'], item['duration']
        if (type(pos) not in (float, int) or type(duration) not in (float, int)
                or not math.isfinite(pos) or not math.isfinite(duration)
                or duration < 120 or pos < 60 or pos > duration * 0.93):
            deferred.append(provider)
            continue
        key = name + '||' + url
        if key in staged:
            deferred.append(provider)  # Existing local progress is authoritative.
            continue
        staged[key] = {'name': name, 'url': url, 'position': pos,
                       'duration': duration, 'timestamp': 0.0, 'stype': 'movie'}
        added += 1
    return {'staged': staged, 'added': added, 'deferred': deferred}
