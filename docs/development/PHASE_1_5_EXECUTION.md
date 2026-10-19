# Phase 1.5 execution — 2026-10-18

Status: IN_PROGRESS. No release or Stable changes authorized here.

## Verified baseline

- Branch `codex/master-integration-2026-10-18`, local and remote
  `20e4234a2eb9f892c33cdd28f30d6ae42f8bf7eb`, clean before work.
- Original `/Applications/Kodi.app`, existing standard profile only.
- Installed skin 1.2.29~beta10, service 0.4.37, XStream 1.1.2.8,
  SlyGuy Trailers 0.2.1, SlyGuy module 0.87.0, IPTV Simple 21.11.0.
- Installed coordinator, ownership module, service entrypoint, Home and
  details includes match branch sources. Generated shortcuts are not replaced.
- 108 automated tests passed. Home visibly has populated movie/series rows.
- Read-only JSON-RPC confirmed Home and no active player before restart.

## Block 1 — displaced preview stop token lifetime

Observed runtime: generation 10 was stopped after a row change at 21:52:12.
New focus generation 13 arrived before its terminal callback at 21:52:13.
The callback had no corresponding OWNERSHIP_RELEASED event. Later requests,
including generation 20 observed during this session, were accepted but never
dispatched despite no active player.

Root cause reproduced in a test: `_focus` pruned the displaced request and
its token because preemption had already cleared `scheduler.active`.
`terminal_by_identity` then could not authenticate cleanup; `stop_inflight`
remained occupied and `_take_ready` blocked all subsequent requests.

Minimal change: preserve generations in `stop_inflight` when pruning. The
existing authenticated terminal path remains responsible for releasing them.
No timeout, unconditional player stop, or new scheduler is introduced.

- Regression test failed before the fix; 109 tests passed after it.
- Matching three-line patch applied to source and installed coordinator.
- Verified private backup: `/private/tmp/actweeter-phase15.ahNNLi/kodi_auto_preview.py`.
- Original SHA-256: `3ee4f22b856ffc89488d1fd3266f989952325899bd60bfaccc1febf3ad864397`.
- Restart used native macOS **Kodi > Quit**, never the skin power menu.
- Post-restart runtime on 2026-10-19: Spotlight started generation 1;
  Continue Watching movie generation 5 started at 07:24:03.643. Moving to
  a card with no resolved trailer stopped it and returned an error without
  another playback; moving onward started generation 9 at 07:24:27.968.
  Changing row accepted generation 12 before generation 9's terminal cleanup;
  cleanup succeeded in 295 ms and generation 12 started at 07:24:39.131.
  This directly exercises the previously blocked callback ordering.

## Block 2 — idle row selection and origin consistency

Kodi emits control focus events on row changes, not every item selection.
The old polling only ran while an automatic preview was active. An episode
or unresolved trailer at the start of a mixed row therefore prevented later
movie previews from being requested. Register every Home row and observe
selection changes while idle using the same worker and inherited delay.
Repeated samples of an unchanged item do not reschedule it.

A captured Spotlight request also showed container 1508 with actual focus
13003. Reject differing container/focus IDs so the provider cannot resolve
Spotlight content while a different row is selected.

- 112 tests pass, including idle transition, no duplicate scheduling,
  external-player protection, invalid origins and displaced-stop cleanup.
- Source/installed files match and Python/XML parse.
- Additional verified backup: `/private/tmp/actweeter-selection.fUYRAF/`.
- Runtime: episode first card → movie starts; unresolved card → next movie
  starts; fast Right/Right/Right/Left/Left resolves only final observed card.
- Movie coverage is sampled, not acceptance of every personalized carousel.
- All remaining phase gates below stay open.

## Remaining sequential gates

1. Repeat consecutive movie previews, rapid changes and row transitions.
2. Series/episode preview identities and cancellation, same coordinator.
3. Manual movie/series fullscreen, stop and context restoration.
4. Continue Watching without changing existing resume/history.
5. All menus/widgets including 20 + EXPANDIR and personalized routes.
6. IPTV/EPG and VOD regression within data-preservation constraints.
7. Stress, final integrity, tests, small commits and integration-branch push.

Do not infer any of these runtime results from unit tests. Do not overwrite
generated XML, profile state, credentials, Stable, or other worktrees.

## Block 3 — series and episode trailer resolution (2026-10-19)

The existing bridge rejected all media except movie, and the coordinator's
surface allowlist omitted the real Series hub window 11110. Source and
Master now support movie/tvshow/season/episode through the same scheduler.
`read_preview_metadata` is shared by the focus dispatcher and row observer.
Episode/season lookup uses only the parent TV show database ID or explicit
parent metadata. XStream premium cards preserve series `tmdb_id`/`imdb_id`
properties before changing the card's media type to episode: this contract
was verified in installed `premium_routes.py` listitem and continue routes.
Unidentified parent data produces no results; episode IDs never become show
or movie lookup IDs. No third-party add-on files were changed.

