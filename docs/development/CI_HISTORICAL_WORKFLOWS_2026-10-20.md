# Historical GitHub Actions verification after Stable promotions

Prior GitHub Actions reproducibility jobs falsely treated the current Stable addons.xml as an immutable historical artifact. The live Stable index is intentionally rolling. Old versioned ZIPs and their pinned release manifests are immutable.

The fixed jobs continue to rebuild and compare the historical ZIPs, and 0.4.30/0.4.31 assert reconstructed historical index SHA-256/MD5 against their pinned release manifests. The original versions of all these packages remain available for rollbacks.

Historical source tests still confirm their archived candidate ZIP identities. They additionally compare the current Stable index to the current immutable unified Stable manifest rather than assuming historical versions are still live.

Beta11 runs from a pinned 2026-10-19 commit, so comparing its entire Stable directory against modern main is invalid. The workflow now compares only historical versioned ZIPs that must remain byte-for-byte identical in current main. Its original local Testing index and ZIP comparisons still run.

Current live Stable and Testing artifacts are separately covered by unified-stable-release.yml and installer-beta.yml. Do not silence historical tests or alter historical ZIPs to resolve CI failures. When a new Stable release is promoted, live index verification must update the active release manifest.

No add-on, repository feed, ZIP, or device configuration is changed by this CI-only patch.
