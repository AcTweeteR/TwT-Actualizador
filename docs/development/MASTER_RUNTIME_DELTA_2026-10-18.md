# Master installed-vs-candidate delta — read-only audit (2026-10-18)

## Purpose

Do **not** replace the currently working macOS Kodi Master tree with the Beta
candidate as an undifferentiated directory copy. This snapshot reports only
source names, versions, aggregate file counts, and generated XML structure.
It contains no credentials, personal Kodi settings, or playlist URLs.

## Compared roots

- Installed (read-only): `~/Library/Application Support/Kodi/addons/`.
- Candidate: `source/0.4.32/addons/` in the **Master integration feature branch**
  `codex/master-integration-2026-10-18` of the official repository.
- Compared only files with suffix `.py`, `.xml`, `.xsp` under each add-on;
  the aggregate comparison excludes files named `settings.xml`.
- The candidate snapshot folder name `0.4.32` is **not** the service or skin
  version embedded in its `addon.xml`.

## Aggregate results

| Add-on | Mac installed | Candidate source | Shared files | Modified shared files | Installed-only | Candidate-only |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `service.actweeter` | `0.3.8` | `0.4.37` | 18 | 8 | 0 | 17 |
| `skin.actweeter` | `1.2.0` | `1.2.29~beta10` | 241 | 30 | 0 | 2 |

Relevant modified service files: `service.py`, `setup.py`,
`resources/lib/first_run.py`, `resources/lib/kodi_auto_preview.py`,
`resources/lib/automatic_preview.py`, `resources/lib/xstream_setup.py`,
`resources/lib/search_background.py`, and `addon.xml`.

The installed XStream add-on reports `plugin.video.xstream-pro 1.1.2`.
The candidate's `source/0.4.32/addons/` tree does not contain a full
`plugin.video.xstream-pro` add-on folder (it does have separate patch/build
and distribution workflows). **Do not** infer that the official repository
lacks an XStream package from this snapshot directory alone.

## Critical generated-skin difference

File: `skin.actweeter/1080i/script-skinshortcuts-includes.xml`.

| Property | Installed Master | Candidate snapshot |
| --- | ---: | ---: |
| Bytes | 883,691 | 52 |
| Lines | 15,663 | 2 |
| XML root | `includes` | `includes` |
| Direct `include` definitions | **111** | **0** |
| XML parse | PASS | PASS |

This is a clear installed generated-output vs candidate placeholder distinction,
**not** by itself a diagnosis of a migration failure. Copying the placeholder
over the generated file without testing proper Skin Shortcuts regeneration
could disrupt the Home/menus/widgets. Treat the current generated includes
as runtime state to preserve and back up, not as a canonical source file to
replace blindly.

Other notable modified skin paths include `1080i/Home.xml`,
`1080i/IncludesHomeBingie.xml`, `1080i/IncludesDialogVideoInfo.xml`,
`1080i/DialogVideoInfo.xml`, and multiple `shortcuts/*.DATA.xml`.

## Controlled migration gate for Codex

1. Keep existing Master and provider credentials untouched; take a verified,
   restorable snapshot before **any** subsequent deployment.
2. Compare versioned source changes separately from generated Skin Shortcuts
   output and user-maintained `userdata/addon_data`. Identify which component
   generates each artifact and the migration ordering/consent required.
3. Test the update in an isolated Kodi profile through the supported Kodi
   repository/add-on update path, including startup, Skin Shortcuts
   regeneration, populated Home/Spotlight, PVR, movie and series destinations,
   manual trailer and automatic preview state transitions.
4. A test with an isolated/disposable profile cannot by itself validate
   preservation of the owner's customized Home. Plan a dedicated,
   backed-up preservation check before modifying the working profile.
5. Preserve the existing fail-closed and optional-dependency contracts. Keep
   source-vs-runtime differences as `NOT_TESTED` until observed.
6. Do not install the candidate or publish Beta/Stable merely because this
   read-only comparison passed.

## Provenance and limits

Gathered using filesystem reads and Python `xml.etree.ElementTree`; no
commands wrote to installed Kodi or terminated Kodi. File counts apply to
source-like suffixes only and do not include images, ZIP archives, binaries,
cache, provider data, or Kodi profile settings. A later branch/deployment
may legitimately change the counts; recompute before any migration.