The first runtime attempt exposed an existing provider-dispatch bug: SlyGuy
returned an IMDb plugin route and the bridge passed its `tt…` identifier to
the YouTube extractor. Kodi logged `youtube:truncated_id`. `preview_target`
now distinguishes native IMDb and YouTube routes. IMDb uses SlyGuy's own
`IMDB.get_best` and TrailerItem/headers without its shared `imdb.m3u8` file.

After that change, the episode's parent (A la deriva) completed resolution
with `no_stream` / `no_results` at 07:31:24, without a playback or wrong ID.
This is valid absence of an available trailer, not a successful-series-video
claim. Further known-title playback is PENDING.

- 119 automated tests pass; includes parent-ID boundaries, tvshow types,
  Series hub admission and IMDb/YouTube route separation.
- Backups: `/private/tmp/actweeter-series.dmBBky/` and
  `/private/tmp/actweeter-series-hub.hsPFma/`, per-file cmp verified.
- Master changes remain local and source-backed; no Stable/Beta publication.
- Kodi exits have logged `Application stopped`; no force quit/system shutdown.

Series runtime confirmed after restart: window 11110 / Spotlight tvshow
Ted Lasso, generation 4, AVStarted 07:34:34.762, actual video visible.
Down to Continue Watching and Right selected Medusa S01E01; generation 4
was released in 380 ms; parent-series trailer generation 7 AVStarted at
07:35:16.153, actual Medusa/Netflix trailer visible behind its episode card.
No episode or VOD was played. No claim of testing every series/category.

## Block 4 — manual playback and returning Home (in progress)

Movie detail control 54 was verified before selecting. Baseline's immediate
Action(FullScreen) closed the detail before asynchronous SlyGuy captured the
ListItem: no player and no capture event. Removing that action allowed the
same Spider-Man trailer to play, but behind the detail. Moving presentation
to the captured AVStarted event produced actual fullscreen video at 07:46:17
(window 12005, no detail text). Back stopped it, but the return identity
check failed because Home's focused menu differs from its underlying row.
The source-container recovery change remains awaiting the next runtime check.

Home reload also repeatedly prompts to replace customized layout when the
generated-output fingerprint changes. A declined prompt now suppresses only
automatic prompts during this Kodi session; explicit repair still proceeds.
It does not mark migration complete, change the persisted wizard state or
write generated/user shortcuts. Installed and source setup.py match; this
session-only decline needs runtime confirmation after restart.

Backups for this block: `/private/tmp/actweeter-manual.8IMw1l/`, per-file cmp
verified. 124 automated tests pass at this checkpoint. No publication.

## Remote Desktop Commander handoff — 2026-10-19 08:30

- Recovered Codex's three local commits and all nine pending source/test/doc paths without resetting or overwriting them.
- `python3 -m unittest discover -s source/0.4.32/tests -q`: 126 tests PASS.
- Python AST parse and both modified skin XML parses PASS; `git diff --check` PASS.
- All five pending installed Master service/skin files byte-match their source counterparts.
- Kodi Master running on Home with no active player at inspection. No restart, playback, resume/history changes or UI navigation performed in this handoff.
- PVR logs show 1,293 channels, 46 groups, 764 EPG channels and 180,419 EPG entries loaded; this is not proof of successful live playback or all routes.
- Manual fullscreen and return-to-detail source/test code exists, but the latest source-container recovery remains **runtime unverified**. Manual series detail, resume/history, 20 + EXPANDIR menus, all widgets, IPTV playback and prolonged stress are **NOT YET PASS**.
- Phase verdict: `FASE_1_5_INCOMPLETE`. Do not tag/release/merge to Stable.

## Deep-audit checkpoint — 2026-10-19

Scope inspected: integrated commit history, installed/source parity, coordinator ownership and focus/cancel/exit paths, manual trailer capture/return gates, migration state, Kodi logs, unit/integration contracts, and IPTV/EPG loading. This is a **checkpoint, not an exhaustive function-by-function runtime certification**.

- 580-file integration verification PASS, generated skin shortcuts preserved.
- 128 automated tests PASS; Python/XML checks from prior checkpoint PASS.
- Confirmed bug: an idle row retained `focus_context` after an on-unfocus with no pending request; Home exit also retained the row/refocus marker. This could re-arm a trailer from a stale selection. Fix clears only the matching row on accepted cancel, and clears both row/refocus state on Home exit. Two targeted regressions added.
- Kodi log: local QA repositories `127.0.0.1:8765` and `127.0.0.1:18765` have failed connection attempts. These are disabled/offline local test feeds; do not remove or alter without determining whether the user still needs them.
- Kodi log: recurring `GetDirectory` errors for TMDb Helper's `log_tagger`, `log_library`, `timer_report` paths. Their exact root cause is not established; avoid deleting its addon_data.
- IPTV Simple loads 1293 channels, 46 groups, 764 EPG channels and 180419 entries; actual stream playback, guide navigation and VOD are not verified by this evidence.
- Manual trailer fullscreen, series detail restore, resume/history, personalized navigation, all widgets, stress and cross-device restore remain unverified at this checkpoint. `FASE_1_5_INCOMPLETE`.

## Follow-up focus-state audit — 2026-10-19

