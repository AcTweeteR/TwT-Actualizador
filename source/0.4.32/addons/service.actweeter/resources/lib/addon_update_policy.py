"""Kodi-wide update policy for managed AcTweeteR installations.

Kodi repositories cannot themselves mandate a host-wide setting. The service
checks the policy at startup and requests notification-only mode via JSON-RPC.
"""
import json

SETTING = 'general.addonupdates'
NOTIFY_ONLY = 1


def ensure_notify_only(execute_jsonrpc):
    def call(method, params):
        response = json.loads(execute_jsonrpc(json.dumps({
            'jsonrpc': '2.0', 'id': 'actweeter-update-policy',
            'method': method, 'params': params,
        })))
        if not isinstance(response, dict) or 'error' in response:
            raise RuntimeError('Kodi update policy JSON-RPC failed')
        return response.get('result')

    current = call('Settings.GetSettingValue', {'setting': SETTING})
    if not isinstance(current, dict) or type(current.get('value')) is not int:
        raise RuntimeError('Kodi update setting unavailable')
    if current['value'] == NOTIFY_ONLY:
        return 'ALREADY_PROTECTED'
    if call('Settings.SetSettingValue', {'setting': SETTING, 'value': NOTIFY_ONLY}) is not True:
        raise RuntimeError('Kodi rejected notification-only update setting')
    verified = call('Settings.GetSettingValue', {'setting': SETTING})
    if not isinstance(verified, dict) or verified.get('value') != NOTIFY_ONLY:
        raise RuntimeError('Kodi did not retain notification-only update setting')
    return 'PROTECTED'
