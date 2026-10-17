# AcTweeteR 0.4.31

This maintenance release repairs Skin Shortcuts widget metadata migration.
The service now writes `widgetExpandable` through Skin Shortcuts 2.x's
profile-local custom-property contract, preserves unrelated property rows,
and verifies the generated include before recording migration success.

The known trailer-touch, collection/badge, and scroll runtime checks remain
unverified or unresolved; this release does not claim to fix them. No personal
profile, credential, playback progress, favorites, XStream data, or device was
modified during source/package preparation.
