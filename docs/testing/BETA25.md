# Beta25 — corrección del lanzamiento de Rivulet

## Versiones y artefactos

- Skin AcTweeteR `1.2.32~beta11` (único complemento propio modificado).
- Service AcTweeteR `0.4.85` y XStream Pro `1.1.2.28~beta20`, sin cambios.
- Rivulet `0.36.0`; IAGL `4.0.6`, ambos sin cambios.
- Commit Beta25: `6c4fc9233ada5e1a213657df74b723c075da6f66` (`Fix Rivulet launcher in Testing Beta25`).
- SHA-256 del ZIP de Skin Beta11: `cea8a542a6c3b77473188fc186f055d656b1f5d99490fe2adfdd516f2c3f093d`.
- SHA-256 del índice Testing: `262db8a62ab2898fa718ceb183d725abdf8b785f4ec1df536fe0a2750699d5f9`.
- `addons.xml.md5`: `4f0371bc3f635b1319f5cfe1eba5630c`.
- SHA-256 del índice Stable observado sin cambios: `14adccd38d1004e3b1a547025377d1c1c091eadff95cf6233a47ebcf986bf5b1`.

## Corrección

La acción de RIVULET en el menú llamaba `ActivateWindow(Videos,plugin://plugin.video.rivulet/,return)`. Kodi rechazaba el protocolo del complemento y la navegación quedaba ocupada. Beta25 sustituye esa acción por `RunAddon(plugin.video.rivulet)`, el mecanismo de Kodi para lanzar el complemento. La acción ARCADE/IAGL y los demás complementos no cambiaron.

## Trakt y checks

| Área | Estado | Evidencia y límite |
|---|---|---|
| Código de XStream, `script.trakt` y Service | `PASS_STATIC` | La auditoría previa queda en [BETA24.md](BETA24.md). Se mantienen las responsabilidades existentes; esta corrección no añade sincronizador ni modifica almacenes. |
| Regresión de menú RIVULET | `PASS_AUTOMATED` | La suite cubre la acción en fuentes y paquete candidato. |
| Películas, series, temporadas y episodios vistos | `PARTIAL` | La suite prueba proyección local, identidades exactas, progreso e inventario; no se validó en esta sesión una muestra visual con identidad y estado confirmado. |
| Widgets, Smart Search, fichas, colecciones, favoritos y pendientes | `NOT_TESTED` visualmente | Sin cambios en esas superficies. |
| Sincronización Trakt remota | `NOT_TESTED` | No se renovó OAuth ni se hizo escritura remota. Las seis operaciones ambiguas descritas en BETA24 siguen pendientes. |

## ARCADE y Rivulet en Kodi Mac Master

- ARCADE sigue inmediatamente después de RIVULET y conserva el texto establecido. La captura de Home muestra ambos elementos sin recorte ni solapamiento.
- Rivulet `0.36.0` está habilitado; Addons33.db lo registra desde `repository.rivulet`.
- IAGL `4.0.6` está habilitado; Addons33.db lo registra desde `repository.zachmorris`.
- Al seleccionar ARCADE en la validación Beta24, Kodi abrió IAGL y mostró `IAGL-TOU.xml`. Se rechazaron los términos de Archive.org; no se descargaron ROMs ni se aceptó el acuerdo. Navegación posterior, RetroPlayer y núcleos: `NOT_TESTED`.
- Tras instalar Beta25, Kodi mostró la Home propia de Rivulet. El registro de Kodi contiene `homewindow: opening HomeWindow` y `HomeWindow shown in 0.087 s`, sin el error de protocolo observado con Beta24. No se inició reproducción ni se exploraron catálogos remotos.

## Pruebas y publicación

- Suite completa con los ZIP candidatos: `649 passed`, `0 skipped`, `69` subpruebas aprobadas. Incluye validaciones Python/AST, XML, CRC, dependencias, hashes, instalador y contrato de lanzamiento.
- ZIP de Skin generado dos veces con SHA-256 idéntico. El feed Testing y su checksum también se reprodujeron byte por byte.
- GitHub Actions para commit Beta25: instalador Beta `40151225874` y Pages `40151225685`, ambos `success`; reproducibilidad del feed `40151225859`, `success`.
- Kodi Mac Master: la tabla `installed` de `Addons33.db` marca la Skin habilitada, versión Beta11, origen `repository.actweeter.testing`, `lastUpdated=2026-10-25 02:36:57`. La instalación quedó registrada por el gestor de repositorios; no se copiaron archivos a `addons/`. Service y XStream conservan versiones Beta24.
- El arranque de Kodi cargó Skin Beta11. La prueba runtime de RIVULET llegó a su ventana propia. No se volvieron a recorrer los flujos de Trakt, PVR ni reproducción.
- Stable no aparece en el diff de Beta25. Su índice local mantiene SHA-256 `14adccd3…bf5b1`.

## Incidencias y límites

- Los workflows de verificación Stable `40151225827`, `40151225837` y `40151225831` fallaron al comparar el repositorio Stable con manifiestos/paquetes reproducidos. En particular, la ejecución Stable reconstruye `addons.xml` con SHA-256 `ca6781c5c0c7723a2c79681d4ffef85bf8780d8a6588d6e0f767cafd8780e839`, que difiere del índice Stable presente. No se modificó ni se intentó reparar Stable; la causa exacta del desacuerdo del manifiesto sigue pendiente.
- Los checks visuales de Trakt y la sincronización remota no quedan certificados por esta Beta.
- IAGL se detuvo antes de aceptar sus términos, por lo que no se probó la navegación interna o RetroPlayer. PVR solo tiene evidencia previa de carga de canales/EPG, sin prueba manual de reproducción.

## Clasificación

- RIVULET: `PASS_AUTOMATED` y `PASS_RUNTIME` para lanzamiento y carga de su HomeWindow.
- ARCADE: `PASS_RUNTIME` hasta la pantalla legal; navegación interna `NOT_TESTED`.
- Checks Trakt: `PARTIAL` / `NOT_TESTED` en pantalla; sincronización remota `NOT_TESTED`.
- Publicación Beta25: `PASS_AUTOMATED`; instalación registrada desde Testing y Rivulet `PASS_RUNTIME`.
- Stable: sin cambios intencionados ni archivos Stable en el commit Beta25; auditoría CI Stable `FAIL` por discrepancia de reproducibilidad descrita arriba.