- Found a second idle-observer bug: `_focus` stored `focus_context` before validating media type and stable identity. Invalid folders/placeholders could remain eligible for idle polling. Fixed by retaining only fully validated preview rows and clearing context for rejected content. Added regression test.
- Full suite: 129 PASS; `git diff --check` PASS.
- No claims of exhaustive runtime validation; outstanding manual-return/stream/navigation/stress checks remain.

## Notification decoder audit — 2026-10-19

- Both AcTweeteR and SlyGuy JSONRPC notification decoders used `base64.b64decode(..., validate=True)` but did not catch `binascii.Error` for malformed Base64. A malformed signal could raise into Kodi's monitor callback rather than fail closed. Added `binascii.Error` handling to both bridges and a focused regression test.
- Full suite: 130 PASS; diff validation PASS. This is defensive correctness, not proof of exhaustive Kodi runtime coverage.

## Playback handoff audit — 2026-10-19

- Confirmed state-lifecycle bug: `_preempt` and `external_playback_started` cancelled active previews but retained `focus_context` and `refocus_after_stop`. When manual trailer or VOD playback ended, the idle-row observer could re-arm an old automatic trailer without a new focus event.
- Fixed both handoff paths to discard idle focus and refocus markers before preempting; exact owned-item stop protection remains unchanged.
- Added regression tests for manual detail preemption and external VOD start. Full suite: 132 PASS; `git diff --check` PASS.
- Runtime manual return, IPTV/VOD playback, resume/history, navigation and extended stability remain unverified. Do not close 1.5 on automated tests alone.

## Resolution failure audit — 2026-10-19

- Confirmed coordinator bug: `_work` called `_resolved` for `launch_error` without `request_id`, but `_resolved` requires the exact token. Consequently a `run_script` exception could leave `scheduler.resolving` occupied and prevent later automatic previews.
- Fixed local failure notification to include the exact current generation request token; added regression verifying resolution slot release.
- Full suite: 133 PASS; `git diff --check` PASS. No manual trailer/EPG/VOD/runtime navigation certification implied.

## AVStarted transient-label audit — 2026-10-19

- Confirmed uncaught `ValueError` risk in `KodiAutoPreviewCoordinator.av_started`: transient non-numeric Kodi focus/current-item labels were parsed directly with `int` in the Player callback. An exception could interrupt the owned-preview lifecycle during window changes.
- Treat invalid numeric labels as stale focus (`-1`), preserving exact token ownership and stale-preview rejection. Added a regression for malformed `System.CurrentControlId`.
- Full suite: 134 PASS; no syntax/diff errors. Runtime detail restoration, IPTV and user-data flows remain unverified.

## Carousel consecutive-card transition audit — 2026-10-19

- Confirmed real control-flow bug: `_work` assigned `refocus_after_stop = active` immediately before `_preempt`, which cleared `refocus_after_stop` by design. The prior preview stopped on selection change, but the replacement card could not be rearmed by the worker.
- Moved deferred refocus assignment after `_preempt` only in the internal card-change path, keeping manual/VOD handoff cancellation intact.
- Added deterministic worker regression confirming the old card is passed to `_refocus_current_card`; 135 automated tests PASS. Real visual carousel transition still requires runtime validation.

## Cross-window stale cancellation audit — 2026-10-19

- Confirmed idle-focus cleanup checked only `container` when no preview request remained. A late on-unfocus from another window using the same control ID could erase the currently tracked row.
- Require matching `window` and `container` for idle cancellation; preserve active request cancellation rules. Added regression for cross-window stale callback and same-window cleanup.
- Full suite: 136 PASS. Real UI navigation and manual trailers remain unverified.

## Manual trailer detail-return identity audit — 2026-10-19

- Confirmed premature abandon: `return_decision` treated temporarily empty ListItem identities on detail/list windows as definitive mismatch, potentially losing manual trailer detail restoration during Kodi window transitions.
- Wait on empty identity (bounded by existing 8-second caller deadline); abandon only an observed different identity. Added regression for detail and all supported list windows.
- Full suite: 137 PASS. Manual trailer fullscreen and return require visual runtime QA before closing 1.5.

## Preview manifest deletion safety audit — 2026-10-19

- Confirmed overly broad prefix-based deletion allowed malformed/traversal-like `PreviewManifest` strings to reach VFS deletion.
- Restricted cleanup to the exact `special://temp/actweeter_preview_<safe-token>.mpd` naming convention emitted by the SlyGuy preview bridge. Rejected traversal, suffix and alternate-extension cases; valid MPD cleanup retained.
- Full suite: 138 PASS. No unrelated Kodi user data was modified.

## SlyGuy provider identity validation audit — 2026-10-19

- Provider `_identity` previously coerced non-string values to text; e.g. `None` became `None` as a string and passed `.isalnum()`, admitting an invalid candidate identity.
- Reject missing/non-string and non-ASCII identifiers while retaining valid Kodi IDs. Added regression for malformed and valid inputs; 139 PASS.
- Real runtime provider resolution and playback still require functional verification.

## AcTweeteR coordinator identity validation audit — 2026-10-19

