# AcTweeteR 0.4.10 — Stable

Stable Kodi 21 Omega update: skin 1.2.11, service 0.4.10, repository 1.0.3.
XStream Pro remains 1.1.2.

## What changed

- Home, Movies, and Series now seed the AcTweeteR provider rows on the device
  and ask Kodi's Skin Shortcuts add-on to generate its includes.
- Spotlight rotates real provider entries; year rows use the current and
  previous calendar years.
- Factory English XStream metadata preferences are set to Spanish, while a
  user's non-English custom language is preserved.
- Automatic SlyGuy previews use AcTweeteR's ownership-aware bridge. Setup asks
  before applying the reversible integration to the known SlyGuy 0.2.1 files;
  SlyGuy packages are not redistributed by AcTweeteR.
- Stop actions inherited by the skin no longer interrupt SlyGuy previews.

## Verification

- Automated suite: 437 tests passed.
- On the affected Apple TV, provider rows and 2026/2025 catalog rows loaded;
  Spanish synopses were visible; an automatic preview reached AVStarted and
  advanced in Home, then stopped cleanly on return to the menu.
- After Kodi was restarted, the owner confirmed Spanish synopses and automatic
  previews still worked.
- This was an update to an existing profile. A clean installation with these
  versions remains **NOT TESTED**. No new Android TV or macOS runtime validation
  is claimed. Prior IPTV/PVR/EPG evidence is retained and is not represented as
  a new test in this release.

## Compatibility and recovery

Older packages remain in the Kodi repository for recovery. The service backs up
managed interface and metadata settings on-device; unknown user edits require
consent. SlyGuy integration has a guarded rollback that refuses to overwrite
later user changes.

XStream Pro 1.1.2 retains its CC BY-NC 4.0 attribution and modification notice;
its non-commercial license terms continue to apply.
