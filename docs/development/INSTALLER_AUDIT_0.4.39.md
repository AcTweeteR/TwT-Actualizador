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

## Verified official publication

- PR: https://github.com/AcTweeteR/TwT-Actualizador/pull/21 (merged).
- Public commit: `0fd276e9b94821efa61697dba303ef26287870df`.
- Beta release: https://github.com/AcTweeteR/TwT-Actualizador/releases/tag/v0.4.39-beta-installer
  (`isPrerelease=true`, not draft, not promoted to Latest).
- GitHub Pages build for that commit completed successfully. All six CI/
  deployment runs succeeded, including historical Beta snapshots and the new
  current-installer reproducibility job.
- Public index downloaded from
  https://actweeter.github.io/TwT-Actualizador/testing/repo/addons.xml
  advertises service 0.4.39, Testing repository 1.0.1, skin 1.2.29~beta10 and
  XStream 1.1.2.8. SHA-256:
  `63e90e1e1a5f4178f79eb627509e5c67e845db17a56d1dd4027e3bcb86262b92`.
- Public index MD5: `af8158bc17bf98965c30d1154d02a1d6` (download verified).
- Public ZIP downloaded from
  https://actweeter.github.io/TwT-Actualizador/testing/repo/service.actweeter/service.actweeter-0.4.39.zip
  matches the local source-built package byte-for-byte; CRC and embedded
  manifest 0.4.39 pass. SHA-256:
  `edaa5072a968811e3b153416e03408749b61fb217da3bbf02885e375ed688e2a`.
- Published-source suite: 109 PASS. Integration-source suite: 246 PASS. The
  public subset retains the previous public tests and does not import private
  XStream 1.1.2.9 development. No source/package modification of XStream or
  the skin is in this publication.
- Stable repo/, AGENTS.md, old ZIPs, bootstrap ZIPs, skin and XStream artifacts
  compare unchanged against pre-publication main ecabbe6.
- Source vs ZIP: all 101 packaged files match. AST/XML/CRC/checksums pass;
  credential/token/private-key/credential-URL pattern scan found no matches.
- Mac Master was not written, launched, restarted or used for installer QA in
  this mission. No QA profile was created. No IPTV, PVR, Trakt or user-profile
  data was changed. Actual update/installer execution in tvOS remains pending
  the owner's test; no live installation or trailer playback PASS is claimed.
