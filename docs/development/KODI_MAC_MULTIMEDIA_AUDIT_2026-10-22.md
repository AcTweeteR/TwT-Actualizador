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
