# Kodi Master — shared ChatGPT / Codex handoff (2026-10-18)

## Scope and provenance

- Official repository: `AcTweeteR/TwT-Actualizador`.
- Worktree: `/Users/alberto/Documents/ChatGPT/Kodi AcTweeteR/TwT-Actualizador-master-integration`.
- Branch: `codex/master-integration-2026-10-18`.
- Starting HEAD for this handoff: `6646ccf` (post-restart Master preview ownership/terminal regression fix).
- The parent directory `Kodi AcTweeteR` is **not** the canonical Git checkout: its independent `main` has no commits.
- A separate Codex agent was working on `codex/beta-widget-horizontal-navigation`. Do not overwrite or merge its in-flight changes. No Beta/Stable release operation is authorized by this handoff.

## Changes made in this ChatGPT session

1. `source/0.4.32/addons/service.actweeter/resources/lib/kodi_auto_preview.py`: catch missing required `focus` event fields (`KeyError`) alongside invalid values. Previously, a decoded, otherwise valid focus notification missing `window`, `container`, `focus`, or `position` propagated out of `on_notification()` into Kodi's monitor callback. The change rejects these packets with the existing `FOCUS_REJECT invalid_payload` signal before changing ownership or writing Home properties.
2. In the same parser, reject non-finite preview delays (`nan`, `inf`, `-inf`) before scheduling. These previously passed `float()` and could create unusable/infinite or immediately pathological deadlines.
3. `source/0.4.32/tests/test_kodi_auto_preview_notifications.py`: added isolated contract tests for valid and Kodi-prefixed focus notifications; missing fields; bad/non-finite delays; foreign sender; invalid base64; idle OTHER owner recovery; active OTHER ownership preservation; and Kodi visibility-read failures. A lightweight stub runs the real `on_notification()`/`_focus()` paths without starting any worker or using real player/profile state.

## Reproduction and verification

- On the unmodified source, the required-field regression raised four `KeyError` exceptions in four test subcases; with the first fix, those cases stopped raising.
- Non-finite delays were also independently reproduced as accepted when `nan`, `inf` or `-inf` was supplied in a valid notification.
- Before these changes: `python3 -m unittest discover -s source/0.4.32/tests -q` — 94 PASS.
- Final source branch verification: **102 tests PASS** (`python3 -m unittest discover -s source/0.4.32/tests -q`), `compileall` PASS, `git diff --check` PASS, workspace branch guard PASS. No live Kodi tests were executed.
- Re-run the entire suite after all changes; report an exact count. Test statuses are `PASS_AUTOMATED`, **not** Kodi `PASS_RUNTIME`.

## Explicit runtime boundaries

- No copies were installed into `~/Library/Application Support/Kodi/addons`, and no running Kodi process was killed/restarted; no personal settings, stream URLs, credentials, playback history, profiles, or real provider content were changed.
- No ZIP package was built, no repository feed was published, and no tvOS or Lenovo device was touched.
- The Mac Master runtime is deliberately different from the `source/0.4.32` candidate: the installed Master service is `0.3.8` and skin is `1.2.0`, versus candidate service `0.4.37` and skin `1.2.29~beta10`. The separate [read-only delta audit](MASTER_RUNTIME_DELTA_2026-10-18.md) records generated Skin Shortcuts state that must be preserved and tested. Do **not** copy the candidate over the installed add-ons wholesale.
- Earlier Master evidence: Home/Spotlight and content rows PASS_RUNTIME; manual Spotlight movie and series trailer paths PASS_RUNTIME (limited); first-run status with SlyGuy absent, automatic-preview cancellation/audio/identity/full lifecycle, details dialog trailer, tvOS behavior, and installer persistence remain NOT_TESTED. The persisted first-run state was `prompted`, so startup skipped the interactive wizard.
- Full touch detail-dialog acceptance on Lenovo remains separate Beta work. Do not use this Master notification fix as proof that touch is repaired.

## Safe continuation for either agent

1. Start with `git status --short --branch`, `git log -5 --oneline`, `git worktree list`, and this file. Check for another active agent before writes.
2. Run `python3 tools/workspace_guard.py --require-branch codex/master-integration-2026-10-18` and `python3 -m unittest discover -s source/0.4.32/tests -q`. Record the exact count and commit.
3. Review the pending preview lifecycle paths **without** speculatively changing Kodi's player or SlyGuy integration; prioritize reproducible tests and source-level invariants. Check the standalone no-SlyGuy wizard status only in a disposable isolated Kodi profile or with a controlled test double, not by uninstalling add-ons from the owner's profile.
4. Future packaging and macOS/tvOS runtime gates need explicit compatibility testing. Maintain separate `PASS_STATIC`, `PASS_AUTOMATED`, `PASS_RUNTIME`, and `NOT_TESTED` evidence.
5. Keep changes in named worktrees/feature branches with small commits, focused tests, and append new handoff notes. Do not publish Stable or mutate user runtime data without independent validation and explicit approval.

## Collaboration contract

This file is an appendable signpost. ChatGPT and Codex should use **the official Git branch and commits** as the source of truth; this handoff is evidence, not a substitute for `git status` or the test suite. Every next agent must document: exact baseline commit, files changed, commands/results, runtime gates, and unresolved blockers. Do not cherry-pick/mass-copy the historical snapshots or active Beta worktrees into Master.
