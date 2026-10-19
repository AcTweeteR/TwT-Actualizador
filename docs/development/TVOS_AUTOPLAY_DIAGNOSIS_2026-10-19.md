# tvOS automatic previews: missing published skin wiring

## Baseline and safety

Official main: `0fd276e9b94821efa61697dba303ef26287870df`.
Development branch: `codex/tvos-autoplay-skin-wiring`, independent worktree.
Master integration reference: `3efc8f52d0d958305508b1ece7bf622fec712c65`.
Existing worktrees and untracked artifacts were preserved. No installed Kodi
files, settings, profiles, playback commands or window properties were written.
The production Apple TV was queried exclusively through a closed read-method
allowlist. HTTP credentials remained in memory, never in this repository.
No SSH, file-system access, input injection, addon execution or restart was used.

## Read-only runtime evidence

The actual endpoint's `JSONRPC.Introspect` reports `ReadData` for GUI properties,
addon details and XBMC info labels/booleans. Kodi reports 21.3 stable,
JSON-RPC 13.5.0, `System.Platform.TVOS=true`, skin `1.2.29~beta10`, service
`0.4.39`, SlyGuy Trailers `0.2.1`, SlyGuy module `0.87.0`, and Testing repository
`1.0.1`; all queried addons enabled, not broken.

Both `SpotLightTrailers` and `BingieAutoTrailer` are true;
`AutoYoutubeTrailer=true`, `trailersource=youtube`. These values were not changed.

| User-operated test | Observations (UTC, 2026-10-19) | Result |
| --- | --- | --- |
| A: hold Spotlight Spider-Man | 15:22:01–15:22:21, four samples: window Home, focus 1508, position 2, media movie; active players empty and preview owner empty at every sample. User also reports no autoplay. | FAIL_RUNTIME |
| B: hold normal movie row | 15:23:10–15:23:28, three samples: Home, focus/container 13004, position 1, movie Robarme la vida (user identifies My Nanny Stole My Life); active players and preview owner empty at every sample. | FAIL_RUNTIME |
| C: user starts manual trailer | Internal video player 1, speed 1, not live; fullscreen window 12005, title Robarme la vida (Trailer), position 00:41.481 of 01:35. User confirms it is playing. | PASS_RUNTIME (one movie) |

Both tested containers expose non-empty IMDb and TMDb IDs. No DBID is required
when either stable external ID exists. Empty player lists correctly mean no
active player, not an RPC error. Sampling cannot exclude a very short failed
attempt between samples. No authorized log-reading mechanism was available;
internal resolver logs and SlyGuy bridge startup are NOT_OBSERVED on tvOS.

## Demonstrated distribution defect and Mac antecedent

The publicly downloaded Beta10 ZIP SHA-256 is
`4387012a8d6b928dfc665ef4b48a06773149295ca36937ec35e43e728dc2b808`,
identical to the immutable official artifact. Its effective list definitions
`BingieSpotlightWidget` (`IncludesBingie.xml`, approximately 2257–2298) and
`WidgetBaseBingieIncludes` (`IncludesHomeWidgets.xml`, approximately 690–706)
have **no `preview_focus` dispatch**. The old default/Spotlight preview includes
in `IncludesFunctions.xml` explicitly disable focus-start behavior. Definitions
of `Bingie_Trailer_Action` elsewhere do not automatically execute themselves.

Master added the absent visible-list hooks in:

- `43cc0ab458deaea84524e0302bb08cf15fffa8c1`: Spotlight focus/cancel.
- `5f723e1a00cca3dca84a6c25da925adb5f517783`: regular Home row focus/cancel.
- `2ea7661614d25234f6ece106228fa101596ad328`: retain stop tokens and observe
  subsequent row selections; historical sampled Mac transitions are documented
  in `PHASE_1_5_EXECUTION.md` on the integration branch.
- `45b43c14eb9d05ed0483e65385d889890eef0cb2`: shared series/parent-episode
  resolution, series-window exit cancellation.

