# AcTweeteR — workspace layout and safe development

## Official source of truth

- **Only official GitHub:** https://github.com/AcTweeteR/TwT-Actualizador
- **Active Beta worktree:** `TwT-Actualizador-beta-widget-navigation/` (branch `codex/beta-widget-horizontal-navigation`). Continue from its latest remote commit.
- **Git administrative checkout:** `TwT-Actualizador-git-admin/`. This directory holds the `.git` object database used by official linked worktrees; **do not remove, rename or archive it without migrating Git metadata**. Its historical branch is not the active source.
- **Historical worktrees and clones:** `_archive_readonly_2026-10-17/`, including uncommitted prototypes. Do not delete, reset, auto-merge, publish or modify their worktrees. See `inventory.json` and the `.working.patch` snapshots. Untracked files are preserved in the archived trees.
- **Unrelated/experimental:** `Kodi AcTweeteR Test/`, `qa/` and installer directories were not modified.
- **Outer directory's `.git`:** an independent empty repository, **not the official AcTweeteR repo**. Always `cd` to the active worktree, never run `git` in the outer directory.

## Canonical versioned source

`source/0.4.32/addons/` is the current **Beta candidate** source snapshot (service 0.4.36, skin 1.2.29~beta7). Historical `source/0.4.28`–`source/0.4.31` are intentionally retained as reproducibility snapshots. They are NOT competing live development trees. Do not rename/move their contents or flatten them into a new `addons/` until the reproducibility workflows are migrated and verified. This prevents invalidating versioned release provenance.

## Channel boundaries

- Stable packages and feed: `repo/` and official stable bootstrap. Never rewrite them from a Beta build.
- Test packages/feed: `docs/testing/` and `testing/`; Kodi installations only via the official AcTweeteR test repository.
- A GitHub prerelease or a separate feed alone is **not proof** that Kodi auto-updates cannot cross channels. Verify add-on origin, version precedence and rollback behavior on a test installation before promising isolation.
- Preserve Kodi Master on Mac as read-only and all user data on all devices. No ADB sideload, manual profile copying or ZIP installation.

## Safe commands

```sh
cd '/Users/alberto/Documents/ChatGPT/Kodi AcTweeteR/TwT-Actualizador-beta-widget-navigation'
python3 tools/workspace_guard.py --require-branch codex/beta-widget-horizontal-navigation
python3 -m unittest discover -s source/0.4.32/tests -q
# Before any publication or destructive operation:
python3 tools/workspace_guard.py --require-clean --require-branch codex/beta-widget-horizontal-navigation
```

Do not publish Stable or claim full touch/trailer acceptance until Lenovo runtime gates pass. Current unresolved gates are documented in `BETA_WIDGET_NAVIGATION.md` and `HANDOFF_REMOTE_AUDIT_2026-10-17.md`.

## Historical archive policy

Archive directory is a **preservation area, not a source tree**. Seven older repos/worktrees were moved here with their content, Git state and untracked files intact, plus three older official linked worktrees. `inventory.json` covers the seven historical projects and records their original branches and dirty state. No historical commits or branches were deleted. Some archived worktrees depend on Git metadata in the active Git administrative checkout or in `TweeteR-Kodi-0.4.26`; keep those roots.