- Coordinator `stable_identity` had the same non-string coercion issue fixed earlier in the SlyGuy provider. Both endpoints must reject malformed identities consistently.
- Require nonempty ASCII alphanumeric string identifiers; add regression for missing/numeric/bool/Unicode malformed values and valid TMDb text.
- Full suite: 140 PASS. Functional playback remains pending.

## SlyGuy incoming request token audit — 2026-10-19

- Confirmed the provider interpolated an unvalidated notification `request_id` into a temporary MPD path. Previous cleanup guard protected deletion but not creation.
- Reject request IDs unless they match the coordinator's exact UUID-hex plus positive generation format before enqueue/resolution; add regression for traversal and malformed tokens.
- Full suite: 141 PASS. Functional playback and catalogue remain pending.

## Interface rollback symlink safety audit — 2026-10-19

- `apply_layout` rejects symlinks, but `rollback_layout` did not preflight its destinations or backup sources. This could allow following a symlink during rollback.
- Added all-target preflight for safe names and symlinks, including state and backup metadata. Regression confirms an outside file is unchanged.
- Full suite: 142 PASS. Did not accept the user's pending interface-layout consent dialog or modify live shortcut layout.

## Missing layout rollback manifest audit — 2026-10-19

- Confirmed `rollback_layout` treated missing backup-manifest file entries as `exists=False`, risking deletion of existing shortcuts during a rollback with a missing/corrupt manifest.
- Preflight all expected entries and required integrity fields before any shortcut mutation. Added regression asserting current shortcuts survive a missing manifest; updated symlink test with a valid manifest.
- Full suite: 143 PASS. Live catalogue layout remains untouched; user consent not granted.

## Layout rollback partial-restore audit — 2026-10-19

- Rollback verified each backup payload only immediately before writing it. A corrupt later payload could leave earlier shortcuts already restored.
- Preflight and hash-verify all backup payloads, including previous state, before the first mutation. Added two-file regression with a corrupt second payload proving both current files survive.
- Full suite: 144 PASS. Live catalogue layout and consent remain unchanged.

## Layout rollback previous-state manifest audit — 2026-10-19

- The rollback manifest preflight omitted `previous-state.json`, permitting a missing entry to be interpreted as absent and deleting the current layout state.
- Require an explicit previous-state entry and test fail-closed preservation of the existing state file.
- Full suite: 145 PASS. Live catalogue layout and consent remain unchanged.

## Layout rollback mid-write failure audit — 2026-10-19

- Even after verifying all backup payloads, a later filesystem write failure could leave earlier shortcuts partially restored.
- Snapshot original target bytes, and on rollback write failure restore already touched paths in reverse order. Regression injects a one-time failure on the second shortcut and verifies both original shortcuts and layout state remain intact.
- Full suite: 146 PASS. This is best-effort recovery from a recoverable I/O failure, not a power-loss transaction.

## Manual trailer return focus race — 2026-10-19

- `_restore_context` called SetFocus and immediately Action(Info), without verifying Kodi had processed the asynchronous focus change. This could open information for the wrong item.
- Gate Action(Info) on the original window, confirmed focused control and exact captured item identity, with bounded wait; fail closed when focus cannot be confirmed. AST regression checks guard precedes Action(Info).
- Full suite: 147 PASS. Real movie/series return UI playback remains to be verified.

## Layout rollback deleted-shortcut preservation — 2026-10-19

- A shortcut missing after layout application was not compared against its expected managed hash; rollback could silently recreate a shortcut the user deliberately removed.
- Treat a missing expected managed file (and a non-file target) as a conflict and return without changing shortcuts or state. Regression checks missing shortcut remains absent and state bytes unchanged.
- Full suite: 148 PASS. Live catalogue consent remains unchanged.

## Layout apply state and backup symlink preflight — 2026-10-19

- `apply_layout` guarded shortcut symlinks but did not reject a symlinked state file or `interface_backups` root before reading/writing backups.
- Reject both linked paths before preparing any layout mutation. Regression covers each symlink and verifies the external target and shortcuts remain unchanged.
- Full suite: 149 PASS. User layout consent remains unchanged.

## Section audit: layout apply, backup and rollback — 2026-10-19

Scope: reviewed `apply_layout`, `rollback_layout`, `backup_interface`, backup manifest and state write paths as a single workflow; no user-consent dialog was accepted.

- `apply_layout`: snapshot and restore previous layout state if a state write/readback raises after modifying the file; existing shortcut undo remains in place. Regression injects a post-write failure and checks both state and shortcuts.
- `rollback_layout`: reject a symlinked backup root before loading any manifest. Regression checks no external files change.
- `backup_interface`: reject symlinked backup root and report destination before creating pre-update snapshots. Regression checks both entry points.
- All 152 automated tests PASS; source syntax and diff checks clean. The full Kodi visual/functional flows and power-loss consistency are separate, still-open QA gates.

## Manual trailer lifecycle: return-path audit — 2026-10-19

Reviewed capture, fullscreen handoff, owned stop, terminal gating, marker cleanup and return to detail/spotlight. Two additional unsafe Info-action paths were found:

- Missing/unknown source control or source window could still reach Action(Info) without verified control focus. Refuse restoration without a known source control from the exact current list window.
- Request or selected identity could change between focus confirmation and Action(Info). Recheck request ownership, window, focus and stable identity immediately before opening the detail.