The later service package carries coordinator changes, but the skin package
was still the immutable Beta10 artifact, preceding those hooks. This is a
confirmed missing link in distribution, not evidence of a tvOS player defect.
The installed skin's bytes cannot be read through addon-version queries; its
reported version matches that artifact, but exact installed XML parity is
not claimed.

## Flow and hypothesis assessment

Expected: actual focused list -> `RunScript(service.actweeter,preview_focus,`
`container,3)` -> setup captures window/focus/position/stable metadata ->
AddonSignals notification -> existing coordinator -> bounded latest-wins delay ->
SlyGuy bridge resolves trailer -> owned windowed playback -> Kodi video window.
Selection changes are observed by the coordinator; cancellation/exit invalidates
the request, and only the exact owned preview may be stopped. Manual detail
buttons use the separate explicit SlyGuy action and therefore can work without
the missing focus hook.

| Hypothesis | Evidence for / against | Discriminating result / confidence |
| --- | --- | --- |
| H1 timer reset | No video/owner observed; timer not directly exposed. Against a timer-only cause: published lists never dispatch the request. | Internal timer state unresolved; missing dispatch confirmed, high confidence. |
| H2 focus | Proper movie controls 1508 and 13004 and IDs observed. | Wrong focus not supported for these samples; high confidence in queried focus, not all navigation. |
| H3 XML activation | Both effective list definitions omit start hooks; settings enabled. | Confirmed source/artifact defect, high confidence. |
| H4 resolver path | Manual uses explicit SlyGuy; automatic needs coordinator request. | Paths differ by design; downstream automatic resolver not exercised, unresolved. |
| H5 invisible playback | No player at seven automatic samples; manual video is visible/fullscreen. | No evidence of hidden active video in sampled intervals; transient failures not excluded. |
| H6 tvOS mechanism | Missing hooks are platform-neutral; manual Kodi/SlyGuy works. | No demonstrated tvOS-specific fault; platform-specific automatic runtime remains untested. |
| H7 omitted historical fix | Exact Mac hook commits absent from shipped ZIP. | Confirmed omission, high confidence; not proof of a new player regression. |
| H8 disabled config | All relevant read settings are enabled. | Disabled-setting hypothesis rejected for this session. |

Official references: [Kodi onfocus semantics](https://kodi.wiki/view/Default_control_tags),
[JSON-RPC](https://kodi.wiki/view/JSON-RPC_API). The connected device's own
introspection is the authority for its 13.5.0 method parameters.

## Minimal correction and validation boundary

Skin candidate `1.2.29~beta11`: restore focus/cancel on those two real controls,
require existing service 0.4.39, and cancel on leaving the series hub. Respect
the individual autoplay switches and existing YouTube/IMDb source selection.
Do not add media-type gates that prevent tracking a row after an unsupported
first card. Do not copy Master-only manual trailer changes or alter resolver,
player, touch, profile, generated shortcuts or settings implementations.

Seven new XML contracts cover the two start hooks, feature/source gates, cancel,
window exit, baseline omission, unchanged manual/navigation actions and service
dependency. Full publication-source suite: 116 PASS_AUTOMATED. Separate existing
Master integration suite: 246 PASS_AUTOMATED, not 362 unique tests. None proves
tvOS playback. Two independent builds produce SHA-256
`173b79ef008bfb3c3c4d37b5db66ae3a8a8fdf611dc78cf0b130effd5b704f07`.

## User-only update and acceptance

When published, use Kodi Testing -> Check for updates -> AcTweeteR skin
`1.2.29~beta11`; retain service 0.4.39. No reinstall, reset, SSH or ZIP required.
The agent must NOT install it or change the production Apple TV.

After updating, repeat A/B/C, hold two different posters in each row, navigate
rapidly, leave Home, and verify normal movie/episode playback is not interrupted.
Also test a title with no trailer. A/B after the correction are
PENDING_USER_TEST, not PASS_RUNTIME. If they fail, observe whether a player or
request appears before considering any second downstream cause.

Rollback: select the retained Beta10 skin version through Kodi's native
repository version selection if needed; no settings need deletion. Historical
ZIPs and service/XStream/repository packages remain unchanged. No rollout or
rollback action was performed on the device by this investigation.
