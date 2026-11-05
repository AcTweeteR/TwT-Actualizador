# AcTweeteR Beta4 — verificación independiente 2026-11-05

- Rama: `codex/stabilization-20261105`; commit: `3d4cfd6`.
- Testing público ofrece `service.actweeter` `0.4.99~beta4`; SHA-256 del ZIP público y local: `750ce627ae200fda96de96779ce24a4f8f2d6d034a16b5a9ded0141b843f89a1`.
- Kodi Master macOS tiene instalada la misma versión Service.
- Suite completa con dependencias de Python aisladas y variables de paquete correctas: **900 pruebas, 0 fallos, 4 omitidas**.
- Suite Trakt focalizada: 267 PASS. Integridad de vistos: 19 PASS. Setup: 23 PASS. Preview: 21 PASS. Política Rivulet: 4 PASS.
- La consulta HTTP del Apple TV `192.168.1.31:8080` falló: puerto inaccesible durante esta revisión. No se validó la corrección Rivulet ni autoplay en tvOS.
- La Lenovo no se ha validado en esta revisión.
- Estado Stable público observado: Skin 1.2.41, Service 0.4.98, XStream 1.1.2.41; sin promoción nueva.
- Bloqueadores de promoción: validar tvOS y conservar pruebas reales de actualizaciones en hardware objetivo. La suite automática no demuestra esas propiedades.
- No se han alterado los perfiles Kodi, los tokens Trakt ni los ajustes de Rivulet en esta revisión.