153 automated tests PASS, including AST guard regression. Runtime manual trailer/movie/series Back tests remain pending; do not claim functional certification until reproduced on Kodi.

## Preview provider/coordinator manifest cleanup audit — 2026-10-19

Reviewed provider request validation, preview resolution, player handoff, manifest cleanup, and coordinator stale callbacks.

- Coordinator `_cleanup_stale` previously deleted the item's advertised manifest before verifying identity/token ownership; a stale callback could remove another generation's valid MPD. Validate request ID format, known generation token and identity, and exact expected manifest name *before* deletion.
- Provider `_resolve` cleanup ran in `finally` without protecting VFS translation/existence/deletion exceptions, which could suppress status and terminate the provider worker. Log cleanup failure by exception type and allow worker to continue.
- 156 automated tests PASS, including stale cross-request and mismatched-identity cases, plus structural guard for provider cleanup. Full playback runtime and VFS failure-injection integration still pending.

## Preview selection/cancel/provider parent identity audit — 2026-10-19

Reviewed the focus notification -> scheduler offer -> cancel/unfocus -> SlyGuy episode/season parent trailer lookup path as one workflow.

- Pending/active preview `_cancel` accepted a late cancel from another window with the same container ID; now rejects mismatched windows and checks both window and container when clearing idle focus context.
- SlyGuy `preview_source` accepted malformed parent imdb/tmdb values (including non-string and Unicode numeric values) and invalid parent dbid. Require ASCII alphanumeric string IDs and positive decimal dbid before resolving a series parent; do not substitute episode ID.
- 158 automated tests PASS, including cross-window pending cancel and malformed episode-parent identity. Real GUI carousel/episode preview remains a runtime QA gate.

## Layout rollback: state, manifest and per-file hash audit — 2026-10-19

Reviewed the complete rollback authorization chain (state read, backup location, manifest, names, owned hash, restoration).

- Reject linked `interface_layout_state.json` before reading it, and refuse malformed `files` state.
- Validate all state-derived backup filenames before any backup-file reads.
- The prior fallback `state.files[name] or state.properties_hash` could authorize overwriting an unrelated customized shortcut if its content happened to match the properties hash. Restrict `properties_hash` exclusively to `skin.actweeter.properties`; all other shortcuts require their own exact expected digest.
- 161 automated tests PASS, including symlinked state, traversal in state filenames and incorrect cross-file hash authorization. Full Kodi GUI consent/restore remains pending.

## Layout apply-backup-rollback complete isolated round trip — 2026-10-19

Audited the whole apply/backup/rollback path with a real temporary filesystem (not the Kodi Master profile):

- Apply preflights every shortcut destination, refusing existing directories/non-files before writing any other shortcut. This avoids partially mutated layouts when a later target is a directory.
- Apply validates extra snapshot names, refusing traversal, nested paths and collisions with managed/reserved backup entries. No external path can be selected as backup output via the snapshot key.
- New isolated end-to-end test applies the real skin shortcut documents, verifies a backup is produced, rolls back, and asserts exact original state bytes and no leftover managed shortcuts.
- 164 automated tests PASS; live GUI consent, Skin Shortcuts build and provider playback are separate remaining gates.

## Interface preparation concurrency/lock lifecycle audit — 2026-10-19

Reviewed lock acquisition, stale-owner recovery, preparation callback, and release as a single concurrency path.

- Previously stale-lock recovery recursively reentered `prepare_interface` with no retry bound under lock contention. It now retries acquisition at most once and returns PREPARATION_BUSY when another owner persists.
- Previously the finalizer unlinked any file at the lock path, even if another process had replaced it while preparation ran. The finalizer now compares device/inode identity with its own open descriptor and refuses to remove another owner's lock or a symlink.
- 166 automated tests PASS, including lock replacement during preparation and bounded stale-lock recovery. Multi-process Kodi runtime contention remains a separate QA gate.

## Skin Shortcuts property persistence and state recovery — 2026-10-19

Audited the second-stage widget identity -> property merge -> backup -> write -> state update -> recovery flow.

- Refuse symlinked property, state and backup-root paths before reading/writing; reject directory at the property file destination.
- Snapshot previous state bytes before writing. On a post-write state failure, restore properties only when they still match our written bytes and restore state only when it still contains our exact properties hash and backup marker. This prevents stale state pointing to rolled-back property data without clobbering unrelated concurrent changes.
- 168 tests PASS, including linked destinations and simulated failure after the state file was written. Native Skin Shortcuts GUI rebuild remains unverified.

## XStream Spanish metadata preferences/cache audit — 2026-10-19

Reviewed the full default-language migration: current settings, metadata migration marker, cache discovery, backup, settings persistence, cache invalidation, and rollback.

- Reject linked metadata report and backup root before migration, avoiding writes outside the service profile.
- Validate and snapshot every Spanish premium metadata cache file before creating backups or changing settings; refuse symlinks and nonregular files, preventing late discovery after settings mutation.
- Restore deleted cache entries from the preflight snapshot on a recoverable failure.
- 170 tests PASS, including linked report/backup and linked cache files; actual XStream remote metadata refresh remains a runtime gate.

