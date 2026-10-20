# AcTweeteR unified Testing candidate — 2026-10-20

**Channel:** AcTweeteR Testing, version 1.0.2 (unchanged).

| Add-on | Testing candidate |
|---|---|
| Service | 0.4.44 |
| Skin | 1.2.30~beta2 |
| XStream Pro | 1.1.2.10 |

The candidate reconciles Lenovo Beta guarded autoplay and discovery with Mac Master manual SlyGuy movie/series trailer actions. It retains the optional preview guards, preserves Kodi's global update preference, and records premium series baselines before the UI filter.

The official rolling Testing index is located at [repo/addons.xml](repo/addons.xml) and its checksum at [repo/addons.xml.md5](repo/addons.xml.md5). Pinned SHA-256 checksums for all packages are in [the release manifest](https://github.com/AcTweeteR/TwT-Actualizador/blob/main/manifests/0.4.44-unified-beta-20261020.json).

**Important:** The packages have passed source-level tests and ZIP checks, but have not passed real playback/UI tests on the candidate. Test on Lenovo first, keeping the existing Kodi profile, IPTV and Trakt data. Take a complete restore-capable backup before installing. Do not update the Mac Master or promote this candidate to Stable until Lenovo runtime acceptance.

Enabling Testing alongside Stable may present competing sources for the same add-on. Explicitly select **AcTweeteR Testing Repository** for the candidate update and verify installed versions. If Kodi automatic add-on updates are enabled, publishing newer candidate versions can trigger background updates on devices with Testing enabled. Do not change the global update policy as part of this release.

To revert, restore a verified pre-deployment backup, including add-on data and skin menu, rather than simply downgrading ZIPs. Trakt sessions, passwords, and watch histories must not be copied between devices.

XStream Pro is an independently modified distribution of upstream 1.1.2, subject to its CC BY-NC 4.0 license. No credentials or profile data are bundled.
