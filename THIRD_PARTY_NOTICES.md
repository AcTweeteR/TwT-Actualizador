# Third-party notices

AcTweeteR skin 1.1.3 is a modified derivative of **BINGIE by Matke** (Omega
line 2.0.2): <https://github.com/matke-84/skin.bingie>. The upstream add-on
metadata declares GPL v2. The complete GPL text remains inside the skin ZIP as
`skin.actweeter/LICENSE`. AcTweeteR is not endorsed by the upstream authors.

The bundled Inter font files are Copyright (c) 2016 The Inter Project Authors
and licensed under SIL Open Font License 1.1; its complete text is included at
`skin.actweeter/fonts/OFL.txt`. They are not relicensed under GPL.

The local 1.1.0 package also contained Netflix Sans and Impact font binaries.
No redistribution grant for those files was established, so they are omitted
from this public distribution and their skin font references use Inter instead.
No Netflix Sans or Impact font binary is published here.

Kodi and all helpers/dependencies are separate upstream add-ons and retain
their own authorship, terms and update channels. They are not copied into this
repository. This notice identifies known direct origins for this artifact; it
is not a complete code-level reuse audit, which remains a later project phase.

`repo/upstream-bingie/addons.xml` is a filtered metadata-only snapshot of the
public Bingie Omega repository index (<https://github.com/matke-84/repository.bingie>),
limited to dependency records required directly or transitively by the skin.
It contains no helper source or binary; Kodi downloads those packages directly
from the upstream repository. The snapshot is manually refreshed for a future
authorized repository release.

## Dependency source/license notes for 1.1.2

`plugin.program.autocompletion` is obtained from Kodi's official Omega
repository (minimum 2.1.2). Its upstream metadata credits Philipp Temminghoff,
sualfred, xulek and finkleandeinhorn and declares GPL-2.0-or-later.
`resource.images.studios.coloured` is obtained from Kodi's official Omega
repository (minimum 0.0.24; provider Team Kodi); its addon.xml has no explicit
license field. Neither dependency is copied into this repository. The higher
version Studio Icons - Coloured - Modded fork is not bundled or redistributed;
its upstream README states the supplied textures are for non-commercial use.
AcTweeteR makes no separate licensing claim for the dependency artwork.

## Historical notes for 1.1.3

`service.actweeter 0.1.0` is AcTweeteR-maintained code distributed under
GPL-2.0-or-later; its complete license text is included in the service ZIP.
The skin's upstream BINGIE notices, GPL text, and Inter/OFL notices remain in
the skin ZIP.

XStream Pro 1.1.2 and its local AcTweeteR patch were not included in the
original 1.1.3 artifact. The current catalog entry, added on 2026-10-12, is
documented separately below and distributed under the upstream CC BY-NC 4.0
terms. Kodi, PVR and other dependencies retain their own upstream licenses and
update sources.


## XStream Pro upstream 1.1.2 and AcTweeteR revisions 1.1.2.4–1.1.2.5

This repository carries XStream Pro distribution revision 1.1.2.4, based on upstream tag 1.1.2. Upstream: [PesicP/XStreamPro](https://github.com/Pesicp/XStreamPro/tree/1.1.2), commit `1aa3e67da7c03c6acc3ec7e1ca579a7f645220f4`. The ZIP retains `LICENCE.txt`, which grants sharing/adaptation under **CC BY-NC 4.0**; it also contains `ACTWEETER_MODIFICATIONS.txt` identifying the changes. This distribution is not endorsed by the upstream author. The material may not be used commercially. Link to the full license: https://creativecommons.org/licenses/by-nc/4.0/ . Attribution, license notice and change notice remain in the package.

Revision 1.1.2.2 added a strict exact-TMDb provider-availability filter. Revision 1.1.2.3 preserves that behavior and corrects patch placement using unique source context. Revision 1.1.2.4 adds Kodi VideoInfoTag and `script.trakt.ids` playback metadata for movies and episodes; it does not add OAuth or scrobbling code. Revision 1.1.2.5 replaces per-provider-item index SELECTs with one prior-row scan per content type inside the existing transaction; it adds no database schema and preserves provider-ID reconciliation. The package builder syntax-checks Python sources before packaging and checks Python members in the resulting ZIP. The package includes `ACTWEETER_MODIFICATIONS.txt` documenting the local patch set. No upstream license or copyright notice is removed. The Tabler Icons attribution and MIT notice remain in its license file. Its declared Kodi dependencies are resolved from the Kodi repository; no separate third-party dependency ZIPs are bundled here. This catalog's package snapshot is maintained by AcTweeteR for compatibility and is distinct from upstream's release/update channel.
