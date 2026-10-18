# Kodi AcTweeteR — phase 1.5 acceptance checkpoint (2026-10-18)

Status: **OPEN / NOT READY TO CLOSE**. These are proposed *functional acceptance gates*, not a claim that the Beta code or the next phase is incomplete by itself. Work on the real **Kodi Master** profile only: the owner explicitly rejected a parallel Kodi QA installation. Do not touch the independent Android Beta Codex worktree.

## Confirmed baseline

- Official branch: `codex/master-integration-2026-10-18`, Master worktree `TwT-Actualizador-master-integration`.
- Code integrated in **the installed Master profile**: skin `1.2.29~beta10`, service `0.4.37`, XStream `1.1.2.8`. The former Master generated Skin Shortcuts data and original credentials/configuration were protected; full rollback path is in `MASTER_INPLACE_INTEGRATION_2026-10-18.md`.
- Current automated suite: **107/107 PASS** on 2026-10-18; proof of code contracts, not proof of live playback or remote/touch interaction.
- The original provider state `series_changes_p1.json` still has 25 active `NUEVA SERIE` events and two `NUEVOS CAPÍTULOS` events, source-linked via `XStream.ChangeStatus`. Visual rendering after update remains **NOT_TESTED**.
- Kodi startup after the upgrade started service and SlyGuy preview bridge without a Python traceback. `GetDirectory - Error getting 1111` is **still reproduced**. Later log samples also show TMDb Helper folder errors and `CCurlFile` connection failures; do not attribute causes without targeted evidence.
- Another Codex process continues Android touch work on a different worktree. Its success is not implied by merging Beta code into Master.

## Acceptance matrix — every mandatory gate must have post-integration runtime evidence

| Area | Required end-to-end acceptance | Current state |
| --- | --- | --- |
| Master UI and user data | Home has populated Spotlight and rows; existing user movie/series shortcuts preserved; no unexpected layout replacement | **PARTIAL**: hashes/semantic settings preserved, post-update visual inspection unavailable |
| Navigation | Five main destinations plus three lower actions reachable via remote; category EXPANDIR opens correct full list; Back/focus reliable | **PARTIAL / NOT_TESTED** after upgrade; Beta9 main destinations sampled on Lenovo, Beta10 bottom navigation only static |
| TV and catalog | PVR guide with program data; tuned channel playback/return; movies and series category flows; search results work | **NOT_TESTED** after integration; historical PVR/movie passes cannot be promoted |
| Movie and series playback | Movie from card/details and episode via season (play/pause/return), without wrong item being selected | **NOT_TESTED** after integration |
| Trailer ownership | Manual Spotlight film and series trailer play/return; details action; automatic-preview start/cancel/audio/no double playback | **PARTIAL**: historical pre-update manual trailer passes, complete lifecycle untested; Android trailer touch failed in prior Beta |
| Widget state | Continue Watching, correct card source, recently added, badges `NUEVA SERIE`/`NUEVOS CAPÍTULOS` visible where applicable | **PARTIAL**: source and data preserved; post-update live UI unverified |
| Persistence and migration | No forced reset, completed wizard does not block existing setup; explicit customization consent; safe rollback and menu regeneration | **PARTIAL**: backup/restore tool, 580-file hashes and tests pass, customization modal awaits explicit choice |
| Runtime regressions | Repeatable clean startup without unexplained blocking navigation faults, plugin exceptions or unintended UI loss | **BLOCKED**: `GetDirectory - Error getting 1111` unresolved |
| Android touch, if in 1.5 device scope | Video info actions including trailer, horizontal/vertical pan, EXPANDIR, Back | **BLOCKED / separate Codex task**; no final on-device passing evidence |
| Release readiness | Reproducible official Master package and update path without replacing user-owned files | **NOT_TESTED**; direct copy is not a distributable release |

## Safe next moves

1. Do **not** click “Aplicar diseño” over customized Master shortcuts without comparing exact files; choose “Conservar” if shown until a non-destructive, consent-aware migration is validated.
2. In the existing Master, collect actual Home/menus/widget evidence. Kodi desktop screen capture from the remote agent failed, so a manual visual report from the owner or another authorized GUI capture path is needed.
3. Exercise the end-to-end Kodi flows above and collect *specific* sanitized log evidence. Do not silently change history or mark watched items just to make a pass.
4. Trace the exact source of 1111 via targeted logging/callback inspection, then correct it with a regression test.
5. Import only the **verified** Android touch fix when the concurrent Codex task finishes; preserve Master-only preview ownership and optional SlyGuy contract.
6. Only after required gates actually pass, document `PHASE_1_5=PASS_RUNTIME` and then begin phase 1.6. Do not treat test count or add-on load as a substitute.

No real Kodi profile changes, releases, or provider accesses were needed to establish this gate.
