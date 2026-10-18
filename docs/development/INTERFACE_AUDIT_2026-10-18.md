# AcTweeteR interface audit — 2026-10-18

## Baseline and scope

Worktree: `codex/beta-widget-horizontal-navigation`, based on the current
Beta 8 snapshot (`1e1bfb211dad78dd42520b556c5d8c7cc7143866`). The initial
workspace guard passed with a clean tree. This change is limited to default
menu data, the lower menu's viewport, tests, and this audit note. No profile,
generated menu, Stable feed, third-party add-on, or device configuration is
written by these source changes.

## Menu contract: source finding and change

`source/0.4.32/addons/skin.actweeter/shortcuts/mainmenu.DATA.xml` previously
defined eight defaults, including `Canales recientes`, `Ajustes`, and
`Actualizar Catálogo`. `IncludesBingie.xml` renders the generated main menu
in control 900 and a distinct generated power-menu list in control 40003.
Consequently, keeping Settings/catalog refresh in the main data creates the
wrong menu contract and duplicates Settings in the lower area.

The source defaults now have exactly five main destinations: INICIO, TV,
PELÍCULAS, SERIES, BUSCAR. The separate lower menu now has exactly AJUSTES,
RECARGAR CATÁLOGO, RECARGAR, using the existing Kodi Settings action, the
existing AcTweeteR catalog-refresh callback, and Kodi's `ReloadSkin()` action.
No provider path was invented. The lower list's source viewport is 165px for
three existing 55px rows and is positioned at y=909 in the 1080i coordinate
space, keeping its bottom at y=1074.

Skin Shortcuts persists generated menu source documents in
`userdata/addon_data/script.skinshortcuts` and builds the active includes from
those copies. The service migration is now layout v13 and reconciles the
`mainmenu` and `powermenu` documents with a verified backup. It updates only
previously tracked bytes or the exact Beta 8 default SHA-256 values; any other
bytes produce `CONSENT_REQUIRED` and are preserved unless the user explicitly
approves. The power menu is also added to the structural profile-sync
manifest. Migration is idempotent and uses the existing bounded Skin Shortcuts
build workflow.

On Lenovo, the existing main-menu DATA file's hash was read without revealing
its content and matched the exact Beta 8 default (`b192494c…f3323`). The
profile had no power-menu DATA copy. Thus the current main menu is eligible for
automatic migration and the lower defaults can be seeded. This verifies
eligibility only: the Beta9 package has not yet run on the device.

## Runtime evidence collected in this session

On the authorized Lenovo Kodi 21.3 runtime, DPAD navigation moved focus from
Inicio to TV and selecting TV opened the native PVR guide. The guide rendered
channels and schedule entries. This verifies the current TV destination and
visible EPG route for the installed Beta 8 build; no channel playback was
started. It does not validate the changed menu data, since the candidate has
not been installed or rebuilt on the device.

The Home screenshot from this session showed populated Spotlight and widget
rows. Previously recorded Beta 3 evidence in `BETA_WIDGET_NAVIGATION.md`
documents sampled horizontal navigation, poster-to-info selection and
EXPANDIR behavior, but those observations predate Beta 8 and are not treated
as current-version acceptance.

## Feature status matrix

| Area | Status | Evidence / boundary |
| --- | --- | --- |
| Home data present | PASS_RUNTIME (observed) | Populated Home was visible on Lenovo; no performance claim. |
| TV destination / EPG | PASS_RUNTIME (observed) | DPAD selection opened TV guide with channels and schedule. |
| Exact five + three menu defaults | PASS_AUTOMATED | XML tests verify labels, order, destinations and actions. |
| Three lower rows fit source viewport | PASS_STATIC | 3 × 55px = 165px; bounds 909–1074 in 1080i coordinates. |
| Lenovo profile eligible for default migration | PASS_STATIC | Read-only hash matches Beta 8 default; lower DATA absent. |
| Existing Lenovo profile migrated to new menu | NOT_TESTED | Candidate not yet installed from official Beta feed. |
| Movies / series destinations in this run | NOT_TESTED | No runtime navigation performed after edits. |
| Touch detail buttons / trailers | NOT_TESTED | This work follows the user's switch away from touch debugging. |
| Collections, badges, profile isolation | NOT_TESTED | No runtime acceptance in this session. |
| Vertical scroll, horizontal scroll, EXPANDIR | NOT_TESTED for Beta 8 | Older Beta 3 evidence is retained as historical only. |
| Stable channel | UNCHANGED | No Stable files or feed artifacts modified. |

## Automated validation

- `python3 -m unittest discover -s source/0.4.32/tests -p 'test_menu_contract.py' -v` — 10 PASS.
- `python3 -m unittest discover -s source/0.4.32/tests -q` — 72 PASS.
- XML parser — mainmenu, powermenu, and `IncludesBingie.xml` PASS.
- `git diff --check` — PASS.

Reproducible local Beta9 packages were built in a temporary directory:
service 0.4.37 SHA-256 `2c98974f…05e004`, skin 1.2.29~beta9 SHA-256
`c0620714…f8f1a74e`; both ZIP CRC checks passed. The generated Testing index
announces repository 1.0.0, service 0.4.37 and skin 1.2.29~beta9; its MD5
matches the index bytes. These artifacts are not published. Next gate: publish
only to the official Testing feed, update Lenovo through Kodi, then verify the
migration and DPAD navigation. Stable remains unchanged.
