# Beta 11 — XStream `series_recent` route repair

Beta 11 carries forward Skin 1.2.29~beta10 and Service 0.4.37 unchanged, and updates XStream Pro to 1.1.2.8 through the official Testing Kodi repository.

## Diagnosed defect

Lenovo ran XStream Pro 1.1.2.7 from the published package. The runtime traceback showed `premium_routes.py` calling `series_changes.recent(...)`, while the installed `series_changes.py` did not define `recent`. The installed module's SHA-256 matched the same member in the official 1.1.2.7 ZIP, so this was not a stale-install mismatch. The tracked AcTweeteR patch contained the function, but its new-file hunk declared 135 added lines while containing 142. The package builder did not verify the expected runtime-file hashes or that this route provider existed, so it emitted an incomplete ZIP without failing.

## Beta 11 changes

* Corrects the patch hunk count.
* Locks and verifies hashes of the packaged runtime modules.
* Fails the build unless the `series_changes.recent` provider is present in the ZIP.
* Adds XStream Pro 1.1.2.8 only to the Testing feed. Stable's `repo/` index and packages are unchanged.

The fix does not create or alter viewing history, resume points, credentials, or profile data. It only restores the missing provider function required by the existing `series_recent` route.

## Runtime check on Lenovo

After Kodi offers the update from the existing AcTweeteR Testing repository, use the D-pad to open Series → Añadidas recientemente. Confirm that Kodi no longer logs `AttributeError` for `series_changes.recent`; an empty result is acceptable if there are no recent series-change events. Use Back to return. Do not start playback as part of this check.

Automated tests and package verification are not a substitute for this Lenovo runtime check. Beta 11 remains a Testing-only candidate until that check is complete.
