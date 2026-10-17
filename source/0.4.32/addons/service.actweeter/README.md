# AcTweeteR Service

Private Kodi helper add-on used by AcTweeteR for search coordination,
first-run setup, service status, and preview lifecycle integration.

The service does not contain account credentials. IPTV, YouTube/OAuth, Trakt,
and provider settings remain in their respective Kodi add-ons. Status checks
are on demand and intentionally report configuration presence separately from
connectivity or playback validation.

Every registered module is required. The dependency-first catalog drives
installation and version checks, and installed addon.xml files are inspected
recursively. SlyGuy's repository, dependencies, module and Trailers are prepared
through Kodi's native installer using their original feed. No SlyGuy ZIP is
redistributed. Its optional import in the bootstrap service's addon.xml only
permits that bootstrap to start; the completed setup contract requires the
whole chain. Missing components leave setup incomplete while Home stays usable.

Initial setup proceeds sequentially rather than asking users to select modules.
The maintenance menu provides retry, repair and sanitized diagnostics. A
previously completed setup is migrated to the current contract. Authentication
is rechecked before a new completion decision; playback QA is reported separately.

Kodi 21.3 InstallAddon installs absent IDs, but cannot update installed IDs.
Incompatible installed versions are directed to Kodi's supported updates screen;
the service preserves repository origin and update preferences. This native
confirmation is a remaining interaction, not an automatic-update guarantee.

0.4.3 is an experimental candidate. A complete clean installation, SlyGuy
playback, IPTV and device compatibility still require runtime acceptance.

The service is distributed through the AcTweeteR Kodi repository.
