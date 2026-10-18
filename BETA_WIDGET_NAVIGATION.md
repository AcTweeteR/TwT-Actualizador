# Widget-navigation Beta

Base: official main a890e627dd1254ff51f412f7144ccde2ad814d51.
Only `/docs/testing/` announces the Beta skin. The stable `/repo/` and
`/docs/repo/` feeds and their artifacts must remain unchanged.
Service 0.4.33 and the verified layout-v12 migration remain unchanged.

## Evidence before the Beta skin

Lenovo TB330FU, Kodi 21.3, skin 1.2.28:

- Active XML identifies recent movies as fixedlist 6042, horizontal,
  width 100%, height 341, widgetExpandable=true, provider recent route,
  actweeter_expand=1 and limit=20. No provider credentials were collected.
- D-pad down changes rows; right advances selection and eventually changes
  the visible recent-movies page. Therefore the container is not globally
  disabled and is not limited to the initially visible posters.
- Horizontal ADB drags at y=850 did not advance as intended. Some returned
  to the first visible page. This observation alone does not identify the
  receiving control, event or complete cause.
- Taps on two different posters opened their corresponding information
  dialogs; diagnostics reported source 6042 and positions 1 and 2.
- The screen-fixed focus border remained at the first poster even when
  right-arrow selection changed. It conflicts with movement=7.

## Source-confirmed defects addressed

Kodi's `CGUIBaseContainer::OnClick` runs matching XML onclick actions instead
of the provider's default folder action. AcTweeteR diagnostic onclick actions
match while diagnostics are enabled, including on the EXPANDIR folder, but
the media-specific Action(info) does not. The Beta adds explicit native
Videos-window navigation to the folder's existing provider path. No new
provider route is constructed.

The native focused poster layout now draws its own border. The stale
screen-fixed overlay is removed from the shared Home/hub surface. The
poster, actions, IDs, movement and media data remain unchanged.

The optional existing diagnostics show live counts/cursor and current
control in Home, Movies and Series. Labels and images are noninteractive;
no raw gestures, hit-test receiver, titles or paths are claimed/recorded.

Engine references (Kodi 21.3-Omega):
- `xbmc/guilib/GUIBaseContainer.cpp`: OnClick, OnMouseEvent.
- `xbmc/guilib/GUIFixedListContainer.cpp`: GetCursorRange, SelectItemFromPoint.
- `xbmc/guilib/GUIControlGroupList.cpp`: SendMouseEvent, IsControlOnScreen.
- `xbmc/guilib/GUIWindow.cpp`: OnMouseAction and exclusive mouse routing.

## Acceptance still required

### Beta1 runtime observations and Beta2 correction

The native test-repository install of skin 1.2.29~beta1 succeeded. The live
recent-movies counter showed count=20 and its final item was a movie. A rightward
touch drag from that confirmed endpoint changed CurrentItem 20 -> 16 and changed
the rendered posters. Therefore horizontal touch does process on this row;
leftward attempts at its final boundary cannot advance. Repeated movie artwork
and the stale first-slot frame obscured the earlier visual diagnosis.

There is a separate source-level defect in the expansion branch:
`String.IsEqual($PARAM[widgetExpandable],true)` becomes `String.IsEqual(true,true)`.
Kodi 21.3 `CGUIInfoManager::TranslateSingleString` translates its first argument
as an InfoLabel (SYSTEM_ALWAYS_TRUE here), whereas string evaluation reads it
as an image/label. This is not literal boolean equality and chooses the ordinary
limit-20 branch. Beta2 normalizes generated flags to true/false and evaluates
the include parameter directly, with a false default for non-generated callers.
The migration and the four-field property format are unchanged.

Beta2 was rejected by Skin Shortcuts 2.0.3 at runtime: its optional property was
absent from the expression evaluator's names for some default rows, raising
simpleeval.NameNotDefined. Beta3 uses the generator's native ordered property
fallback: take the existing tagged property first, otherwise the literal false.
This avoids Python evaluation entirely. The installed get_properties method is
tested locally against missing, empty, false and true fixtures using
`tools/verify_skinshortcuts_template.py`; no device profile is used in this test.
Beta2 is not a recommended or accepted build.

Install this version through repository.actweeter.testing only. Record live
counts and positions before/during/after a horizontal gesture, compare D-pad
navigation, reach item 21 where a route actually has more than 20 matches,
tap EXPANDIR, verify complete-category navigation and Back. Repeat on more
than one row. No stable promotion until the functional gate passes.