## XStream metadata migration transactional recovery and concurrent cache refresh — 2026-10-19

Reviewed the complete setting writes -> cache invalidation -> migration report commit -> exception recovery path.

- Keep a byte-for-byte pre-migration report snapshot. If report write raises after writing, restore it only when it still matches this migration's report bytes.
- Before each cache invalidation, confirm its current bytes still equal the verified backup snapshot. Refuse deletion of cache refreshed concurrently by another process.
- Track changed settings and actually removed cache entries, and restore only those entries; avoid clobbering a newly created replacement cache during rollback.
- 172 tests PASS, including simulated postwrite report failure and concurrent cache replacement. Kodi remote metadata response remains unverified.

## Manual SlyGuy trailer return workflow — 2026-10-19

Reviewed VIDEO_INFO manual launch, terminal callback, list focus recovery, Spotlight restoration, and marker cleanup as one lifecycle.

- Kodi often starts playback while DialogVideoInfo (12003) is active, so no originating list control is captured. The earlier fail-closed source-control requirement could prevent reopening the detail from Home/Movies Hub. A missing control can now be recovered only from the currently focused control of an approved list window, with an exact per-container identity match; the final Action(Info) still requires current request, window, focus and identity checks.
- During asynchronous Spotlight refocus and detail reopen waits, revalidate the original request to avoid completing a superseded trailer request.
- Treat Home request markers as armed only for literal `1`, not any nonempty value.
- 174 tests PASS. Tests include structural assertions for focus/identity/request guards; full manual trailer playback and actual GUI restoration are still NOT verified.

## Manual trailer identity and presentation transition — 2026-10-19

Reviewed the complete identity parsing/matching, explicit request, video-info dismissal, fullscreen activation and owned stop flow.

- Accept only ASCII alphanumeric provider IDs and positive canonical decimal DBIDs in typed trailer return identities; reject malformed/Unicode/control identifiers and non-string observed identities.
- Revalidate both current request and active video after closing the information dialog and before activating fullscreen, preventing a superseded request from driving the GUI.
- 176 tests PASS, including malformed identity cases and a simulated request invalidated during presentation. Actual Kodi GUI playback remains a runtime QA gate.

## XStream background search refresh lifecycle — 2026-10-19

Reviewed scheduler gate, dispatch, pending provider sync observation, stale request recovery, and retry pacing.

