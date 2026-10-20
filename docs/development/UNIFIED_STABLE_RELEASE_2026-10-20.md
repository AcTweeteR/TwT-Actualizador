# AcTweeteR Stable 1.2.30 / Service 0.4.45 / XStream Pro 1.1.2.10

This release promotes the unified Mac/Android Testing candidate with one intentional change to the skin: 1.2.30~beta2 becomes 1.2.30, with a new stable changelog. All 381 other non-manifest skin files and the beta changelog are byte-for-byte unchanged. Service 0.4.45 and XStream Pro 1.1.2.10 ZIPs are identical to Testing.

- Existing Stable repository installer remains 1.0.3. Kodi users with it installed can refresh the repository index; no repository reinstall is necessary.
- Stable is published in `repo/`; Testing remains untouched in `docs/testing/`.
- The Mac Master runtime checks passed, including IPTV playback, widgets, movies/series navigation, trailers and all mandatory setup gates.
- Android clean install and Service 0.4.45 update were confirmed by the owner.
- Lenovo retains the packages from the prior Testing candidate but full runtime QA is still pending.
- External SlyGuy provider HTTP 429 is not guaranteed preventable by AcTweeteR.
- Trakt credentials, Kodi user profile files and provider configuration are not included in any ZIP.

The release builder `tools/build_stable_channel.py` pins all four source ZIP hashes and refuses to overwrite the existing output directory. CI must reproduce all three Stable artifacts byte for byte. The release manifest records SHA-256 checksums.

Repositories can both offer add-ons with the same IDs. Device owners should choose the desired channel explicitly and avoid unintended automatic updates from Testing.
