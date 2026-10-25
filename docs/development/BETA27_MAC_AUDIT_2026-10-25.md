# AcTweeteR Beta27 – Mac integration audit (2026-10-25)

Status: **LOCAL CANDIDATE INSTALLED IN KODI MAC; NOT PUBLISHED**. Stable repository remains unchanged. The working branch contains pre-existing uncommitted changes; do not discard them.

## Local candidate versions / integrity

| Add-on | Version | SHA-256 ZIP |
|---|---|---|
| XStream Pro | `1.1.2.34~beta1` | `0ebc6e12c55e4cdf2701d4a98828cc8dc93d6a247393965a9739535066761b74` |
| AcTweeteR Service | `0.4.88` | `9eb40d65ff553e3b4b92e29fc71c451ce612ba073c3b2a57b94f64bd3cb851ac` |
| Skin AcTweeteR | `1.2.32~beta15` | `a4e5a9a0082d43a83572b36dbd2de7d8e2e2e958ccfbcf8906b667ebdba47b24` |

Full local Testing layout: `/tmp/actweeter-beta27-candidate-v4/channel/` (not the published GitHub feed). Copy of installable ZIPs: `~/KodiBeta27-Candidata/`. Upstream XStream 1.1.2 ZIP SHA-256: `915f45708670d07e789bb73b7390a7b5cf30175f818ef5da8ea18c9f13f537fe`. Repository index and checksum independently constructed and byte-for-byte identical to the staged Testing channel. Official pinned Rivulet 1.0.2 and IAGL/Zach Morris 1.0.4 repositories are included.

## Evidence

- `python3.11 -m unittest discover -s tests -p 'test_*.py' -q`: **675 tests, 0 failures, 0 errors, 2 skipped**. File `/tmp/actweeter-beta27-full-tests-v4.log`. One intentional skip is Stable gate; Stable cannot be promoted until platform runtime checks finish. See test output for other skip.
- Kodi Mac 21.3 Omega, running installed `plugin.video.xstream-pro 1.1.2.34~beta1`, `service.actweeter 0.4.88`, `skin.actweeter 1.2.32~beta15`, enabled. Installed sequentially with Kodi native **Install from ZIP** GUI, not by copying add-on folders. Home loads and `INTERFACE_LAYOUT_UPDATE status=verified target=16` appears in kodi.log.
- Live Kodi JSON-RPC opened `plugin://plugin.video.xstream-pro/?mode=xstream_trakt_list&section=recommendations&tmdb_type=movie`. Directory displayed real items (current control `Chappie`), log says `Route timing: xstream_trakt_list finished in 1146 ms`. Prior missing `_tmdb_routes.trakt_recommendations_route` fixed in reproducible upstream patch to call `trakt_list_route`.
- `SlyGuy Trailers 0.2.2` source hashes matched recognized official signatures; `script.module.slyguy 0.87.4` player module likewise; bridge payload compiled in read-only dry run. Fixed frozen version conditions (0.2.1 / 0.87.3) while retaining fail-closed source hashes, backups and symlink protection. Kodi log after install reports `SLYGUY_PLAYER_GUARD status=RESTART_REQUIRED` before Kodi was gracefully restarted. The native installer wizard subsequently obtained consent and installed the bridge. Current manifest records `INSTALLED_NOT_RUNTIME_VERIFIED` for SlyGuy 0.2.2; log confirms `[SlyGuy] ACTWEETER_PREVIEW_BRIDGE status=started`. Automatic VIDEO playback still not verified.
- Added static guard for manual SlyGuy trailer info-dialog overlay in `DialogVideoInfo.xml`; XML parsing and release regression tests pass, but FULLSCREEN VISUAL TEST NOT YET PASSED.
- Series watched overlay: unknown/partial catalog preserves old Kodi watched state instead of forcing 0; known complete and known incomplete-with-proven-not-watched still update playcount. Real account season/episode/Trakt display still requires independent GUI validation. Local tests cover exact provider, TMDb and Trakt synchronization; no real Trakt writes were made during this audit.
- Rivulet 0.36.0 and IAGL 4.0.6 are enabled on Kodi Mac (both were present before this candidate). The AcTweeteR HOME launchers were tested live: Rivulet opened its HomeWindow and painted catalog rows; IAGL opened "Explorar todas las Listas" and logged `IAGL: Lets Play!`. Clean macOS/Android/tvOS bootstrap NOT YET VERIFIED. User forbids QA isolated profiles; do not wipe the Kodi Master profile to simulate a clean install.

## Recovery / limits

Prior Mac files backed up to `~/Documents/ChatGPT/Kodi AcTweeteR/runtime-backups/20261025-beta27-preinstall` (428 MB incl. 3 add-on directories, profile data and SQLite backup of Kodi Addons33.db). Do not overwrite or delete. This is not a guarantee of hot restoration; coordinate a safe Kodi shutdown before restoring. No Stable/remote Testing publication, no Trakt account mutations, no Lenovo/Apple TV installation. Remaining gates: verify actual automatic previews on a media-bearing Spotlight/widget control and manual fullscreen playback, verify movie/series/season/episode checks and synchronization, verify Rivulet/IAGL navigation, then publish Beta to Testing, install Lenovo, only then promote Stable and check Apple TV.

## Follow-up: runtime validation and visible trailer controls

- The Kodi wizard entry **Configuración inicial de AcTweeteR → Preparar tráilers y autorizaciones** successfully presented an explicit SlyGuy 0.2.2 authorization dialog. It was approved, and the integration wrote the backed-up manifest. The bridge has started; that is distinct from verifying a real trailer video.
- Discovered two hidden skin radiobuttons: Spotlight trailers `31370` and Home/widget trailers `31173` both had `<visible>false</visible>` in the source; delay control `31213` was hidden as well. Replaced visibility with conditions on installed SlyGuy/YouTube and `Skin.HasSetting(BingieAutoTrailer)`. Regression test `test_auto_preview_options_are_exposed_in_packaged_skin` prevents reintroduction.
- New skin `1.2.32~beta15` installed through native Kodi ZIP browser. Both controls now display in skin settings, confirmed via GUI. Kodi stores skin setting identifiers in **lowercase** (`spotlighttrailers` and `bingieautotrailer`), so an earlier uppercase-only inspection was incorrect. Both are now verified `true` and were toggled using native skin controls, not direct file modifications.
- Live Kodi routes tested for Trakt **watched movies**, **watched TV series** and **movie recommendations**; all display listings; no Trakt writes. The first attempted automatic preview logged `AUTO_PREVIEW_FOCUS_REJECT reason=context` after receiving an empty-media focus (`container=1508`, `identity=missing`). This **does not** establish preview success or a provider failure; retry with a real focused movie poster is still needed. The SlyGuy listener logs `decode_rejected` for non-`resolve` focus/exit notifications, which is consistent with its action filter and not sufficient evidence of a decode regression.
- Local Testing candidate v4 **not published**. Installed Mac packages: Service 0.4.88, XStream 1.1.2.34~beta1, Skin 1.2.32~beta15. Beta release and Stable promotion are gated on playback/check runtime and then Lenovo/Apple TV.
