# Beta26 — candidatos y validación previa a publicación

## Versiones candidatas

- Skin `1.2.32~beta12` — SHA-256 `d29efb7cf094fe55c9a3327bbd71a5db5eb70298a0ced8fe59b25cb85a0cc5ed`.
- Service `0.4.86` — SHA-256 `f4ff23b309771e050c68937ccc4dd2dae3b8e819e6fa2d28c4bc07fa05dacb1e`.
- XStream `1.1.2.28~beta21` — SHA-256 `fa7256bc64dd82318e2eaa498fa53cacb12b92ff410eb62535822117dad5c065`.
- Testing `addons.xml` — SHA-256 `a908baa392e6f161d4045002709c704d29a3863c77a2e016ba202004e443c108`.

## Verificaciones

- Suite sobre ZIPs candidatos exactos: **663 passed, 73 subtests passed, 4 deselected** (pruebas históricas que reconstruyen Stable). Cero fallos.
- CRC de paquetes Service y Skin correcto; XStream compilado y validado contra fuente upstream fijada.
- Índice Testing generado dos veces y comparado byte a byte: PASS.
- Stable `repo/addons.xml` conserva SHA-256 `14adccd38d1004e3b1a547025377d1c1c091eadff95cf6233a47ebcf986bf5b1`.
- Se actualizaron contratos de tests para `tmdb_watched_state`, el contexto `_CTX` y Service 0.4.86; no se eliminaron las aserciones de seguridad de identidad.

## Limitaciones y comprobaciones pendientes

- Publicación remota, CI y actualización de Kodi Mac Master: **PENDIENTE**.
- Checks Trakt visuales con identidades reales: **NO VERIFICADO**.
- Sincronización Trakt remota y escritura bidireccional: **NO VERIFICADO**; no se ha escrito en Trakt.
- IAGL: en Beta25 abrió términos legales; navegación interna y RetroPlayer siguen **NO VERIFICADOS**; no se aceptan términos automáticamente.
- Reproducción IPTV/PVR/VOD/series: **NO VERIFICADA** en esta ejecución.
- Las cuatro pruebas históricas de reconstrucción Stable fueron excluidas, no declaradas PASS.

**Estado:** PASS automatizado / PARTIAL funcional hasta completar pruebas runtime.
