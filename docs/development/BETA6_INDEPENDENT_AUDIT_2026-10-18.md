# Independent Beta6 audit — 2026-10-18

## Scope and safety
Inspected the clean official branch at `24706f5` via Remote Desktop Commander and read the authorized Lenovo Kodi 21.3 log using ADB. No Kodi profile, playback, Android package, Master, Apple TV, Stable feed, or provider content was modified. This review does not establish runtime touch acceptance.

## Confirmed findings
1. `DialogVideoInfo.xml` selects exactly one of `BingieInfo` and `BingieAltInfo` using `UseBingieInfoDialog`. Both implement `radiobutton id=54` with a touch-action snapshot and shared `AcTweeteR_Primary_Trailer_Action`. However, `BingieAltInfo` uses explicit 280x72, whereas `BingieInfo` inherits 550x72 from `Bingie_InfoDialog_Button_Default_Defs`. They are not geometrically equivalent. A tap at about (300,860) on Lenovo failed; the control that handled the tap is unknown. Do not change dimensions or activate playback until the actual active layout and hit rectangle have been measured.
2. Kodi `Home.xml` triggers both the native Skin Shortcuts build and `first_run`. The service's layout migration can independently request additional Skin Shortcuts builds. Beta6 device log contains at 23:14:35 and 23:14:36 two requested builds, both completed with `output_changed=false`, followed by a Home reload at 23:14:41 and migration `verified`. Logs demonstrate redundant no-change requests, not a proven causal explanation for delayed widgets.
3. Kodi logs show `GetDirectory - Error getting include` during a Home reload and separate `GetDirectory - Error getting ActivateWindow(Settings)` events. Distinguish these failure classes. Log also reports `Trying to add unsupported control type 7` during `DialogVideoInfo.xml` load; source attribution and impact unproven.
4. A `service.search_refresh` plugin query completed in about 60053 ms without a reported error in the sampled log. This is evidence of a slow query, **not** proof that it blocked Home loading. Instrument correlation and timeline before changing retries or timeouts.
5. Earlier Lenovo Beta6 runtime data establishes only sampled poster-to-details, one horizontal swipe, and one vertical traversal; axes remain entangled, trailer touch remains FAIL, profile/collections/badges/autoplay/remote acceptance remains untested.

## Local changes
Added `source/0.4.32/tests/test_trailer_touch_contract.py`: 4 tests verifying both dialog layouts retain a diagnostic snapshot, one shared primary trailer action, clickable control type, and mutually exclusive selection. This is structural assurance, **not** a touch fix.

## Recommended next implementation sequence
- Identify actual `UseBingieInfoDialog` setting and visible dialog branch in Lenovo (read-only diagnostic; do not disclose media titles or provider URLs). Measure the control's transformed pixel bounds (parent positions, nested scroll, scale, overlays) and compare actual touch coordinates with D-pad or OK. If necessary, make a reversible beta-only change and validate on device through native Beta repository.
- Instrument Home startup with monotonic stage timings and correlation IDs; trace provider query completion, Skin Shortcuts changes, rows and first visible item. Stop duplicate build requests only after proving coordinator ownership/rollback.
- Test 2D gesture isolation across Spotlight/row edge/row center, then D-pad, EXPANDIR, Back; do not infer event recipient from focus telemetry.
- Audit XML references and dependency graph before deleting BINGIE features. Keep original visual style, five sidebar tabs and bottom actions, profile isolation and playback ownership.
- Run all tests and native Lenovo runtime QA before any Stable promotion.

## Validation
The local test suite increased from 47 to 51 tests; `python3 -m unittest discover -s source/0.4.32/tests -q` PASS (51/51). `tools/workspace_guard.py --require-branch codex/beta-widget-horizontal-navigation` PASS. Stable feed and installed Kodi were not changed.
