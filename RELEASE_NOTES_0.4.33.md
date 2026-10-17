# AcTweeteR 0.4.33 — test candidate

This is a prerelease candidate for validating the Skin Shortcuts
`widgetExpandable` migration on Kodi 21.3. It is not a stable release.

The 0.4.32 runtime attempt completed the first Skin Shortcuts build but then
failed while persisting widget properties. Runtime analysis found 26 source
defaults, of which 20 were materialized by the active profile; six defaults
from group `10000-1` were absent from the generated include. The migration had
incorrectly treated those unmaterialized defaults as a fatal error.

0.4.33 persists properties only for currently materialized widget identities.
It retains the second-build verification gate, so the migration still fails
unless every active expandable widget has the property in the generated XML.
No stable-feed files are changed by this test candidate. Runtime validation
and EXPANDIR interaction remain pending on the Lenovo.
