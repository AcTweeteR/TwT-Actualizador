# Installer repair 0.4.39 — evidence and acceptance

Base: integration a64477e / public main ecabbe6. The distributed 0.4.38
service was compared entry-by-entry with its source before this change: only
setup.py, first_run.py and module_catalog.py differed after the installer fix.
The new service also changes its own version/changelog; playback, PVR binding,
credentials, profiles, preview coordinator and skin are not modified by this
release. No installed Kodi files or AGENTS.md were written in this mission.

## Confirmed defects and corrections

- `_install_slyguy_stack` required Stable even when Testing was enabled.
  The same stale assumption existed in `_open_settings`. All three install
  entry points now share repository-candidate selection. They use already
  installed repositories and never install/switch AcTweeteR channels.
- Installed SlyGuy was checked with mandatory-only minimums, omitting its
  optional minimum versions. One shared readiness predicate now verifies
  enabled state and every explicit minimum, including diagnostics.
- Already-ready add-ons prompted unnecessarily; they now return without
  reinstalling or asking for consent. Missing/disabled/old components still
  use Kodi installation/enable/update UI and its trust/license confirmations.
- InputStream Adaptive was a mandatory catalog root although no mandatory
  AcTweeteR manifest imports it. It is now a consent-selected optional trailer
  capability; its absence cannot block the IPTV core. This does not claim that
  DASH trailers play without InputStream.
- Seven baseline tests failed on old version/index assumptions. Current
  candidate contracts advance; historical Beta11 index verification now
  reconstructs the immutable index from its original packages and still checks
  its original MD5/SHA-256. No historical artifact or manifest is overwritten.

## Dependency evidence

`INSTALLER_DEPENDENCY_AUDIT_0.4.39.json` records 43 recursively inspected addon
IDs, source-index digests, minimums, licenses as advertised and platform tags.
Sources: official Kodi Omega, Matke Omega, official SlyGuy and AcTweeteR Beta.
SlyGuy's fetched index contains repository.slyguy 0.0.9, slyguy.dependencies
0.0.30, script.module.slyguy 0.87.0 and slyguy.trailers 0.2.1. The repository
is a real import of the upstream dependency/module manifests, not an invented
bootstrap requirement. Both AcTweeteR repositories already aggregate that
same complete upstream index. No new third-party package is hosted here.

PVR/InputStream entries in the generic Kodi index advertise Windows/macOS/
Android binaries, not tvOS. Pillow is verified as bundled on this Mac only;
that does not prove its tvOS presence. The signed Kodi tvOS distribution must
provide compatible native components. No cross-platform binaries are copied.
Metadata availability is not a runtime install or playback test.

## Tests and preservation

246 integration-branch tests pass. New real-function Kodi API-double tests
exercise Stable-only, Beta-only, both, disabled Beta/consent, absent/partial/
disabled/old/ready SlyGuy, declined optional install, absent sources, failed
transactions followed by retry, bounded waits, existing-add-on idempotence,
Beta XStream settings, optional InputStream and wizard-state normalization.
These are PASS_AUTOMATED, not live Kodi PASS_RUNTIME.

Wizard schema/version is unchanged. Known step statuses and Trakt status
survive repeated normalization; state files use existing atomic saves.
No private token access, provider URL mutation, profile copying, cache deletion,
global security setting or Kodi repository-origin preference change is added.
No Mac runtime installer test was performed: Master is excluded and no safe
isolated instance was started. tvOS execution is PENDING_USER_TEST.

## Apple TV update / acceptance

1. Keep Testing Repository 1.0.1 enabled. In Kodi Add-ons, check for updates.
2. Open AcTweeteR Service → Versions/Update and select 0.4.39 from Testing.
   Do not reinstall Kodi or the skin and do not delete any add-on data.
3. Reopen AcTweeteR setup. Use Repair components first; then resume the
   provider/service steps. Existing IPTV credentials remain in XStream.
4. If SlyGuy is desired, choose Prepare trailers and accept Kodi's own prompts.
   Record installed/enabled versions of repository.slyguy, slyguy.dependencies,
   script.module.slyguy and slyguy.trailers. Alternatively leave it pending;
   mandatory IPTV preparation must still be able to finish.
5. Record the exact next error, if any; redact URLs, passwords and tokens.
   Confirm Home, movies, series, a safe episode/live channel, Search, Back,
   Continue Watching and a manual trailer separately. These are not pre-passed.
6. Restart Kodi normally and confirm version, preserved provider/profile and
   setup progress. Do not use the skin's system-power action to quit a Mac.

Recovery: historical 0.4.38 package is retained unchanged in Testing. Kodi's
native Versions dialog can select it if offered. Otherwise report the failure
before making further changes; no destructive downgrade or profile reset.
Stable remains unmodified. Publication/hash evidence is appended separately.
