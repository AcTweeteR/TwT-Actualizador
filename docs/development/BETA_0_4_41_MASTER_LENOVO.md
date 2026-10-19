# Testing 0.4.41 — Master development, Lenovo validation

## Authorized environment policy

- Master: `/Applications/Kodi.app`, existing standard profile; development and
  integration. Back up before writes, never erase profiles/configuration.
- Lenovo: Android Beta acceptance, native updates from official Testing only.
- Apple TV: production/Stable role; no connection or mutation in this mission.
  Moving its existing Testing installation to Stable is a separate operation.
- Kodi QA: DISCONTINUED. No QA installation/profile created or used.

## Integration/provenance

PR #22 is already merged as `63be13db36edb452009c228d82169e6126c126d1`.
Service 0.4.40 and skin 1.2.29~beta11 already distribute its focus hooks and
optional, independently consented bridge offer. Do not merge it a second time.

This branch retains `0ed33f87c19e51b03620a4d6b8aceefcc7eaf1df` (stop retrying
deterministic output-validation failures), then adds the profile-scope repair
below and publishes service **0.4.41**. Skin beta11, XStream 1.1.2.8 and Testing
repository 1.0.1 are reused byte-identically. No Stable change is authorized.

## New evidence from Master (read-only)

Master is running `/Applications/Kodi.app/Contents/MacOS/Kodi`. Installed:
service 0.4.37, skin 1.2.29~beta10, XStream 1.1.2.8. It has local integration
history; do not overwrite its add-on directories merely to match a version.

Sanitized existing-log analysis found six preparation attempts at startup,
repeated `GENERATED_XML_PROPERTY_MISSING`, identity/property builds reporting
`output_changed=false`, and final `BUILD_NOT_CONFIRMED`. No log, profile name,
provider URL or credentials were copied to Git.

Read-only parsing of its actual generated includes demonstrates:

| Validator | Home rows | Movie rows | Series rows | Result |
| --- | ---: | ---: | ---: | --- |
| Previous: combines every generated profile | 24 | 49 | 43 | false |
| Corrected: selected profile only | 6 | 10 | 10 | true |

The first profile's expansion metadata and four-field property store were
already valid. Other profiles' rows were being checked against that profile's
property store. Their missing expansion metadata falsely rejected the entire
output, leaving the migration pending. Retrying did not change those foreign
profiles, hence the rebuild loop. This is demonstrated against Master data,
**not proof of the exact Apple TV or Lenovo failure**.

The fix filters Skin Shortcuts' native leading
`String.IsEqual(System.ProfileName,...)` selectors using Kodi's own boolean
evaluator, both for template traversal and generated item identities. Other
visibility/focus conditions are not evaluated to decide which properties must
exist. All runtime callers, including inspection and diagnostics, pass the
evaluator. Unscoped offline callers retain the existing all-profile inspection.
An invalid row in the active profile still fails validation. No generated XML,
property store, menu or unrelated profile is rewritten by the filter itself.

This mission has not installed this code in Master or proven a clean cold
startup there. The direct comparison is **PASS_STATIC on real installed data**.
Disappearing retries alone is not acceptance of initialization.

## Automated and package gates

135 tests PASS with Python 3.11 and 3.14 (same 135 tests, not 270 distinct).
Coverage includes startup reuse, pending migration recovery, interruption,
exclusive preparation lock, legitimate applied changes, customized menus,
multi-profile generated includes, conflicting foreign identities, active invalid
rows, profile switching, installer channels and optional bridge consent.

Service ZIP is reproducible byte-for-byte across both Python versions:
`0ab0b44c00825af323ef37e6e6b918aa24401799a1fc47c0bd82ad2ba57b404f`.
Skin beta11 remains
`66dd56dd5d9b78087fca5d3ba8f49228d3de1217b1aa87c263af7c77c24f2c43`.
These are artifact checks, not playback or native installer acceptance.

## Lenovo procedure and acceptance

ADB server works after the authorized sandbox/network permission. Desktop
Commander sees the Mac gateway. Initial `adb devices -l` and `adb mdns services`
found no Lenovo: connection endpoint requested; no blind port scan or install.

Once connected, verify `ro.product.model`, Android version, supported ABIs and
installed Kodi package before any input. Read Kodi manifests/logs with ADB;
never push profile files or install packages with ADB. Do not navigate another
personal app. Use DPAD/BACK in Kodi and the normal Testing repository update.

Target versions: service 0.4.41, skin 1.2.29~beta11, XStream 1.1.2.8,
repository.actweeter.testing 1.0.1. Preserve optional bridge consent: offer it
through the assistant/“Preparar tráilers y autorizaciones”, never pre-authorize.
Do not force the first-run prompted state or replace profile data.

Acceptance needs separate evidence for installed origin/version/hash, dependencies,
Home loaded, migration VERIFIED, InterfaceReady=1, no repeated builds across
five unchanged restarts, legitimate menu rebuild, manual trailer, Spotlight,
carousel replacement/cancellation, IPTV and preserved customizations. Do not
interrupt user playback or alter history simply to exercise a test.

All of these Lenovo runtime gates start **NOT_TESTED** until observed.

## Recovery and future Stable promotion (not authorized here)

Retain immutable older Testing ZIPs and recorded hashes. Roll back through
Kodi's supported add-on version selection from the official repository, with
auto-update policy explicitly reviewed by the user; never promise a rollback
button exists before checking it on the target. Preserve migration backups and
personal settings; never restore another profile's files or downgrade a database
schema by copying it. No schema change is introduced in 0.4.41.

Before a separate Stable promotion: verify Beta in Master and Android, all
automated/reproducibility/dependency gates, no critical regression, tvOS API and
platform review, actual user tvOS acceptance, recoverable backups and supported
version rollback. Review channel origins/version precedence explicitly: merely
having two feeds does not guarantee update isolation. Stable publication and
Apple TV channel transition require separate explicit authorization.