Rollback uses Kodi's native Versions selector and the unchanged stable
repository packages. Do not restore or overwrite profile files for a skin
rollback. The pre-existing restricted Lenovo backup remains available.

## Beta3 device validation — 2026-10-17

Status: PARTIAL; **not approved for stable promotion**.

Installed through Kodi's native Testing-repository update, not a local ZIP.
Installed manifest reports skin 1.2.29~beta3. Read-only comparisons of
IncludesBingie.xml, IncludesHomeWidgets.xml and shortcuts/template.xml match
the general versioned source byte-for-byte. Service 0.4.33 is unchanged.
Skin ZIP SHA-256:
`0234e3a354d2d84def0843dac5075205f7b7fdb16cebed8cf42b33184dea7787`.
Rebuild and public download match this hash.

### Observed results (ADB touch injection, 1920 × 1200 landscape)

| Check | Result | Evidence without personal catalog identifiers |
| --- | --- | --- |
| Recent movies 6042 | PASS_RUNTIME | Counter becomes 21; LastPage selects 21/21, cursor 7; final folder label is red EXPANDIR. |
| Recent-movies expansion | PASS_RUNTIME | Tap (1870,850) opens provider poster grid; Back returns to 6042, item 21/21. |
| Movie premieres 6046 | PASS_RUNTIME | Red EXPANDIR at last position; same tap opens grid headed with the original premiere year. Back restores the row. |
| Series premieres 6056 | PASS_RUNTIME | Red EXPANDIR; touch opens series grid headed with the original premiere year; Back returns to row. Exact series item count not exposed by current overlay. |
| Horizontal pan | PASS_RUNTIME, sampled rows only | Recent movies previously measured 20 → 16 → 20. Beta3 movie and series premiere rows visibly shift with (350,850) → (1050,850), 800 ms; reverse drag returns to EXPANDIR. Not a claim that every widget/style is verified. |
| Poster selection | PASS_RUNTIME, sampled items only | Series row 6056 second visible poster opens its own sheet; source=6056, position=1, same-spotlight=no. Previous two movie-poster tests also matched their sheets. |
| Vertical pan from row | FAIL | (1000,900) → (1000,400), 850 ms leaves series row 6056 and vertical item=5/cursor=8 unchanged. Arrow navigation changes rows. |
| Trailer touch | FAIL, pre-existing issue | Tap (340,897) leaves snapshot at action=info and focus=7011; no trailer invocation. |
| Trailer remote action | PASS_RUNTIME, one series trailer | Down/Down focuses control 54; OK records action=trailer/source=54 and video visibly plays. Stopped normally after observation. |
| Autoplay / collections / new-series badges | NOT_TESTED | Do not infer their runtime status from this widget test. |

Local screenshots are retained on the diagnostic Mac, not uploaded with this
report. They contain provider artwork and are not general-purpose fixtures.
Relevant basenames: `actweeter-beta3-expand-end`, `expand-open`,
`expanded-loaded`, `expand-back`, `premiere-end`, `premiere-open`,
`series-premiere`, `series-expanded`, `series-pan-away2`, `series-pan-end2`,
`series-vertical`, `series-info`, `trailer-tap`, `trailer-focus`,
`trailer-ok`, `trailer-result` (all prefixed `actweeter-beta3-`, PNG).

The active generated XML has 20 true expansion parameters. The log records
layout-v12 verified (home=6, movies=10, series=10) at 17:30:06, but an older
concurrent retry worker subsequently reports identity BUILD_NOT_CONFIRMED.
Thus the observed successful generation is not a claim that all background
confirmation/retry behavior is resolved. No migration code was changed here.

### Vertical scrolling: bounded diagnosis, not a speculative fix

`IncludesHomeBingie.xml` places group 77777 at top=564 and includes
`Fixed_Focus_Bottom`, whose bottom=-100000 overrides the normal viewport.
Rows are moved with `Fixed_Focus_Navigation` animations based on focus.
This is not equivalent to the native grouplist scroll offset.

Kodi 21.3-Omega `CGUIControlGroupList::SendMouseEvent` (378–413) offers
events to children first. `CGUIBaseContainer::OnMouseEvent` (758–796)
advertises the horizontal axis and captures pan for a horizontal row.
The parent's pan handler (group-list 557–561) clamps against total size
minus viewport size; the oversized viewport removes a useful overflow range.
These are source-confirmed obstacles consistent with the reproduced failure;
the actual gesture receiver is not exposed by the diagnostic XML overlay.

