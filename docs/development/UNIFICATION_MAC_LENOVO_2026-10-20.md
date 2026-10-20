# Mac Master + Lenovo Beta unification — 2026-10-20

## Status

`PARTIAL` — source integration and automated/package validation are complete for this candidate. It is **not published or installed**. Runtime acceptance on the candidate is still required before a Beta deployment.

## Source and protection boundary

- Official repository: `AcTweeteR/TwT-Actualizador`.
- Worktree/branch: `TwT-Actualizador-unify-master-beta-20261020` / `codex/unify-master-beta-2026-10-20`.
- Base and current `HEAD`: `d9a0ae7523df6fe7f34afd55c829998d34380af6` (`origin/main` at audit time).
- The branch was created from the explicit official `origin/main` reference; the pre-existing branch name did not exist.
- Stable index `repo/addons.xml` remains byte-identical to the initial baseline, SHA-256 `cada550963d1456d7e3bd5566128fb6cd3936dd2ae8992cceb3673fd2f383976`.
- No files in Kodi Master, Lenovo, Apple TV, or Stable were changed. No profile, user data, credential, or Trakt state was copied.
- The original Master-integration worktree and its untracked `source/0.4.32/dist/` were not modified.

## Reconciled versions

| Component | Mac Master observed | Lenovo observed | Candidate source |
|---|---:|---:|---:|
| Skin | `1.2.29~beta10` | `1.2.30~beta1` | `1.2.30~beta2` |
| Service | `0.4.37` | `0.4.43` | `0.4.44` |
| XStream Pro | `1.1.2.8` | `1.1.2.9` | `1.1.2.10` |
| Testing repository | — | `1.0.2` | `1.0.2` (unchanged) |

Read-only recheck on 2026-10-20 confirmed the same installed versions. Lenovo was identified as `TB330FU`, Android 15, Kodi `21.3` via the existing ADB connection. Mac process `/Applications/Kodi.app/Contents/MacOS/Kodi` (PID 1962) remained running with the listed Master versions. The candidate is not installed on either device.

## Integrated differences

- **Skin:** retained Lenovo's guarded automatic-preview focus wiring and restored Mac's manual SlyGuy trailer action for both `movie` and `tvshow` items. The automatic preview remains separately opt-in and gated; generated `script-skinshortcuts-includes.xml` and other profile-owned state were excluded.
- **Service:** kept the Beta repository discovery, XML/shortcut identity, atomic search-store and initialization work. Removed the service startup write that forced Kodi's global add-on update policy to notify-only; the service now leaves the user's Kodi-wide update preference untouched.
- **XStream:** extended the reproducible source patch so the premium series catalog route records the provider's unfiltered series baseline before UI filters. The existing six-hour per-profile guard prevents duplicate catalog notifications. The package builder now rejects archives missing this hook and accepts the new candidate version. CC BY-NC 4.0 attribution and the pinned upstream archive are retained.
- **Channel packaging:** candidate index generation targets `repository.actweeter.testing` only; Stable `repo/` artifacts and index are not regenerated.
- **Excluded:** device settings, credentials, Trakt tokens/session, generated user menus, profile data, caches, and compiled Python files.

## Automated and static checks

- `python3 -m unittest discover -s source/0.4.32/tests -q`: **140 tests PASS**.
- `git diff --check`: **PASS**.
- XStream upstream archive SHA-256 matched its pinned manifest: `915f45708670d07e789bb73b7390a7b5cf30175f818ef5da8ea18c9f13f537fe`.
- Two independent source builds produced identical ZIP hashes (reproducibility check):
  - Service `0.4.44`: `7bf19f1d85323cb410a746c35a683a12f4cd8b27f1dd05d7f723d99fdab001a0`.
  - Skin `1.2.30~beta2`: `752dffebc825702bbb613dec3939e77c5bb8f57cbd12dd12b7fcc169f677f349`.
  - XStream `1.1.2.10`: `0824403e46d3d7ac1b8e4949e8d89f78e51727fec60680b015291bbff489bbf7`.
- Private Testing feed build: index versions exactly match Testing repository `1.0.2`, service `0.4.44`, skin `1.2.30~beta2`, and XStream `1.1.2.10`; `addons.xml.md5` matches the index. Candidate ZIP CRC and embedded XML parsing pass; no `.pyc`, caches, databases, logs, M3U/EPG files, or profile data were found. Literal secret scan passed after excluding code that interpolates credentials at runtime and a documented placeholder URL; no credential values were found.
- Testing bootstrap ZIP SHA-256: `ce0f53ea95ece57f4ced0dd1085457084ad2a333b67bdee4e121ef340376b6e1`.
- Candidate Testing index MD5: `852ba029ad14793e49cc51bbf527c682`.

## Runtime status and release gate

| Check | Result | Evidence / limitation |
|---|---|---|
| Existing Master | `PASS_STATIC` version/process identification; candidate `NOT_TESTED` | Read-only process and addon manifest inspection; candidate was not installed. |
| Existing Lenovo Beta | `PASS_STATIC` device/version identification; candidate `NOT_TESTED` | Existing ADB connection read `TB330FU`, Android 15, Kodi 21.3 and installed add-on manifests; no device files were written. |
| Candidate trailers, widgets, XStream and PVR | `NOT_TESTED` | Automated contracts/build checks are not real Kodi playback or UI tests. |
| Stable/Testing separation | `PASS_STATIC` | Candidate builder emits only the Testing repository identity; Stable index hash is unchanged. |
| Candidate Testing discovery/update | `NOT_TESTED` | Candidate feed is under `/tmp` only and has not been published. |
| Trakt isolation | `PASS_STATIC` | No authentication or synchronization was performed; Lenovo remains unauthenticated. |

The source integration is committed locally in three auditable commits:

- `c01c047` — preserve the user's update preference and manual series-trailer actions.
- `d7fa0e4` — record premium series catalogs and validate the XStream package hook.
- `47e52d2` — prepare candidate versions and Testing-only feed generation.

No push, PR, release, or device installation has been made. The candidate should not be promoted or treated as runtime-validated until the owner authorizes and completes a Beta QA deployment through Kodi's Testing repository.

## Working tree at report time

The branch contains the source, tests, changelogs, and report described above. The final report update is committed separately after the three integration commits. No unrelated worktree changes were staged or included. This document records the candidate state, not publication approval.