- Initial `RefreshGate.last_request=0` incorrectly suppressed first dispatch until one full interval of clock uptime. A never-requested gate now uses `None` and permits the first due request immediately (subject to coordinator's initial provider bootstrap grace period).
- A dispatched refresh without a later `last_successful_sync` update previously stayed pending indefinitely. After two refresh intervals, the coordinator marks it unobserved, clears pending and returns to normal refresh gate decisions. It does not infer successful sync or change provider credentials.
- 179 tests PASS, including scheduler behavioral tests and pending lifecycle structural contract. Provider real sync remains an integration gate.

## XStream provider SQLite sync marker read — 2026-10-19

Audited the index timestamp path through SQLite open, scalar extraction and refresh_due decision.

- Refuse symlink/nonregular index paths and use read-only SQLite URI without resolving a linked path. No provider data mutation.
- Treat nonfinite SQLite timestamps (`NaN`, infinities) as absent; reject nonfinite inputs in refresh_due rather than producing unstable scheduling decisions.
- 181 tests PASS, including real temporary SQLite databases and linked index paths. Concurrent index rebuild/runtime sync remains unverified.

## XStream real index verification and clock-skew recovery — 2026-10-19

Read-only verification of installed Kodi Master XStream SQLite index: `PRAGMA quick_check` returned `ok`, with 12,934 movie rows and 5,070 series rows; movie/series/filter/schema and last successful sync metadata exist. This proves a readable local index, not a completed fresh provider refresh. The installed provider exposes `search_sync`.

Reviewed timestamp handling through due-check and request cooldown for system-clock corrections:

- Provider timestamps more than five minutes in the future now trigger a refresh rather than blocking until the clock catches up. Small clock differences remain tolerated.
- An in-memory request timestamp more than five minutes ahead of the current clock no longer blocks the scheduler indefinitely after a backwards clock adjustment.
- 183 automated tests PASS. A real live sync and UI search are still pending; no provider mutation was performed during read-only verification.

## XStream active-profile isolation and refresh URL — 2026-10-19

Audited the end-to-end active profile setting -> numeric profile -> provider SQLite filename -> plugin refresh URL path. Invalid `Profile 999` and malformed names previously silently fell back to profile 1, risking a wrong-profile refresh. The conversion now accepts only the canonical `Profile 1`–`Profile 10` labels (case-insensitive), with an empty setting still defaulting to Profile 1. The SQLite marker reader and refresh URL both require a real integer 1–10; no coercion of strings/bools/floats. Invalid profiles fail closed and are logged by the existing coordinator exception handling. Kodi Master currently uses Profile 1.

185 tests PASS including active-profile, SQLite selection, and refresh URL boundaries. Real multi-profile switching and provider refresh remain runtime QA gates.

## SearchWorker two-provider snapshot transaction — 2026-10-19

Audited standalone service search worker -> snapshot provider -> `reconcile` -> SQLite meta commit. Previously movie changes committed before series snapshot was obtained, so a series failure could leave a partially updated index. The worker now collects both complete snapshots before opening one SQLite write transaction, reconciles both under caller-owned transaction, and commits the success marker with both media types. Cancellation and reconciliation errors roll back all writes. `reconcile` retains standalone transaction behavior by default but can join a verified caller-owned transaction.

191 tests PASS including six real SQLite transaction scenarios. **Scope:** this worker currently has no caller in the installed service; the actual XStream provider implements its own `_ensure_search_index` transaction and is not modified by this change. Do not claim runtime provider synchronization was tested.

## Installed XStream `_ensure_search_index` defensive provider snapshot guards — 2026-10-19

Audited the active provider's SQLite open, snapshot extraction, empty-snapshot protection, and patch reproducibility. Three issues corrected in `actweeter-runtime.patch`: (1) an empty snapshot was rejected only if filter stamp was unchanged, allowing deletion of all existing titles after a filter change; now always refuse an empty snapshot when previous titles exist; (2) non-dictionary provider records previously caused incidental exceptions; now fail explicitly before reconciliation; (3) refuse symlink/nonregular index paths before opening SQLite. Updated manifest patch and runtime provider hashes to match the intended patched bytes. Added three tests validating patch hunk count, manifest hash, syntax and guard presence. 194 tests PASS. Live provider refresh not executed; source deployment requires a Kodi-idle restart and backup.

## XStream release reproducibility and immutable published ZIP — 2026-10-19

Verified exact SHA-256 mismatch: historical testing ZIP `1.1.2.8` contains original `premium_routes.py` (`7b34d01d…`), installed Kodi Master has the guarded provider (`4986a744…`), and the development manifest now hashes the guarded provider. Historical ZIP restored unchanged, SHA-256 `f1a305719b8b8bc5e5e0b99c66331af5ad153fdd15829b25947ba1fe97ad9382`. Added builder guard refusing to overwrite an existing ZIP carrying the same version, plus two tests. The source release is not yet rebuilt: new distribution version, pinned upstream release ZIP, channel index and release manifest updates are required. Do not change the historical 1.1.2.8 ZIP or stable channel.

196 tests PASS. Full 580-file runtime verification currently reports source/runtime divergence for the two service search worker/store files (not deployed) and XStream provider (installed code ahead of historical ZIP). This is a known release-consistency gate, not proof of runtime failure.

## Reproducible XStream 1.1.2.9 candidate and isolated testing feed — 2026-10-19

Fetched the pinned upstream XStream 1.1.2 release from the locked upstream URL and verified SHA-256 `915f45708670d07e789bb73b7390a7b5cf30175f818ef5da8ea18c9f13f537fe`. Bumped **development distribution manifest only** from 1.1.2.8 to 1.1.2.9, recomputed the expected addon.xml SHA-256, and generated the corrected XStream package twice into independent staging directories. Both builds yielded SHA-256 `4b127c59b182126824772776c710e72881e08d67852f8b5c9c626ee56e7736d3`. Builder verified the patched runtime hashes, Python syntax, ZIP CRC, attribution and route contracts.

Built an **isolated temporary Testing feed** containing repository 1.0.0, service 0.4.37, skin beta10, XStream 1.1.2.9. XML versions, checksum and copied ZIP hash passed. Did not publish the feed, overwrite the historical 1.1.2.8 ZIP, modify stable or install 1.1.2.9 into Kodi Master. New candidate manifest records the staging location and remaining runtime gates. Existing Kodi Master still has installed XStream 1.1.2.8 with surgical provider fixes; its version is not falsely advanced.

## XStream search filters and local query fail-closed audit — 2026-10-19

Continued complete provider search workflow review. `_search_filter_stamp` previously silently substituted `()` when hidden-category/hidden-item preferences could not be read, risking an incorrect stamp and index reconciliation under incomplete user preferences. Now propagates the error so refresh fails before modifying SQLite. Local search query now refuses a symlink at the index path instead of following it. Added structural and executable filter-stamp tests, including stable stamps for reordered values and exception propagation. Revised the **unpublished** 1.1.2.9 candidate twice with matching SHA-256 `544586b086756437d37f5ab18fad9e55f1769bd17fa7fa28a5fbd61c0324a423`; supersedes earlier staged candidate `4b127c59…`, which was never published. 199 tests PASS. Live search GUI and provider sync remain unverified.

## XStream live index builder transactional SQLite tests — 2026-10-19

Extracted the actual patched `_ensure_search_index` function and executed it against isolated temporary SQLite databases, with mocked provider credentials and catalogs. Added four behavioral integration tests: movie+series commit, second-provider failure preserves prior data, source cache changing mid-catalog rejects stale snapshot, and forced provider refresh permits the expected cache timestamp change. Fixed non-forced refresh stamp mismatch so a concurrent cache update cannot be attributed to older catalog rows. No real credentials or provider index changed during these tests. 203 tests PASS. Rebuilt unpublished 1.1.2.9 candidate SHA-256 `551aec6d4b98306bc63925d6d10e0b8bc66bdac11cb4b14f9ff6720a8a6f2fe1`, replacing prior staged candidate. Real provider refresh and GUI search still pending.

## Mandatory managed-addon update policy — 2026-10-19

User explicitly requested automatic add-on updates disabled in Kodi Master and mandatory behavior for installations from our repository. Applied Kodi JSON-RPC `Settings.SetSettingValue` (`general.addonupdates=1`, notification-only), confirmed readback. Added `addon_update_policy.py` to the managed service startup: it reads current setting, switches to notification-only when necessary, verifies readback, and logs failures without crashing playback. This applies to installations that actually install/enable/start `service.actweeter`, not merely installing the repository ZIP: Kodi repositories cannot directly enforce global host settings. The user can still manually change the setting, which the service reasserts on next startup. Four unit tests; 207 PASS. This setting applies to all Kodi add-ons, not just AcTweeteR. Existing notifications remain enabled.

## XStream release builder: end-to-end transactional audit (2026-10-19)

Audited the entire verified-upstream -> patch -> syntax -> ZIP -> integrity -> publish pipeline. Found and fixed (1) overwrite of an existing output containing a different addon version, (2) truncation/partial output on post-write validation failure, (3) race between two publishers overwriting one target, (4) untrusted ZIP entries outside the expected addon prefix silently ignored, (5) duplicate upstream ZIP paths accepted, and (6) unsafe ZIP member types / symlink patch targets not explicitly rejected. The builder now stages in the target directory, verifies the candidate before atomic no-clobber hard-link publication, removes temporary artifacts on failure, and validates archive entries. The historical 1.1.2.8 ZIP remains immutable. New 1.1.2.9 candidate built with the hardened tool is byte-for-byte reproducible, SHA-256 `551aec6d4b98306bc63925d6d10e0b8bc66bdac11cb4b14f9ff6720a8a6f2fe1`. 213 tests PASS. No Kodi Master changes and no repository publication.

## Testing feed builder — full distribution-path audit (2026-10-19)

Reviewed repository source/identity and feed endpoints, service/skin/XStream input ZIP identity and CRC, bootstrap ZIP, copied package paths, `addons.xml` and checksum, staging, failure recovery, and Stable isolation. Corrected: direct writes could leave a partial testing feed; an existing feed could be silently overwritten; unexpected/duplicate ZIP entries and special file types could pass identity checks; repository-source symlinks could be followed into the published bootstrap. Now validates inputs before writing, builds in a temporary sibling tree, renames the complete tree to a previously absent output, rejects existing outputs and unsafe input members, and cleans staging on failure. Added three regression tests for overwrite rejection, malicious input and simulated write failure; suite **216 PASS**. Historical `docs/testing` and Stable untouched; no Kodi Master deployment. Limitation: plain `os.rename` on Unix is not an atomic no-clobber operation if another process races to create an empty output directory; do not run concurrent publishers to the same output path. Production publication still needs a dedicated lock/no-replace primitive and release-channel QA.

## Test-channel atomic publication race closure (2026-10-19)

Follow-up audit of the full staged test-channel publishing path found the prior `os.rename(stage, output)` could replace an empty destination directory created by a concurrent process. On macOS, publication now uses Darwin `renamex_np` with `RENAME_EXCL`, preserving the completed staging directory until a no-replace atomic publish succeeds. Explicitly fail closed on unsupported platforms; no implicit non-atomic fallback. Added tests for empty-directory collision, symlink collision and successful complete-directory publication. **219 automated tests PASS**. No changes to Kodi Master or historical Beta/Stable artifacts. Follow-up: implement/test equivalent atomic publishing for Android/Linux build hosts before claiming cross-platform builder support.

## Repository bootstrap package: complete builder audit (2026-10-19)

Audited the `repository.actweeter` ZIP build end-to-end: source identity, source tree inclusion, reproducibility, ZIP integrity, destination preservation, and publication. Corrected direct overwrite/truncation of existing outputs, partial ZIP exposure on failure, and symlink inclusion from source trees. Build now stages beside destination, validates CRC and embedded addon identity, then publishes with atomic create-if-absent hard-link; staging is removed on all paths. Added three subprocess regression tests for reproducibility, existing output and symlink destination. **222 tests PASS**. No Kodi Master changes and no release published. Overall phase 1.5 remains OPEN until live acceptance gates are satisfied.

## Skin and service ZIP builders audit (2026-10-19)

Audited both addon package creation paths end-to-end: deterministic ZIP entries, source-tree safety, skin Skin Shortcuts bootstrap replacement, metadata identity, output collisions, and partial-build failure cleanup. Replaced direct overwrite with a shared staged ZIP builder that checks source symlinks, validates ZIP CRC and embedded addon identity, and atomically creates output without replacing existing files. Updated reproducibility test to compare independent output paths instead of requiring an unsafe overwrite. **222 automated tests PASS**. Kodi Master unchanged. More dedicated fault-injection tests and live deployment acceptance remain outstanding.