References:
- https://github.com/xbmc/xbmc/blob/21.3-Omega/xbmc/guilib/GUIControlGroupList.cpp#L378-L413
- https://github.com/xbmc/xbmc/blob/21.3-Omega/xbmc/guilib/GUIControlGroupList.cpp#L557-L561
- https://github.com/xbmc/xbmc/blob/21.3-Omega/xbmc/guilib/GUIBaseContainer.cpp#L758-L796

Do not remove just the oversized bottom while retaining focus-driven row
translations: that would combine two scrolling coordinate systems and needs
its own controlled comparison. Do not claim that changing movement or adding
a scrollbar fixes vertical axis arbitration in nested containers. The next
repair must reconcile native bounded scrolling, row animations and Spotlight
hit area, preserving remote navigation. The Beta3 fix deliberately does not
invent an XML gesture callback or modify Kodi's engine/keymaps.

The final EXPANDIR tile is partially clipped at the right edge (cursor 7) but
was reachable and tappable in all three expansion tests. Full tile visibility
remains a layout issue; it is not reported as visually complete.

Automated validation: 41 unit tests PASS plus 12 cases using the installed
Skin Shortcuts 2.0.3 get_properties implementation. XML/CRC and reproducible
ZIP checks PASS. These do not replace device interaction. Stable feeds and
bootstrap remain byte-for-byte unchanged; no stable tag/release was created.

## Beta4 candidate — native Home vertical-scroll prototype, 2026-10-17

Base: branch `codex/beta-widget-horizontal-navigation`, commit `d15d365`.
Candidate skin is `1.2.29~beta4`; service remains `0.4.33`. This is a
Beta-only source/package candidate and is not runtime accepted.

### Diagnosis and source change

Kodi 21.3 Omega engine source confirms that
`CGUIControlGroupList::OnMouseEvent` changes the scroll offset by the
container's own orientation and clamps it to `m_totalSize - Size()`;
`CGUIControlGroupList::SendMouseEvent` visits children first and only then
offers an unhandled gesture to the group itself. See the 21.3-Omega source
references below. In AcTweeteR Home, the parent `grouplist` is anchored at
`top=564` while `Fixed_Focus_Bottom` expands its viewport to `-100000` and its
rows are separately translated by `Fixed_Focus_Navigation`. This is
consistent with two observed defects: no useful vertical overflow to scroll,
and no parent hit area for a gesture starting above y=564. Runtime cannot
identify the exact receiving control through the existing skin diagnostic
overlay, so hit-test interception remains an inference, not a claimed event
trace.

The Beta4 source experiment is limited to Home:

- `HomeVerticalScrollViewport` gives the Home parent and page-control a
  bounded full-screen viewport; hub windows keep their existing bounds.
- A transparent 564px spacer is inserted before the Spotlight focus proxy to
  preserve the prior vertical origin of visible rows.
- Home uses native vertical grouplist movement rather than legacy row
  translation animations; hub animations and Home wrap fades remain.
- Horizontal fixedlists, movement=7, item actions, focus navigation and
  Spotlight layout remain unchanged in source.

This is a technically motivated experiment, not a confirmed fix. In
particular, whether Kodi lets an empty spacer fall through to the underlying
Spotlight click target must be checked at runtime.

### Current Lenovo availability and candidate checks

ADB confirms the authorized Lenovo TB330FU and Kodi foreground. Installed
manifests still report skin `1.2.29~beta3` and service `0.4.33`. After more
than five minutes of 15-second observations, visible Home remains in its
empty-state; the Home diagnostic reports the sampled recent-movies widget
count as zero. One native navigation to Películas also leaves an empty
provider state and a zero-item Continue row. Thus there are no visible rows
to scroll or posters to tap; vertical/horizontal runtime acceptance,
detail-button tests and EXPANDIR interaction are NOT_TESTED in this session.
This records the observed state after the requested wait and does not assume
earlier catalog tests were invalid.

Kodi logs in the same interval show layout-update workers repeatedly
encountering `PREPARATION_BUSY`, repeated Skin Shortcuts builds/Home reloads,
and `Trying to add unsupported control type 7`. The latter is not yet tied to
the gesture defect. The repeated layout activity is a concrete concurrent
build symptom; its trigger and ownership are still under investigation. No
locks, caches or profile data were changed.

