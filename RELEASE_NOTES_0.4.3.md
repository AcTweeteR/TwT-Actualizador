# AcTweeteR Service 0.4.3 — Stable

Kodi 21.3 Omega service update for AcTweeteR.

## Included

- Resumable setup and diagnostics for the declared component catalogue.
- Provider-specific XStream/PVR verification and preservation of existing
  provider configuration during retries.
- Typed XStream profile boolean-setting writes, read-back verification, and
  rollback of prior values on failure.
- Defensive handling of `HTTPError` objects without an underlying response
  body.

## Validation and limitations

- Automated suite: 416 tests passed.
- Earlier runtime results communicated for setup, IPTV authentication, VOD,
  episodes, PVR/live TV, EPG, persistence, and manual trailers are retained as
  prior QA evidence; these were not repeated for this release.
- A clean isolated Kodi install remains **NOT TESTED**. The Kodi QA app did not
  initialize, so this release makes no new runtime claim for that environment.
- Android TV and tvOS runtime compatibility remain unverified.

The add-on package contains AcTweeteR's GPL-2.0-or-later service code. The
separately distributed XStream Pro 1.1.2 package remains under CC BY-NC 4.0,
with attribution and its modification notice retained; non-commercial use only.
