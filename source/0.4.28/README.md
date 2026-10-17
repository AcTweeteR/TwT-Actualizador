# AcTweeteR 0.4.28 source snapshot

This folder is the public, profile-neutral source/build snapshot for the
published 0.4.28 Kodi packages. It derives from private source commit
`494d43b` (history through `9c418a8`) and is checked against the exact
published package hashes in the root `manifests/0.4.28.json`.

It includes the complete AcTweeteR skin, service and repository sources; the
pinned XStream upstream lock and contextual patch set; and deterministic
package/index builders. The generated
`1080i/script-skinshortcuts-includes.xml` is intentionally replaced with an
empty profile-neutral build slot. The builder generates packaged starter
includes from `tools/skinshortcuts_include_names.txt` and the portable
`shortcuts/mainmenu.DATA.xml`; no generated user profile menu is published.

## Rebuild

Use Python 3, the standard library and the `patch` utility. Download the
upstream XStream 1.1.2 release asset and verify its SHA-256 against
`third_party/xstream/upstream.json`, then run from this directory:

```sh
python3 tools/build_repository_package.py --output /tmp/repository.actweeter-1.0.3.zip
python3 tools/build_skin_package.py --output /tmp/skin.actweeter-1.2.27.zip
python3 tools/build_service_package.py --output /tmp/service.actweeter-0.4.28.zip
python3 tools/build_xstream_package.py --upstream-zip /path/to/plugin.video.xstream-pro-1.1.2.zip --output /tmp/plugin.video.xstream-pro-1.1.2.7.zip
python3 tools/build_distribution_index.py --repository-zip /tmp/repository.actweeter-1.0.3.zip --skin-zip /tmp/skin.actweeter-1.2.27.zip --service-zip /tmp/service.actweeter-0.4.28.zip --xstream-zip /tmp/plugin.video.xstream-pro-1.1.2.7.zip --output-dir /tmp/actweeter-index
```

Compare the resulting hashes and index bytes with the published files and
manifest. The root workflow `Verify 0.4.28 reproducibility` repeats the build
and comparison on pushes and pull requests. A reproducible package build is
not Kodi runtime validation.

## Third-party terms

XStream Pro is by PesicP and licensed CC BY-NC 4.0. The builder fetches the
upstream archive by pinned release URL/hash, retains its license, applies the
identified AcTweeteR changes and includes a modification notice. Sharing and
adaptation remain limited to non-commercial use under that license; this is
not an upstream-endorsed build. See the root `THIRD_PARTY_NOTICES.md`.
