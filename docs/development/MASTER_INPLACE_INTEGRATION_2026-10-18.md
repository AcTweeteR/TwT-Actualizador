# Kodi Master — direct integration checkpoint (2026-10-18)

## User-directed scope

The owner explicitly cancelled any additional isolated Kodi QA profile.
Work only against the existing macOS **Kodi Master** installation and its
official Master integration Git branch; preserve the owner's additions.
Do not touch the concurrent Android Beta worktree, Apple TV, or Stable feed.

This checkpoint is an **in-place code integration**, not a claim that every
runtime feature or the eventual multi-device v1.0 is accepted.

## Verified starting point

- Master Kodi executable: `/Applications/Kodi.app`, Kodi 21.3.
- Installed before integration: `skin.actweeter 1.2.0`,
  `service.actweeter 0.3.8`, `plugin.video.xstream-pro 1.1.2`.
- Repository worktree: `codex/master-integration-2026-10-18`, starting at
  `21bbb71`, clean; another Codex process was working on Android Beta.
- Kodi was shut down politely before copying and restarted afterward.
- Full active Kodi profile (1.6 GiB displayed by `du -sh`) was copied using
  APFS copy-on-write into a private folder **outside Git**:
  `~/Documents/Codex/kodi-master-backups/MASTER_BEFORE_BETA_INTEGRATION_20261018_1940`.
  Six key source/profile files were validated by SHA-256 against the original;
  `Addons33.db` passed `PRAGMA quick_check`. Kodi was not running during copy.

## Actual components applied to Master (same profile)

The guarded `tools/integrate_master_runtime.py` tool copied and hash-verified
580 versioned files, including:

- **Service 0.4.37**, using the current Master integration branch source.
  The service carries new modular setup, search, layout migration, PVR,
  diagnostics, profiles, Trakt opt-in code and preview coordination.
- **Skin 1.2.29~beta10**, with new widgets, native scrolling, new menu contract,
  navigation logic, and touch/layout improvements from the candidate source.
- **XStream Pro 1.1.2.8** from the official tracked Testing package, with
  corrections to series changes, collections, resume/pagination, Trakt
  metadata and other provider routes. The ZIP passed integrity checks.

The integration used **the same original Kodi Master profile**, not a clone
as a second Kodi installation. Existing user settings and all
`userdata/addon_data` (including provider credentials and Skin Shortcuts
personalized DATA/property files) were left untouched by the installer.
No URL, password, token, or private setting was copied to Git.

### Protected original Master behavior

- The precise SlyGuy manual Spotlight trailer action chain, return identifiers
  and fallback was asserted against Master before applying the new skin.
  This protects the known working manual-trailer code route at source level,
  *not* its post-update playback runtime.
- Master generated `skin.actweeter/1080i/script-skinshortcuts-includes.xml`
  was **excluded from replacement**. Its 883,691 bytes and 111 generated
  includes remain unchanged and well-formed. Candidate source would otherwise
  contain an empty 52-byte placeholder.
- Profile-side main menu, movie hub, series hub and XStream settings files
  were independently compared against the full backup after Kodi's first
  restart and were byte-identical.
- The only detected `userdata/guisettings.xml` difference at the first Kodi
  shutdown was Kodi's normal `systemtotaluptime` counter; 382 setting values
  were unchanged. Installer verification compares all XML fields/attributes
  while excluding precisely that volatile counter.
- In `first_run.py`, legacy configured Masters whose old completion flag lacks
  newly introduced mandatory runtime gates can avoid automatic modal
  re-onboarding while remaining explicitly `INCOMPLETE` in status and
  eligible for manual setup/repair. A regression test covers this contract.
  An old state already containing the required `PASS_RUNTIME` checks remains
  recognized as complete.

## Validation and limitations

- Source tests: **107 PASS**, Python compile PASS, `git diff --check` PASS.
- `integrate_master_runtime.py verify`: **580 files verified**, generated UI
  and semantic GUI configuration unchanged.
- Kodi's first post-integration startup log confirms it *discovered* skin
  `1.2.29~beta10`, service `0.4.37`, and XStream `1.1.2.8`, loaded the
  new skin, started AcTweeteR service/coordinator/automatic preview and
  SlyGuy preview bridge; the start-up intro ended normally. No Python
  traceback was observed in that startup snapshot.
- **One `GetDirectory - Error getting 1111` remained**. This message was
  documented before the integration and is not yet attributed; Kodi startup
  is not a full Home/navigation/media acceptance test.
- Remote macOS `screencapture` failed with `could not create image from
  display`, so no claim of visual Home/Spotlight, remote control, playlist
  playback, trailer lifecycle, series episodes, Trakt, menu migration or
  automatic preview QA is made in this session.
- No new official ZIP/feed was published; the current Master has source
  installed directly, not a release distributed by Kodi Repository. A later
  Kodi add-on update may overwrite these local changes unless this branch
  is packaged and officially promoted with compatible version handling.
- Android touch work belongs to the concurrently active Beta Codex agent.
  Neither Apple TV nor the Android profile was modified.

## Commands for Codex / ChatGPT

From the *Master* worktree (not the containing empty Git repository):

```sh
python3 tools/workspace_guard.py --require-branch codex/master-integration-2026-10-18
python3 -m unittest discover -s source/0.4.32/tests -q
python3 tools/integrate_master_runtime.py verify --backup "$HOME/Documents/Codex/kodi-master-backups/MASTER_BEFORE_BETA_INTEGRATION_20261018_1940"
git status --short --branch
```

If the integrated Kodi Master fails a functional runtime check, stop Kodi
gracefully first and restore *only the three changed add-on trees* using
`python3 tools/integrate_master_runtime.py rollback --backup <backup_folder>`.
All user data remains in the same profile. The full backup is also available
for a separately verified restoration if later runtime actions change user
data. Do not force-quit Kodi or delete the backup.

## Outstanding acceptance gates (not a second profile)

1. Visually verify Kodi Master Home, 5+3 menu destinations, preserved custom
   movie/series widgets, Spotlight and skin navigation on this existing profile.
2. Test real provider movie and episode paths, PVR/EPG, manual trailer and
   automatic preview ownership/return, without modifying watched history
   unless the owner approves.
3. Inspect the persisted Skin Shortcuts layout v13 migration decision; no
   user-customized DATA files should be overwritten without explicit consent.
4. Close observed `GetDirectory - Error getting 1111` with a targeted
   reproduction instead of speculative XML changes.
5. Once these gates pass, build a **reproducible official** integrated package
   and update channel. Do not claim a v1.0 release or cross-platform parity yet.
