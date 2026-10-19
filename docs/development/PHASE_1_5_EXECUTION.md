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
