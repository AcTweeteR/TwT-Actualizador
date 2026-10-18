# Kodi Master integration — baseline audit (2026-10-18)

This is a checkpoint before integrating Beta code into the active Kodi Master
profile. No add-on, profile, Stable feed, or device package was changed during
this audit.

## Source and isolation

- Official repository: `AcTweeteR/TwT-Actualizador`.
- GitHub read-only commit search confirmed remote `main` at
  `20524bcc61106260c067ee899ab47a1dac218fbc`, matching this isolated
  worktree's `origin/main` and HEAD.
- Development branch: `codex/master-integration-2026-10-18`.
- `workspace_guard.py --require-branch codex/master-integration-2026-10-18`:
  PASS; clean tree before this report.
- `python3 -m unittest discover -s source/0.4.32/tests -q`: 84 tests PASS
  after adding installer-consent regression coverage.
- Direct `git ls-remote` was unavailable because the shell sandbox could not
  resolve `github.com`; remote verification used the connected GitHub
  read-only commit search instead.
- Stable `repo/` was not edited or published. Apple TV was not accessed.
- A private pre-integration restore point exists. A byte comparison of the
  installed Master skin directory against that checkpoint reported no
  differences.

## Installed Master baseline

| Component | Installed version |
| --- | --- |
| Kodi | 21.3 |
| `skin.actweeter` | 1.2.0 |
| `service.actweeter` | 0.3.8 |
| `plugin.video.xstream-pro` | 1.1.2 |
| `repository.actweeter` | 1.0.3 |
| `pvr.iptvsimple` | 21.11.0 |
| SlyGuy Trailers | 0.2.1 |
| YouTube | 7.4.4 |
| Skin Shortcuts | 2.1.0 |
| `script.trakt` | not installed |

Versions were read from the active Kodi add-on manifests, not inferred from
repository candidates.

## Runtime observations (Master UI)

- **Home/catalog — PASS_RUNTIME (observed screen):** Home rendered Spotlight
  and populated movie rows. It was not an empty-catalog state.
- **Widget DPAD — PASS_RUNTIME (sampled):** Down moved focus from Spotlight
  into the row; Right changed the selected poster and Spotlight metadata.
  Return opened the detail view for the selected row item; no playback action
  was activated.
- **Series recent — PASS_RUNTIME (sampled):** the Series “recently added” row
  was populated and opening a card showed its detail view. Installed
  XStream's `resources/lib/series_changes.py` defines `recent(...)`, and
  `premium_routes.py` dispatches `series_recent` to it. The current log
  contains no `AttributeError` or literal `series_recent` marker. This is not
  a full pagination, season, or episode regression test.
- **TV — PARTIAL:** navigating through the TV menu reached the TV/guide
  surface and channel rows were present. Guide programme information was not
  established as complete; no channel was deliberately played in this audit.
- **Movies/Series category trees, Search latency, PVR channel switching,
  profiles/collections, watched-state sync, and full install wizard —
  NOT_TESTED in this checkpoint.** The previously reported ~60-second search
  delay was not timed here and has no causal attribution.

## Trailer protection gate

Master's active `skin.actweeter/1080i/IncludesBingie.xml` contains the
Spotlight trailer button and an ordered action chain around lines 2364–2380:
clear/cancel preview state, notify `service.actweeter`, set SlyGuy return
context, then invoke `slyguy.trailers` with the selected item's trailer URL;
Kodi `PlayMedia` is the fallback only when SlyGuy is absent. This implementation
must not be replaced wholesale by Beta XML.

The corresponding installed Master service modules
`automatic_preview.py`, `kodi_auto_preview.py`, and
`slyguy_preview_bridge.py` are byte-identical to the current Beta source. The
broader service coordinator and setup files are not identical and remain
unmerged pending a semantic review.

During a previous manual-trailer probe Kodi displayed a SlyGuy proxy startup
error. The sanitized current log contains three `Address already in use`
messages; the earlier read-only port check associated TCP 8095 with the Kodi
process. This does **not** establish whether a trailer can still play, nor does
it establish that AcTweeteR caused the port collision. Therefore:

`MASTER_TRAILERS_REGRESSION=NOT_TESTED (baseline gate unresolved)`

### Follow-up visual check

