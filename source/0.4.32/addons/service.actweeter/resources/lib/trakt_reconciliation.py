"""Read-only bridge from a verified Trakt import to uncertain local history writes.

No network access, no automatic POST, no guessed identity and no mutation of
unrelated operations. A caller must fetch a complete authenticated snapshot.
"""


def reconcile_uncertain(outbox, operations, snapshot, *, account, profile):
    if (not isinstance(snapshot, dict) or snapshot.get('complete') is not True
            or snapshot.get('account') != account
            or not isinstance(snapshot.get('history'), list)
            or not isinstance(operations, (list, tuple))):
        raise ValueError('complete account-bound history required')
    if not str(profile).isdigit() or int(profile) < 1:
        raise ValueError('valid profile required')
    results = {}
    for operation in operations:
        if not isinstance(operation, str) or not operation:
            raise ValueError('valid operation ID required')
        status = outbox.status(operation)
        if status is None:
            raise ValueError('unknown operation')
        if status['state'] in ('unknown', 'inflight'):
            results[operation] = outbox.confirm_from_snapshot(
                operation, snapshot, account=account, profile=profile)
        else:
            results[operation] = status['state']
    return results
