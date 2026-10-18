# Contributor / coding-agent operating notes

This is the **official** Kodi AcTweeteR repository (`AcTweeteR/TwT-Actualizador`).
Read the existing development documentation before making changes:

1. `docs/development/WORKSPACE_LAYOUT.md` — worktrees, channels, archives and safety.
2. `docs/development/MASTER_HANDOFF_2026-10-18_CHATGPT.md` — last Master integration evidence and continuation checklist.
3. `docs/development/MASTER_RUNTIME_DELTA_2026-10-18.md` — macOS Master vs candidate: generated Skin Shortcuts state and migration risks.
4. `docs/development/MASTER_INTEGRATION_AUDIT_2026-10-18.md` — earlier runtime findings, explicitly bounded.

## Collaboration rules

- Confirm `pwd`, `git status --short --branch`, `git log -5 --oneline` and `git worktree list` first. The containing `Kodi AcTweeteR/` directory has a separate empty Git repository; never commit there by accident.
- Look for concurrent agent sessions and preserve all in-flight worktrees. Do not overwrite the active Beta Android changes while working on Master.
- **Owner decision 2026-10-18:** operate on the existing Kodi Master only. Do not create a second Kodi QA profile, portable copy, or alternate working Kodi installation. Read `docs/development/PHASE_1_5_CLOSURE_GATE_2026-10-18.md` and work toward real post-integration runtime acceptance. Other pre-existing Codex worktrees are references, not targets for new development.
- Use one task per commit, with regression tests and a factual handoff note. Preserve exact evidence levels: `PASS_STATIC`, `PASS_AUTOMATED`, `PASS_RUNTIME`, `NOT_TESTED`. Never infer runtime success from source tests.
- Run the applicable `tools/workspace_guard.py --require-branch <expected>`, full source tests for the active candidate, Python/XML checks, and `git diff --check`. Record test counts and limitations.
- **Master integration is now installed** (skin `1.2.29~beta10`, service `0.4.37`, XStream `1.1.2.8`), with 580 versioned files verified. Never overwrite the generated `script-skinshortcuts-includes.xml` or user shortcuts: see `docs/development/MASTER_INPLACE_INTEGRATION_2026-10-18.md` for full-profile backup and guarded in-place verification/rollback. Do not re-copy entire candidate trees or auto-accept a customized-layout replacement; preserve Master-only trailer behavior.
- Do not touch Kodi profiles, credentials, third-party app settings, devices, stable releases, or public feeds without explicit scope and verification. Do not put IPTV URLs/tokens in logs, tests, docs, commits or screenshots.
- Preserve source/versioned snapshots and third-party licensing. Use supported repository update/rollback paths, not untracked manual ZIP replacements.
- When starting or ending a session, update the relevant handoff with baseline commit, exact paths changed, tests, runtime boundaries and unresolved blockers so ChatGPT and Codex can resume one another's work.

These rules do not supersede the repository's tests, device owners' approval, or new explicit instructions.
