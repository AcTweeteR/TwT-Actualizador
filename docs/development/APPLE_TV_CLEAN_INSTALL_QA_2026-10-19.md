# Apple TV 4K — clean Kodi 21.3 AcTweeteR Beta installation gate

Status: **WAITING_FOR_DEVICE**. Apple TV is operated by its owner. Do not modify macOS Kodi Master, existing tvOS app signatures, sideload certificates or the stable release feed.

## Verified distribution facts (2026-10-19)

- Live Beta index responds HTTP 200 at `https://actweeter.github.io/TwT-Actualizador/testing/repo/addons.xml`.
- Live repository ZIP responds HTTP 200 at `https://actweeter.github.io/TwT-Actualizador/testing/repo/repository.actweeter.testing/repository.actweeter.testing-1.0.0.zip`.
- Live service 0.4.37 ZIP SHA-256: `2c98974fe5f2c42e9e71db368f8ffcd2cd73bb44e073faaf54d56be0c605e004`.
- Live skin 1.2.29~beta10 ZIP SHA-256: `4387012a8d6b928dfc665ef4b48a06773149295ca36937ec35e43e728dc2b808`.
- A newly built local candidate has different ZIP bytes but the **same version identifiers**. It is **not published** and must not overwrite the historical Beta10 artifacts. Assign new versions and re-run compatibility/release tests before distribution.

## Clean-install instructions for owner

1. Verify the Apple TV has a working, signed **Kodi 21.3 tvOS** installation, launched at least once. If uninstalling Kodi to reset, first export/backup any tvOS data the owner wishes to keep. Kodi tvOS sideload signing and app renewal are separate from AcTweeteR repository installation.
2. In Kodi, go to **Settings > System > Add-ons** and allow installation from unknown sources only if Kodi requests it and the owner accepts the security implications. Avoid installing unrelated repositories.
3. Use Kodi's **File manager > Add source** to add `https://actweeter.github.io/TwT-Actualizador/testing/bootstrap/` if the built-in ZIP browser can access HTTPS directories. If directory browsing is unsupported on tvOS, use an HTTPS-accessible ZIP source through Kodi's supported file manager or a user-controlled SMB/WebDAV share; do not assume an IPA or macOS ZIP can be opened by the tvOS installer.
4. In **Add-ons > Install from zip file**, select `repository.actweeter.testing-1.0.0.zip`. Verify Kodi confirms installation.
5. Run **Install from repository > AcTweeteR Testing Repository** and locate `skin.actweeter` (Beta10) and `service.actweeter` (0.4.37). Install the skin using Kodi's dependency resolver. Record the exact first missing dependency or platform error if installation fails; do not manually copy addon directories or silently replace binaries.
6. If installation completes, open the skin and first-run wizard. Test: Home spotlight, sidebar/remote focus, PVR channel open/stop, Xtream login and VOD listing, movie playback, episode resume/play/stop, manual trailer, automatic preview (only if enabled), Search, Back, cold restart, and persistence of settings. Never include Xtream credentials or signed stream URLs in shared logs.
7. Record installed versions and any missing addons. Test **update/rollback only after a newly versioned candidate is published**, and after backing up tvOS Kodi userdata. Keep stable and Beta feeds isolated.

## Device-specific risks and release blockers

- tvOS does not necessarily expose the same addon binaries or filesystem permissions as macOS; the service requires PVR IPTV Simple, YouTube and XStream, and the skin also requires Bingie helper/toolbox/widgets, Skin Shortcuts, TMDb helper, autocompletion and resource addons. Confirm availability on tvOS; do not mark clean install PASS based on ZIP CRC.
- The Beta testing repository also lists the official stable feed; its name alone does not establish isolation of dependencies or versions. Do not enable Kodi global auto-updates.
- tvOS sideloaded Kodi can be removed or expire with signing/provisioning; repository ZIP installation cannot fix an invalid app signature.
- The selective AcTweeteR-only auto-updater is still unimplemented. No claim of automatic future updates until tested.

## Evidence checklist

- [ ] Kodi 21.3 tvOS launched cleanly
- [ ] Test repository ZIP installed through Kodi
- [ ] Skin/service/XStream and mandatory dependencies resolved through Kodi
- [ ] First-run wizard finished and persisted
- [ ] TV, movie, series episode and trailer playback/stop verified
- [ ] Search, navigation and cold restart verified
- [ ] New-version update verified without loss of data
- [ ] Failed-update recovery verified
- [ ] Third-party addons not auto-updated; approved first-party updates verified

**Do not close QA or publish Stable until the checks are evidenced.**

## tvOS clean-install failure: unresolved dependencies (owner screenshot 2026-10-19)

**FAIL_RUNTIME_INSTALL**: Kodi displayed `Not available` for `slyguy.trailers`, `plugin.video.tmdb.bingie.helper`, `script.bingie.helper`, `script.bingie.toolbox`, `script.bingie.widgets` when installing the skin. The Beta bootstrap repository advertises only the Beta and Stable AcTweeteR indexes, which contain just four addon entries each. The stable `repository.actweeter` ZIP advertises additional Matke BINGIE and SlyGuy feeds; the Beta bootstrap does not. Both upstream XML endpoints responded HTTP 200 when checked on the Mac, but that does not prove tvOS can install every addon. **Do not claim a successful clean install**. Remediation: new-version Beta bootstrap with vetted, accessible dependency feeds or self-hosted version-pinned, license-compliant dependencies; verify transitive dependencies and tvOS compatibility; regenerate ZIP/index, publish a new immutable version and retest from clean Kodi. Do not overwrite historical `repository.actweeter.testing-1.0.0.zip`.
