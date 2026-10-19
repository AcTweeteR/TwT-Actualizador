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

## Kodi JSON-RPC runtime probe and remote-access interruption (2026-10-18)

This session reached Kodi Master on TCP `127.0.0.1:9090`; Kodi's
JSON-RPC **uses a raw JSON reply without a mandatory final newline**.
`GUI.GetProperties` reported `skin.actweeter` and window 10100
(Yes/No dialog) with the focused button **Conservar**, so the active
post-upgrade customization-consent question was verified rather than
inferred from log text. `PVR.GetProperties` reported
`available=true, scanning=false, recording=false` (PVR subsystem
ready only; no channel-playback claim). `Player.GetActivePlayers`
returned an empty list at the snapshot.

The existing focused **Conservar** option was selected through
`Input.Select` to prevent destructive replacement of user-owned
shortcuts. Kodi then displayed another Yes/No dialog with focused
**Ahora no**. `Input.ExecuteAction(action=screenshot)` opened the
file browser (window 10126), apparently because Kodi's screenshot
folder setting is empty. That unintended file chooser was closed
using `Input.Back`, returning to the Yes/No dialog. The screenshot
was **not** captured or attached, and the later state of the
**Ahora no** dialog cannot be confirmed after remote access failed.
Never claim the optional offer was dismissed.

After these bounded actions, **Desktop Commander stopped responding**,
including a ping that eventually timed out. The Mac's last known Kodi
process was `49085`; its current process/UI state is unknown until
remote access is recovered. Do not retry non-idempotent UI actions
without querying `GUI.GetProperties` first. No profile reset, addon
reinstall, provider playback, background scheduling or QA clone was
performed.

**Result:** the menu-customization protection gate has direct
`PASS_RUNTIME` evidence for the *declined overwrite path only*.
Power-menu migration, Home/widget visual acceptance, playback,
trailers, touch gestures and the `1111` diagnosis remain
`NOT_TESTED/BLOCKED`. Phase 1.5 remains **OPEN**.

For a repeatable Kodi UI probe, use a raw JSON-RPC request
terminated by `\\r\\n` to localhost:9090 and parse a complete JSON
object (do not wait for an output newline). Never print IPTV URLs
or settings. To diagnose the `1111` log, capture the caller
and surrounding Kodi log context; do not treat a bare
`GetDirectory - Error getting 1111` as proof of a particular
malformed menu or plugin route.


## Control de actualizaciones (19-10-2026)

Política de Kodi Master **notificar sin instalar** (`general.addonupdates=1`) confirmada por JSON-RPC y en el log del servicio tras reinicio. El servicio vuelve a aplicar esta política al arrancar; instalar solo el repositorio no puede imponerla. El control completo de versiones, integridad, compatibilidad, avisos y rollback sigue **PENDIENTE**. Ver [hoja de ruta de actualizaciones](UPDATE_CONTROL_ROADMAP.md). La validación de distribución nueva y las pruebas de regresión de Kodi Master siguen abiertas.

## Requisito adicional de actualizaciones selectivas (19-10-2026)

El propietario exige **actualización automática de las versiones propias publicadas y testadas por AcTweeteR**, manteniendo los addons de terceros en modo manual. El ajuste actual `general.addonupdates=1` protege de actualizaciones no supervisadas pero también impide las propias: es una **solución provisional**, no el objetivo final. Se añade como gate P0 un actualizador selectivo con manifiesto propio verificable, lista de paquetes permitidos, backup, validación de plataforma y rollback. El repositorio agrega feeds externos, por lo que pertenecer a `repository.actweeter` no basta como criterio de confianza. Ver [roadmap](UPDATE_CONTROL_ROADMAP.md).
