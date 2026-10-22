# Kodi Mac — multimedia regression audit (2026-10-22)

Real installed Kodi 21.3; XStream 1.1.2.20~beta1, service 0.4.54. Inspected through local Kodi JSON-RPC on loopback port 9090, without changing Kodi settings or credentials.

- `PVR.GetProperties`: available=true. 92 TV channel groups; 1776 channels in all-channels group.
- `Player.Open(channelid=2709)`: PASS. `Player.GetActivePlayers`: internal video player, speed=1, channel La 1; stopped successfully after brief playback.
- `GUI.ActivateWindow(videos, plugin://plugin.video.xstream-pro/?mode=premium&view=collections_root&stype=movie|series&profile_num=1)`: PASS for both media types, showing Favoritos, Pendientes, Mis listas (3 items).
- Movie catalog `view=catalog&stype=movie`: PASS, 24 visible entries. Selected first movie; after load, active internal video player, fullscreen, VideoPlayer.VideoCodec=h264, Player.Time=00:00:13; stopped successfully.
- Series catalog `view=catalog&stype=series`: PASS, 24 entries. Opened first series to Temporada 1, then first season to two episodes; source-select route includes verified TMDb ID. Episode playback NOT tested.
- `view=favorites|pending` movie and series: PASS navigation; movie favorites/pending empty, series pending empty, series favorites retains Medusa. No mutations performed.
- Episode context menu opens; first action `Agregar a favoritos del perfil`. No modification made.
- Tráilers and widget expansion were not functionally exercised in this pass; no PASS claimed.
- 413/413 automated tests PASS after the runtime checks. `git diff --check` PASS.

Remote bidirectional Trakt/TMDb sync is NOT implemented end-to-end or authorized for writes. No remote write, release, repository update, Lenovo deployment, or Stable modification occurred. Preexisting unrelated worktree changes remain untouched.

## Continued runtime verification

- XStream `VisionQuest` S01E01: selected from real Kodi series season listing, entered fullscreen playback, H.264, playback time ~14 seconds at speed 1. **Episode playback PASS**; stopped immediately after verifying.
- Expanded XStream catalog `view=catalog&actweeter_expand=1&limit=19`: movies and series both return 19 media items plus red `[COLOR FFE50914]EXPANDIR[/COLOR]` item at index 19 (20 total). Selecting Expand in series opens browse route `browse=1&limit=48`, 49 total items. **Route and click PASS**; pixel-level clipping not verified.
- Installed skin `IncludesFunctions.xml`, `IncludesHomeWidgets.xml`, `IncludesBingie.xml` parse as valid XML. `slyguy.trailers` installed. Manual trailer XML contains guarded movie/TV actions. 5 unification and 17 widget metadata tests PASS. **Manual trailer actual playback not verified**; do not claim PASS.
- No source changes were needed from these runtime checks. No remote account writes, skin changes, or other user data mutations.