After returning to Home, two Kodi screenshots 2.5 seconds apart showed
different frames in the Spotlight video area while the selected title remained
`My Nanny Stole My Life`. This is direct runtime evidence that moving Spotlight
preview video was active on Master. It does not establish which launch path
started it, whether the separate manual trailer button completed its flow, or
audio, cancellation, duplicate-playback, and return behavior. Accordingly,
record `MASTER_AUTOMATIC_PREVIEW=PARTIAL_RUNTIME` and keep
`MASTER_TRAILERS_REGRESSION=NOT_TESTED` until those parts are tested
independently. No trailer implementation was changed.

No trailer-related source or installed file was changed. Before integrating
any service/skin change that can touch previews, establish a clean, repeatable
Master manual and automatic preview baseline and resolve/understand the proxy
collision without changing SlyGuy speculatively.

## Selective-integration map

The current source snapshot is Beta (`source/0.4.32/addons/`), not a drop-in
replacement for Master:

- Skin comparison: 307 same-path files byte-identical, 32 differ, 41 are
  Beta-only; no Master-only paths were found.
- Service comparison: 31 same-path files byte-identical, 8 differ, 62 are
  Beta-only, and 7 are Master-only.
- XStream 1.1.2.8 has a verified Beta artifact and modification notices, but
  the upstream source is not vendored in this repository snapshot. Master
  1.1.2 already contains the `series_changes.recent` function and dispatch;
  runtime row evidence gives no reason to replace it for this route.

High-risk changed service surfaces include `service.py`, `setup.py`,
`resources/lib/first_run.py`, and `resources/lib/xstream_setup.py`. Beta adds
many modules (Trakt coordination, profile handling, search diagnostics,
layout migration, preview coordination and metrics); each requires a
consumer/dependency review before copying. Skin files that differ include
Home and video-info XML; those are especially sensitive to the protected
trailer behavior. Beta touch diagnostics and touch-specific hit-test/scroll
experiments are excluded from this integration.

One installer contract needs correction/review before adoption: Beta
`first_run.py` labels `slyguy.trailers` optional in `OPTIONAL_ADDONS` and the
catalog uses a consent-based offer, but also includes `trailer_addon_ready` in
`MANDATORY_SETUP_CHECKS`. `setup.py` then refuses completion while that check
is not `PASS_RUNTIME`. This conflicts with the stated rule that optional
components must not be installed without consent and may make IPTV setup
completion depend on the trailer package. Preserve Master's working trailer
path while resolving this contract; do not solve it by deleting trailer
support.

### Isolated source correction (not installed)

The source now treats the SlyGuy module and its four packages as optional,
consent-gated entries; removes `slyguy.trailers` from the service's mandatory
catalog dependency closure; and moves `trailer_addon_ready` to optional setup
checks. Trailer readiness remains reported, but no longer blocks completion
of the core IPTV/PVR setup. The upstream SlyGuy packages remain sourced from
their own Kodi repository, and the service manifest retains its optional
import. No preview code, skin XML, SlyGuy settings, or Master files were
changed.

Evidence so far: four focused regression tests and the complete 84-test suite
PASS; two independent service-package builds produced the same SHA-256
`f47dad7422c09882b7f2de603e1be29074d113e7c1ee200c9191032e2921c28a`; ZIP CRC
validation passed. This package is a local candidate only: it has not been
installed in Master, added to a repository feed, or released. The change must
still pass a clean-profile consent/install test before distribution.

### Master follow-up: optional-add-on completion gate

Inspection of the actual installed service `0.3.8` found a second, older
gate not present in the current Beta implementation: `slyguy.trailers` was in
`REQUIRED_EXTERNAL_ADDON_MINIMUMS`, and `_mandatory_addons_ready()` separately
required both SlyGuy Trailers and YouTube after checking the core add-ons. This
made the Master wizard's runtime completion status depend on an optional
trailer integration. The separate YouTube dependency remains required by the
current service contract for explicit fallback/search actions; this correction
does not remove it.

I changed only those two installed source conditions: removed SlyGuy from the
required-version map and made the helper return success after the remaining
required add-on/version checks pass. Before writing, both target files were
copied to a private restore point and SHA-256 verified. The patch is limited to
one removed map entry and one removed optional-readiness condition; no settings,
credentials, profile data, preview modules, skin XML, or SlyGuy files changed.
The equivalent behavior is represented in the repository candidate's
`first_run.py` and `module_catalog.py`.

