# Remote continuation audit — 2026-10-17

## Confirmed

- Lenovo TB330FU accessible by ADB at `192.168.1.215:41583`; Kodi running; installed `skin.actweeter` is `1.2.29~beta3`.
- Beta3 functional evidence and ADB screenshots are documented in `BETA_WIDGET_NAVIGATION.md`; this is not a new functional validation.
- `python3 -m unittest discover -s source/0.4.32/tests -q` => 41 PASS on Mac.
- Beta branch was clean at start; stable was not modified or published.
- Android Kodi log after a skin reload: `SKINSHORTCUTS_BUILD status=finished output_changed=false`, `INTERFACE_LAYOUT migration=... status=verified`.

## Unresolved, no speculative patch applied

- Vertical touch gesture in nested Home `grouplist` 77777 versus horizontal child fixedlists. Home uses `Fixed_Focus_Bottom` = -100000 and per-row `Fixed_Focus_Navigation` animations. Removing only the oversized bottom without reconciling animations risks remote/focus regressions.
- Trailer touch in the video information dialog: two variants of `radiobutton` 54 exist in `IncludesDialogVideoInfo.xml`. Remote OK worked on one series, touch did not. Inspect active layout, actual hit rectangle and focus/event routing before changing playback commands.
- Auto-trailers, new-series/new-episodes badges, collections and profile isolation have not passed Lenovo functional gates. EXPANDIR right-edge clipping remains.
- Android log contained `Trying to add unsupported control type 7` during Home load; investigate context and relevance, do not assume root cause.

## Read-only Kodi Master comparison

Against `source/0.4.32/addons` using SHA-256 per file (excluding __pycache__):

- `skin.actweeter`: zero files unique to Master, 31 same-path differing files, 34 files unique to source.
- `service.actweeter`: zero files unique to Master, 7 same-path differing files, 54 files unique to source.

Differences are NOT necessarily missing features: installed Master and development source may represent different versions. Review diffs semantically, with no writes to Master.

## Safe next gates

1. Capture Kodi GUI coordinates / screenshots and active window/controls before and after vertical drags and trailer taps; compare with remote keys and scroll bar interaction.
2. Test a coordinated bounded-scroll and focus-animation change on a new Beta revision only; retain rollback and prove horizontal/vertical/remote navigation and EXPANDIR on device.
3. Test trailer touch against actual active button bounds, preserving the existing remote OK route.
4. Test auto-trailer, new badges, favorites/pending/profile, category back navigation and right-edge visibility.
5. Keep stable feeds and Kodi Master read-only. Do not mark any untested gate PASS.
