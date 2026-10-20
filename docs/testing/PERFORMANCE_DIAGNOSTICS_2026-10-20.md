# AcTweeteR Performance 2.0 — XStream diagnostics build

**Testing candidate:** XStream Pro 1.1.2.12  
**Base:** upstream XStream Pro 1.1.2, AcTweeteR 1.1.2.11 runtime  
**Kodi:** 21.3 Omega  
**Scope:** opt-in instrumentation only. No provider, cache policy, menu, widget, artwork, playback, service, skin, or account behavior is intentionally changed.

## Instrumentation

The package includes a temporary setting, **Performance diagnostics (Testing build only)**, in XStream's add-on settings. It defaults to **off**. When off, XStream does not import the diagnostic module or install timing wrappers; the existing premium dispatcher runs directly. Enable it only on the test profile, then run the desired menus/widgets. It applies to each subsequent XStream plugin process. Turn it off after collecting data.

Each instrumented process emits one aggregate line with a random correlation ID, allow-listed route/media, numeric timing/count aggregates, CPU counters, peak RSS where supported, active thread count, and Linux/Android process I/O counters where available. It never logs call arguments, provider names, cache keys, titles, paths, URLs, credentials, tokens, or API response/error text. Errors retain their original behavior and are counted by type of operation, without message text.

Recorded phases include:

- first module line to add-on setup, and first module line to the premium dispatcher;
- premium dispatch, provider credential selection, Xtream streams/categories, visibility filtering, ranking, metadata preparation and enrichment;
- Xtream streams/categories, VOD info and series-info request call durations; TMDb search/details/images and Trakt public-list calls;
- common JSON cache reads/writes and hit/miss counts; series catalog/inventory, watched and resume-state reads;
- VOD prefetch, ListItem construction/completion, Kodi directory-item insertion, and end-of-directory calls;
- process user/system CPU deltas, peak RSS, thread count, block I/O and /proc I/O byte deltas when the platform exposes them.

Timings are inclusive when a phase contains another timed phase; do not add nested phase totals. Each log line is one process/request. Calculate medians/P90 across repeated, equivalent invocations after collecting at least ten samples per condition.

## Limits and complementary visual capture

Python cannot measure time before the interpreter executes the first module line. The two startup values start at that first line; process creation/interpreter launch before it requires external process sampling. Peak RSS is a process high-water mark, not current memory. Per-thread CPU, scheduler wait, storage latency and sustained thermal throttling are not fully available from this add-on probe; collect them separately with OS/ADB tools. Temperature and Kodi texture-cache statistics are external measurements.

The instrumentation measures Kodi directory completion, not screen composition. It does not time first visible title/poster, the last visible image, image decode, GPU texture upload, or animation completion. Capture these separately on screen. Do not treat endOfDirectory as visual completion. The skin and Service are unmodified in this candidate.

## Build and integrity

Build from the pinned upstream ZIP using source/0.4.32/tools/build_xstream_package.py and the checked-in manifest/patches. The upstream archive SHA-256 is locked to `915f45708670d07e789bb73b7390a7b5cf30175f818ef5da8ea18c9f13f537fe`; the Testing package SHA-256 is recorded in `manifests/xstream-performance-diagnostics-20261020.json`. The build retains upstream LICENCE.txt and ACTWEETER_MODIFICATIONS.txt and fails if source hashes, patch contexts, Python syntax, ZIP CRC, expected runtime symbols, or the off-by-default setting do not validate.

The rolling feed change is limited to docs/testing/repo. The Stable feed remains at the pre-existing package set and is checked by the manifest. No service or skin update is part of this build.

## Install and rollback gates

Before installation, preserve and hash the relevant XStream add-on settings and the installed 1.1.2.11 package on each device. Install 1.1.2.12 only by selecting **AcTweeteR Testing Repository** in Kodi; confirm the displayed source and version. Enable diagnostics through Kodi's add-on settings. Do not change Kodi's global automatic-update setting. Never reset/clear provider caches or profile data to construct a cold run.

After collection, disable the diagnostics setting. The saved 1.1.2.11 package and backed-up settings provide an exact code/settings rollback path. Leave caches, watch state, Trakt state, favorites, IPTV/PVR and the profile untouched. No Stable promotion is included or implied.

## Runtime status

Package build and automated source/package checks are required before installation. Mac/Lenovo installation, visual milestones, the requested scenario matrix, and measured per-phase results are recorded in the final audit report after live testing; this document makes no runtime-performance claim.