Validation of the installed files: Python AST parse PASS. The installed
`_mandatory_addons_ready()` function was extracted and exercised with stubs:
missing optional SlyGuy did not block completion, while a missing required
core add-on did block it. This verifies the edited function's contract, but
Kodi has not reloaded or invoked that helper in its live Python runtime yet;
therefore `MASTER_SETUP_GATE=PASS_STATIC` and `MASTER_SETUP_GATE_RUNTIME=NOT_TESTED`.
The repository suite now has 85 tests PASS, including a regression contract
that the default readiness gate does not inspect optional add-ons.

## Checkpoint decision

`MASTER_INTEGRATION=PARTIAL` — one selective low-risk Master service-source
  correction is installed; broader feature integration remains pending.
`MASTER_TRAILERS_REGRESSION=NOT_TESTED` — moving Spotlight preview is visibly
active, but the complete manual/automatic lifecycle remains unverified.
`TRAKT_INTEGRATION=PARTIAL` — Beta code exists, Master has no
`script.trakt`, and no account authorization or remote sync was attempted.
`INITIAL_INSTALLER=PARTIAL` — the optional trailer gate is corrected in
installed Master source, but not reloaded in Kodi and no clean profile was run.
`BETA_REPRODUCIBILITY=PARTIAL` — the 84-test suite passes; a complete
cross-component package/feed rebuild was not performed in this checkpoint.
`STABLE_UNCHANGED=PASS` — stable source/feed untouched.
`SECRETS_EXPOSURE=NONE_OBSERVED` — no profile data or log was copied into Git;
  a release-wide secret scan remains a pre-publication gate.

Next integration should proceed in small, non-trailer blocks only after the
trailer baseline is repeatable. Keep the installed Master and the private
restore point unchanged until a concrete source patch is ready for review.

## Follow-up evidence: SlyGuy listener and XStream delta

Read-only inspection of the active Kodi log records SlyGuy's proxy failing to
bind its configured default port `8095` with `Address already in use`. `lsof`
shows that the listener is owned by the active Kodi process. Kodi's own
JSON-RPC listener is on loopback `9090`; its built-in HTTP webserver is disabled
in the active profile. This proves an in-process port collision, but does not
identify which add-on opened the existing socket. No port or proxy setting was
changed. The conflict remains a pre-existing runtime issue pending attribution.

The same live log contains AcTweeteR/SlyGuy preview handoff traces: SlyGuy
reports `decode_rejected` for the received preview notification, while the
AcTweeteR service records some focus notifications as rejected for ownership.
Those entries establish that preview signaling is occurring but do not prove
which component causes a manual trailer failure. The log also records
`unsupported control type 7` during a Home/TV-hub skin load, but the message
does not identify the XML control or establish a trailer regression. Neither
issue was changed as part of the setup-gate correction.

Process identity needs confirmation before additional installed-file writes:
the running executable is under `/Applications/AcTweeteR QA Kodi 21.3 0.4.11/`,
while Kodi maps `special://home` to the standard
`~/Library/Application Support/Kodi/` profile used by the Master add-ons. The
profile is the expected one, but the executable's QA-labelled app path is an
ambiguity; only read-only diagnosis and repository-side work should continue
until the owner confirms this is the authorized Master instance.

The installed XStream manifest is 1.1.2. Its current `series_recent` route
calls `series_changes.recent(...)`, and the runtime-populated series row
confirms that path is present in this build. The 1.1.2.7 package delta is
concrete rather than a version-only upgrade: it adds the `script.trakt.ids`
playback-metadata bridge needed to expose validated movie/episode IDs to the
official `script.trakt` add-on, and adds strict, fail-closed provider-catalog
filtering for personalized Trakt recommendations. The installed build has
neither that bridge module nor the strict recommendation filter/route. These
features require a corresponding XStream update; ordinary catalogs,
`series_recent`, profile refresh, and existing Trakt account routes do not by
themselves justify upgrading. `script.trakt` is not installed in Master, so no
scrobbling or account-history test has been attempted.

The official Beta service manifest already marks `slyguy.trailers` as an
optional Kodi dependency. The installed Master service manifest still declares
it as required even though its Python setup gate was selectively corrected.
The source test suite now checks this manifest contract as well as the setup
gate. Focused test: 6 PASS; complete suite: 86 PASS. The manifest mismatch is
not yet changed on disk because the active executable identity above needs
owner confirmation.
