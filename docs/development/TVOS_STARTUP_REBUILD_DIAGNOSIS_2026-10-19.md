# tvOS startup rebuilds — partial diagnosis, publication blocked

**Historical checkpoint:** the subsequent user mission authorized a Testing
release and moved runtime investigation to Master/Lenovo. New real-data
evidence and the profile-scope fix are documented in
`BETA_0_4_41_MASTER_LENOVO.md`. The Apple TV remains untouched and its acceptance
is still pending; this original report is retained without rewriting history.

## Scope and baseline

- Base: official main `63be13db36edb452009c228d82169e6126c126d1` (PR #22).
- Isolated worktree: `TwT-Actualizador-startup-rebuild`.
- Branch: `codex/startup-skinshortcuts-idempotence`.
- Apple TV was queried using an allowlisted, read-only JSON-RPC client. No
  settings, properties, files, add-ons, playback or navigation were changed.
  The user closed/reopened Kodi manually when requested.
- Master and other worktrees were not modified. Tests use temporary directories,
  not a Kodi profile. No new version/package/feed/release is published here.

## Actual remote evidence

Authenticated `JSONRPC.Ping`, `Application.GetProperties`,
`GUI.GetProperties`, `Addons.GetAddonDetails`, `Player.GetActivePlayers` and
`XBMC.GetInfoLabels` returned:

| Observation | Result |
| --- | --- |
| Kodi | 21.3, stable |
| Skin | skin.actweeter 1.2.29~beta11, enabled, not broken |
| Service | service.actweeter 0.4.40, enabled, not broken |
| Skin Shortcuts | 2.0.3, enabled, not broken |
| Foreground | Home, INICIO |
| Playback at initial inspection | no active players |
| InterfaceReady | empty before and after the manual restart |
| InterfaceMigrationAttempted | populated after startup, stable across samples |
| skinshortcuts-reloadmainmenu | two separate True-to-empty cycles sampled |
| skinshortcuts-isrunning | not observed True in the samples |

The user reports approximately five menu writes/reloads. Sampling a property
is **not** a reliable count of completed builds: the exact number and terminal
error remain NOT_MEASURED. No claim of five independently observed builds is
made. Automatic and manual trailer success are the user's current baseline;
this investigation did not start playback or revalidate it.

`Files.PrepareDownload(special://logpath/kodi.log)` returns a native HTTP route,
but downloading that route with the same authentication returns HTTP 401.
RPC remains authenticated (`Ping` still returns pong). This is a log-download
access restriction, not proof of an invalid RPC password. No security setting
was changed and no alternate filesystem access was attempted. Consequently the
actual terminal INTERFACE_LAYOUT/SKINSHORTCUTS_BUILD log event is unavailable.

## Trigger inventory

| Route | Caller / condition | Duplicate protection |
| --- | --- | --- |
| Home.xml:21 first_run | each Home load, including ReloadSkin | first-run process claim, independent layout claim |
| setup.py `_run_pending_interface_migration` | pending migration or generated output failing readiness | output signature + process claim + bounded retry |
| setup.py `_finish_setup` | explicit wizard completion | shared prepare lock and generated-output reuse |
| setup.py prepare_interface / repair_interface actions | explicit supported repair | same shared preparation function |
| interface_layout.py `_prepare_interface` identity build | after data/settings preparation when reuse fails | exclusive profile lock; checks native busy property |
| same function property build | properties changed or expansion output unverified | second pass skipped when unchanged and verified |
| SkinSettings.xml:6 buildxml | leaving skin settings | native Skin Shortcuts busy/hash checks; not proven active at startup |
| IncludesContextMenu.xml / IncludesSkinSettings.xml / extras/bingiesettings.xml | explicit view/settings actions | conditional; no evidence of startup execution |
| shortcuts/powermenu.DATA.xml / overrides.xml ReloadSkin | explicit Reload action | user initiated; not an automatic startup caller |
| setup.py intro | first_run with AcTweeteR splash mode | once-per-process intro claim |

The bridge no longer belongs to `_prepare_interface` after PR #22. Its consent
offer belongs to explicit optional trailer setup. This change does not touch
bridge consent, autoplay hooks, playback ownership, trailer resolution or XML.

## Confirmed code defect, not yet the full device root cause

`interface_layout.py:43` classified all three deterministic validation failures
as transient:

- BUILD_OUTPUT_INVALID
- GENERATED_XML_PROPERTY_MISSING
- GENERATED_IDENTITY_INVALID

`retry_interface_preparation` then invokes preparation six times using delays
1, 2, 4, 8 and 15 seconds. On each attempt `_prepare_interface` can request
native builds; its property phase explicitly sets reloadmainmenu=True. An
unsatisfied validation therefore feeds repeated rebuild/ReloadSkin attempts
without changing inputs to repair the validation error.

The new regression test was executed **before** changing production code:
all three subcases failed because preparation ran six times rather than once.
After removing these errors from the transient retry set they pass with one
attempt, no retry delay, and the original error preserved. Migration is not
marked verified, notifications are not suppressed, and customizations are not
changed. Genuine busy/start-observation/timeout retry behavior remains intact.

This confirms an amplification defect. It does **not** identify which validation
fails on this Apple TV, nor prove that this alone eliminates the reported
startup sequence. In particular, no specific missing property, stale file,
incorrect group, tvOS VFS issue or bridge regression is claimed as confirmed.

## Hypotheses

| Hypothesis | Evidence / discriminating test | Status |
| --- | --- | --- |
| H1 repeated preparation | retry policy reproduces six invocations for identical validation failures; remote reload request cycles observed | CONFIRMED in isolated code; device result code unknown |
| H2 repeated wizard | Home calls first_run; process guard exists; no exported FIRST_RUN_FLOW log | NOT DETERMINED on device |
| H3 continually changing inputs | no remote input/hash file read available | NOT DETERMINED |
| H4 incomplete migration persistence | InterfaceReady empty; state JSON unavailable | NOT DETERMINED |
| H5 repeated ReloadSkin | native successful builds reload skin; actual build completion log unavailable | downstream mechanism confirmed, exact count unknown |
| H6 competing builders | Home native build already removed; settings exit remains | possible only; no evidence settings exit runs at startup |
| H7 race | shared preparation lock excludes a second owner in isolated tests | NOT DETERMINED on device |
| H8 bridge | no bridge installation/consent call in layout preparation; no bridge mutation in this fix | no evidence supporting attribution |

## Tests and limits

Baseline: 122 tests PASS. Added one regression test (three failure subcases)
and eight isolated adapter tests. Final suite: **131 tests PASS**.

Adapter scenarios: verified layout reused across five initializations;
pending first build followed by persisted reuse; legitimate applied change
builds once; interrupted build remains pending and can recover; simultaneous
preparation is rejected rather than queued; custom menu is preserved; service
version alone does not force a build; replaced/unverified skin output rebuilds
once. Existing optional-preview tests remain in the suite.

These tests stub the Kodi API, native generator and readiness fixtures. They
are not five real Kodi launches, native Skin Shortcuts integration, a verified
skin hash-cache update, tvOS playback regression or tvOS acceptance. They do
not demonstrate that the actual failing device output is repaired.

## Publication gate and next action

**BLOCKED for Beta publication.** Do not increment/publish a release with only
this guard or overwrite the immutable service 0.4.40 ZIP. Stable, Testing and
all existing packages remain unchanged.

Next evidence needed: a sanitized current-startup log containing
INTERFACE_LAYOUT_OUTPUT, INTERFACE_LAYOUT_UPDATE, SKINSHORTCUTS_BUILD,
WIDGET_EXPANDABLE_PROPERTIES and FIRST_RUN_FLOW. The user asked the agent to
retrieve it if possible; the native authorized download route was denied.
Use a user-supplied export or an already-authorized read mechanism, without
installing tools or changing production security settings.

Then reproduce the exact terminal validation failure using anonymized source /
generated-output fixtures, repair that cause, test no-change cold startups and
legitimate changes, version the service, rebuild reproducibly, open a PR and
publish only Testing after required checks. User performs the eventual update
and restart; trailer and clean-start runtime gates remain mandatory.