Automated validation on source: 46 tests PASS, including a new structural
contract for the bounded Home viewport, preserved spacer geometry, Hub
compatibility and no Home row-translation animation. Deterministic local
Beta4 skin/service/test-feed artifacts build successfully. These checks are
not runtime proof. The candidate feed has not been published or installed;
Stable and Kodi Master remain untouched.

Kodi 21.3 source references:
- [CGUIControlGroupList.cpp — SendMouseEvent and orientation-bounded pan](https://raw.githubusercontent.com/xbmc/xbmc/21.3-Omega/xbmc/guilib/GUIControlGroupList.cpp)
- [GUIBaseContainer.cpp — container gesture handling](https://raw.githubusercontent.com/xbmc/xbmc/21.3-Omega/xbmc/guilib/GUIBaseContainer.cpp)

Runtime gates still open: Home vertical pan from Spotlight and rows;
horizontal pan and remote navigation after the viewport change; widget taps;
EXPANDIR clipping/reachability; detail touch buttons; automatic trailers;
series badges; collections/profile isolation; Skin Shortcuts race. No Stable
promotion is permitted on these results.
## Beta5 candidate — responsive Home viewport and current Lenovo follow-up, 2026-10-17

Base branch: `codex/beta-widget-horizontal-navigation`, base commit
`0753a117d8b7db656771a5dc3fe76c20eef271f7`. Installed Lenovo remains on
skin `1.2.29~beta4` and service `0.4.34`; no package was installed during
this follow-up.

### Confirmed evidence

- Kodi is foreground on the authorized Lenovo test device.
- The current Home render showed Spotlight artwork/actions but no materialized
  widget rows; the diagnostics label reported the vertical container as
  `item=-1`, with the recent-movies count blank. We waited through successive
  15- and 30-second checks. This is a current observation, not a conclusion
  that the provider has no catalogue; the five-minute delayed-load gate was
  not exhausted in this follow-up.
- On a content details sheet, a tap at `(310,906)` over the visible
  “Reproducir Tráiler” control left the screen and diagnostic action unchanged
  after four seconds. This confirms the touch failure for that control in this
  observed state, but does not identify whether the click missed the control
  or a later action failed. Do not change the trailer route based on this alone.
- Earlier runtime testing on this same installed Beta generation did reach the
  21st EXPANDIR folder and opened its provider category. The last tile was
  visibly clipped at the right edge; category return worked. That evidence
  applies to the tested widget(s), not every row/profile.
- The installed service manifest reads `0.4.34`; the installed skin manifest
  reads `1.2.29~beta4`. Recent log reads show no new
  `INTERFACE_LAYOUT_UPDATE`/`SKINSHORTCUTS_BUILD` entries after the prior
  build burst around 22:13. An XStream `search_sync` request took 60,019 ms
  at 22:53 and completed; no causal link to missing Home rows is established.

### Kodi input model and bounded correction

In Kodi 21.3 Omega, `CGUIControlGroup::SendMouseEvent` checks children in
reverse render order and returns as soon as one child handles/focuses the
event. `CGUIBaseContainer::OnMouseEvent` advertises pan support according to
its orientation and pans only that axis. This makes a horizontal child
carousel a plausible reason a vertical swipe begun on its card does not reach
the Home vertical parent; it is consistent with the observed runtime failure,
but the skin diagnostics do not expose the actual event receiver. No
`movement`-only or overlay workaround is claimed to fix this arbitration.

The independently demonstrated right-edge clipping has a concrete source
correlate: Home grouplist `77777` used a fixed width of 2070 while the Lenovo
Kodi viewport is 1920 pixels wide. The Beta5 candidate changes only this Home
viewport width to `100%`, adds a regression assertion, and advances the skin
package from `1.2.29~beta4` to `1.2.29~beta5`. It does not change widget routes,
limits, card actions, control types, or focus. This is structurally justified
but still requires package-on-device visual/runtime confirmation.

Kodi engine references (21.3-Omega):
- [GUIBaseContainer.cpp: gesture direction and pan](https://github.com/xbmc/xbmc/blob/21.3-Omega/xbmc/guilib/GUIBaseContainer.cpp#L3523-L3603)
- [GUIControlGroup.cpp: child-first reverse hit testing](https://github.com/xbmc/xbmc/blob/21.3-Omega/xbmc/guilib/GUIControlGroup.cpp#L1886-L1933)

Automated suite: 47 PASS; skin XML parse: PASS; Beta5 skin ZIP built with
CRC PASS, SHA-256 `26f04ee5ea58777ddd7e6f8d8229b2a4fd72a1033078ec217c1b17f19ca1a965`.
No runtime result has been recorded for Beta5 yet. Vertical pan from a widget,
trailer touch, autoplay, badges, collections/profile separation and the
remaining concurrent Skin Shortcuts conditions stay open. Stable feed,
Kodi Master Mac and Apple TV remain untouched.
## Beta5 candidate — coalesce repeated Skin Shortcuts migration triggers, 2026-10-17

Candidate service `0.4.34`; skin remains `1.2.29~beta4` and is byte-identical
to the Beta4 package. This change is limited to the Beta feed; the Stable
`repo/` tree is not modified.

### New runtime evidence

After Beta4 had been installed through Kodi's Testing repository and Home had
been observed for over five minutes, ADB-readable Kodi logs showed repeated
Home.xml loads roughly every 6–15 seconds. Home.xml invokes both the native
Skin Shortcuts build and `service.actweeter,first_run`; the latter logs
`session_claimed` and then still enters the pending layout-migration path.
Across those reloads the service repeatedly requested a Skin Shortcuts build
and logged `PREPARATION_BUSY` / `BUILD_NOT_CONFIRMED`. This establishes a
repeated-trigger/rebuild loop in the service's per-session suppression, but
does not establish that it is the cause of Home's empty provider widgets.
Home remained in its empty state, and no poster targets were visible. The
unrelated `Trying to add unsupported control type 7` log line remains
unattributed.

### Candidate change and guardrails

`_run_pending_interface_migration` already performs a bounded retry sequence.
Previously it cleared its window marker after `GENERATED` and after retryable
deferred outcomes, allowing every Skin Shortcuts-triggered Home reload to
start another worker. Service 0.4.34 now marks the migration attempt for the
current Kodi session after either a verified success or a bounded deferred
result. An explicit repair action still clears that session marker first; a
new Kodi session may retry deferred work. This avoids deleting locks, caches,
or profile state and does not change the established four-field widget
property migration.

The service package was built reproducibly (SHA-256
`08ab9a8ec4f4756a7364de5ccbce255272ba2f68c646e978faacac96e3df41f2`); the
unchanged Beta4 skin package hash remains
`3e3aef0ba5c8ce544fa733639c4bdbbf35987a02976db4c005d8d53e2cef8283`.
Automated service/source tests: 47 PASS. This is not device validation of
the loop fix.

### Runtime status and next gate

The Beta4 Home viewport change has not yet received a meaningful scroll or
poster-selection test on this run because Home exposed zero visible items.
Horizontal/vertical touch, widget tap identity, EXPANDIR, detail buttons,
trailers, badges, and collections remain NOT_TESTED in the Beta4 runtime
state. Do not treat this service-only Beta5 as validation of those functions.
Publish only to the separate Testing feed, update the Lenovo through Kodi's
native Beta repository, then observe whether repeated Home/build events stop
and whether the user catalog/widgets materialize. If they do not, continue
diagnosing the independent content-loading issue without clearing profile
data or weakening the remaining runtime gates. Stable remains unchanged.

## Beta6 candidate — correct Home viewport geometry, 2026-10-18

Base commit: `3ed2447c7b8a781359099b46fa5c8281aee49b67`. Active source is
the clean Beta worktree; no archive/admin checkout was used. Lenovo ADB is
connected through its authorized mDNS serial, with Kodi foreground. Installed
manifests observed before this candidate: skin `1.2.29~beta5`, service
`0.4.34`.

### Runtime observations before the source change

- Home initially rendered Spotlight before the rows. After waiting for the
  rows to materialize, real widget rows appeared; an initially sparse screen
  is therefore not evidence that the provider has no catalogue.
- With rows visible, vertical swipe from Spotlight and a long vertical swipe
  initiated within a poster row produced no visible vertical movement in the
  captured before/after screens. These are sampled `FAIL_RUNTIME` observations.
- Two horizontal swipe attempts within the visible row did not produce a
  visually measurable change in this follow-up. Earlier Beta3 tests moved
  cards on selected rows; horizontal behavior is consequently inconsistent
  across observed runs and is not declared fixed or globally broken.
- Dragging the native vertical scrollbar moved its thumb and changed the
  visible content. The viewport is scrollable by page control; this does not
  prove touch-pan works.
- A sampled poster tap previously opened the corresponding information sheet.
  This does not generalize to all widgets or resolve the touch-button issue.
- The overlay's recent-movies diagnostics still refer to container `6042`,
  while the current sampled widget source was `13003`. The overlay also asks
  `Container(77777)` for state although `77777` is the parent grouplist. Those
  fields are not reliable event-receiver telemetry; Kodi skin XML does not
  expose the hit-tested receiver ID for arbitrary touch motion.

### Confirmed geometry cause and minimal source correction

The Home grouplist `77777` and page-control `317` each declared a literal
`<top>564</top>` before including `HomeVerticalScrollViewport`, whose `<top>`
is zero. In Kodi 21.3's `CGUIControlFactory::GetPosition`, geometry is read
with `FirstChildElement("top")`; the first expanded value wins, so the Home
viewport remained anchored at 564 rather than starting over Spotlight. This
is a source-confirmed geometry defect matching the failed upper-screen pan.
The candidate removes the unconditional geometry children and selects one
mutually exclusive viewport include: top=0 for Home, top=564 for hub windows.
The grouplist's existing transparent spacer preserves row layout. No widget
routes, action logic, focus behavior, or profile data are changed.

Kodi source reference (21.3-Omega), `GUIControlFactory.cpp`,
`GetPosition` / `GetDimensions`:
https://github.com/xbmc/xbmc/blob/21.3-Omega/xbmc/guilib/GUIControlFactory.cpp#L186-L195

The automated regression test now rejects literal geometry before either
viewport include on both controls and checks the Home/hub branches. The
deterministic Beta6 skin ZIP was rebuilt twice with matching SHA-256
`a94845d87ff9aa33c05340a6578de1e8c53b41af9e539e03cfdf1fc8ed42835b` and
passes ZIP CRC. The locally generated Testing index SHA-256 is
`5b64c22618f6622e897d0da83d6b002b70d6a34b47257124255bcdb68099de37`, MD5
`23de2ce6ce751d0ce51651228080cd13`; the stable `/repo/` tree remains
unchanged. The Beta6 feed is prepared locally, not yet publicly deployed or
installed. Android runtime acceptance is pending installation from
`repository.actweeter.testing`. Do not promote to Stable until
Spotlight-origin and row-origin vertical pan, horizontal navigation, remote
navigation, and separate functional gates are rechecked on Lenovo.

### Lenovo Beta6 follow-up — deployment and runtime observations, 2026-10-18

Correction to the preceding preparation status: the Beta6 Testing feed was
subsequently deployed, and Kodi installed it using the native repository
updater. The official merge commit is `af8f095a3b441ed2729642654f35636f4600a6e2`.
Public Beta index and ZIP hashes were verified against the locally generated
artifacts; Stable was not changed.

Installed Kodi 21.3 process PID 32140 was foreground on the authorized Lenovo
TB330FU; the skin manifest reported `1.2.29~beta6`. Home first showed Spotlight
without materialized rows. After waiting/navigation, Spotlight, Continue
Watching and additional movie rows appeared; the recent-movies diagnostic
reported 21 items. The initial blank state was transient in this run, not
evidence that the provider had no catalogue. Its exact delay/root trigger is
still undetermined.

The first Home parse in the available log had four invalid Skin Shortcuts
include warnings and `GetDirectory - Error getting include` at 00:34:18; these
did not recur in later sampled Home loads. `Trying to add unsupported control
type 7` recurred, but its origin and relation to Home/touch remain unattributed.
No causal link between the earlier Skin Shortcuts busy/build events and the
delayed rows was established.

| Lenovo interaction | Result | Evidence |
| --- | --- | --- |
| Tap second poster in Continue Watching | PASS_RUNTIME, sampled | Overlay source `6041`, position `1`, `same-spotlight=no`; the opened detail matched the tapped poster while Spotlight differed. |
| Tap a poster in the long recent-movies row | PASS_RUNTIME, sampled | Overlay source `6042`, position `1`, `same-spotlight=no`; the opened information sheet matched that poster, not Spotlight. |
| Horizontal swipe on recent-movies row | PASS_RUNTIME, one row/sample | Diagnostic item changed `1 → 7` with count `21` and the rendered row advanced. Vertical parent also changed row, so clean axis isolation is not proven. |
| Vertical swipe from a widget poster | PASS_RUNTIME, one traversal sample | Without opening a detail, parent diagnostic changed `item=3/cursor=4 → item=2/cursor=2` and the preceding row entered the viewport. This is not proof of smooth/continuous scrolling or all start regions. |
| Vertical swipe from Spotlight | PARTIAL / NOT_ACCEPTED | Parent state changed toward the first row while Spotlight focus/artwork changed; this does not isolate native vertical pan or prove intuitive direction. |
| Touch “Reproducir tráiler” in a detail sheet | FAIL_RUNTIME, one attempt | Tap around `(300,860)` left the sheet and action diagnostic unchanged after four seconds; no trailer playback occurred. The active receiver is not exposed by the current overlay. |
| Reproducir / Continuar | NOT_TESTED | Not activated, to avoid mutating playback progress/history. |

The current overlay reports XML action source ID, focus before/after, container
position and a boolean Spotlight comparison when a card onclick runs. It cannot
identify the hit-tested receiver for arbitrary touch motion or prove which
control received a missed tap. Kodi skin XML has no supported generic callback
for raw touch/hit-test telemetry; do not infer receiver identity from focus.

Home/catalog is now visibly available after deferred loading. Sampled poster
taps resolve independently from Spotlight; horizontal motion works on at least
one long row; vertical traversal has one successful sample but needs
direction/axis-isolation checks; trailer touch remains a runtime failure.
EXPANDIR across rows, badges, collections, profile isolation, autoplay and
remote regression gates were not newly validated. No device files were edited,
no playback started and no provider-artwork screenshots were added to Git.
Stable remains unchanged; do not promote Beta6 based on these partial results.

### Beta7 preparation — Skin Shortcuts single ownership and trailer touch, 2026-10-18

The active Lenovo manifests now report skin `1.2.29~beta6` and service
`0.4.34`. The `UseBingieInfoDialog` setting is true, so the active detail
layout is `BingieInfo`, not `BingieAltInfo`. Runtime screenshot bounds for the
visible trailer radiobutton were approximately x=139–689, y=948–1028 for a
1920×1200 capture; the source tree confirms it is nested in three vertical
grouplists (`IncludesDialogVideoInfo.xml`, include `BingieInfo`, inner control
8000). The box inherits 550×72. One ADB touchscreen tap within that visible
box did not change the action snapshot or start playback, while a remote OK on
control 54 did invoke the shared trailer action and the test trailer played.
A second tap with focus moved to another detail control likewise did not focus
or activate trailer. This confirms a touch-dispatch/hit-region failure in the
active layout, but Kodi's skin layer exposes no hit-tested receiver ID; the
exact intercepting control/coordinate transform remains undetermined. No
trailer command or radiobutton type was changed. Any playback started here was
the explicit short trailer validation and was stopped immediately; user VOD
state was not touched.

The independent log sample from 2026-10-17 shows a no-change preparation
sequence: the first native build finished with `output_changed=false`,
property persistence reported `changed=false`, and the code nevertheless
requested another build. This log was collected while an earlier Beta skin was
installed, so it is historical evidence, not a Beta6 runtime confirmation.
Source inspection also found an uncoordinated Skin Shortcuts build in Home.xml
alongside the service's preparation/migration coordinator. The Beta7 source
candidate removes that competing Home invocation; the service now reuses an
already verified current XML/property store, skips the second build only when
the first generated output is already complete, logs correlated build phase
IDs, and treats `PREPARATION_BUSY` as a coalesced outcome instead of queuing a
second preparation. A later read-only ADB log sample from the installed Beta6
runtime contains repeated `INTERFACE_LAYOUT_UPDATE` starts on distinct Kodi
script threads within the same short window. Multiple workers reach
`PREPARATION_BUSY`, while the active worker reports two native builds with
`output_changed=false` and Home reloads between them. This supports two
separate defects: a direct Skin-Shortcuts Home onload competing with the
service, and a check-then-set session marker that was not an atomic claim. It
does not prove every trigger origin or establish that the long provider query
caused Home delay.

Beta7 now atomically claims the migration session before reading state or
requesting a native build. The existing profile preparation lock remains in
place. This change is static/unit-tested but not installed on Lenovo yet.

The 60.053-second `service.search_refresh` completion is not the provider
scan's measured duration: the trace records the query separately, and the
service observes completion on a 60-second pending-check cadence. Other scans
in the sampled log took approximately 17.9 and 45.3 seconds. Home loads in
that excerpt occurred at other times; the evidence does not show that those
queries blocked Home.

`unsupported control type 7` is Kodi's numeric BUTTON type rejected as a
child in a `CGUIListGroup` item layout; the decorative no-op new-episode tag
buttons in the poster and landscape layout includes are candidate sources.
The warning does not identify the particular instance, so this remains a
source-supported attribution, not an exact runtime attribution. The
`GetDirectory` failures are separate: logs contain both `include` and literal
`ActivateWindow(Settings)` failures. The latter is present as an action in
Skin Shortcuts data; without a matching click/path trace neither is changed or
attributed to a specific widget.

Beta7 local artifacts were built twice reproducibly:

- Service `0.4.35`: SHA-256 `562009204db0fd63c651890ec9fad35541db46b5c148b14a5f5230c698c84e59`.
- Skin `1.2.29~beta7`: SHA-256 `a97177a4039b873b00eb9fd3fca216f842873f204614e55c4be8bf5bec38c34c`.

## Beta7 follow-up — empty Home output and Beta8 repair, 2026-10-18

The authorized Lenovo was updated natively from Beta6 to service `0.4.35`
and skin `1.2.29~beta7`. Kodi reports Home loaded with Spotlight content, but
after more than five minutes the on-screen diagnostic still showed no live or
recent-movie count and the visible Home contained no widget posters. The
Kodi process remained foreground and its Android input channel reported
`responsive`; this does not establish that the Kodi GUI was frozen.

Read-only inspection of active Skin Shortcuts 2.0.3 output found 73 generated
include declarations. The three active widget-template declarations
(`Widgets`, movie hub, series hub) were empty nodes; Kodi's log at the same
Home load reports `Skin has invalid include` for the widget template and
`GetDirectory - Error getting include`. The profile still had six Home
shortcut records and 46 `widgetExpandable` rows (20 current four-field rows,
26 preserved legacy rows). Those stored inputs do not prove that Home's
generated templates were materialized. The active skin source and installed
manifests identify the running versions; no profile data was changed.

Beta7's pending-migration path could return `CURRENT` from the verified
layout-state version without validating active generated XML, and its
once-per-session marker only represented the layout schema. The device log
after the skin update has no corresponding successful interface-build record.
This is a source-confirmed recovery gap consistent with the observed empty
generated templates; whether the initial empty generation also involved a
Skin Shortcuts runtime/build issue remains undetermined. The unrelated
`unsupported control type 7` warning and the `GetDirectory` errors are not
attributed by this evidence.

The private Beta8 service change (candidate `0.4.36`) checks the active
generated output and the existing property store before treating a verified
migration as reusable. It keys one bounded attempt to the installed skin
version and those output fingerprints, so repeated Home loads of identical
stale output are coalesced while a changed package/output can be retried even
within the same Kodi process. A separate native preparation lock still
serializes actual Skin Shortcuts work. It does not delete caches, rewrite
shortcuts, or touch stable data. Automated tests cover current/invalid output,
signature changes, changed-signature claims in one process, and checking
readiness before the session marker. This is not yet runtime validation.

The Beta8 package and `docs/testing` index were rebuilt reproducibly in the
current worktree, but have not been deployed from GitHub or installed on the
Lenovo. Service `0.4.36` SHA-256 is
`7ad66e9cb6969445fef4c698eb50c471d9cda4d230c03e1832887f431ce7e7da`;
test-feed `addons.xml` SHA-256 is
`0d18b8384549245dacb03c5b731df083cb5581aa75e99c5a783248affad25631`.
The stable `repo/` tree remains unchanged. The test suite passes 61 tests.
Trailer touch remains FAIL_RUNTIME on the previously observed installation.
Install only after this candidate is merged and deployed to the official Beta
feed, then verify generated widget rows and Home on Lenovo.

The earlier ~60-second `service.search_refresh` wall interval still does not
prove it blocked Home: the correlated XStream scan itself finished in about
20 seconds, while the service trace completed at its pending-check cadence.
No current Home-load/query causality has been established.
- Test index: SHA-256 `ea1901d0b9cebad8155241f81e29b0f3c9936b1f86ea885d45570667edc7056f`; MD5 verified.
- Bootstrap repository ZIP: SHA-256 `72a7b30b9f6fa4ff8a05261f7e92330ad30a7cfb743cfd164b10e421707ab5e1`.

The automated suite passes 56 tests (51 existing plus 5 new coordination/build-policy tests). The Beta7 packages are currently local branch artifacts, not yet deployed or installed. Trailer touch remains FAIL_RUNTIME on Beta6. The Beta7 coordinator change still needs a native Beta install and runtime log confirmation; no Stable feed was changed.
