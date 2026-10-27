# Beta33 — cierre de instalación y puerta Stable (2026-10-27)

## Estado

Beta33 está publicada en Testing e instalada en Kodi Mac Master mediante el gestor nativo. Stable **no** se publicó: faltan pruebas reales obligatorias en Lenovo y Apple TV, y el autoplay todavía no ha reproducido un tráiler en una muestra real.

| Área | Estado | Evidencia |
| --- | --- | --- |
| Actualización Skin | PARTIAL | Kodi instaló `1.2.36~beta4` tras «Comprobar actualizaciones», sin seleccionar versión; no se observó descubrimiento espontáneo. |
| Actualización Service | PARTIAL | Kodi instaló `0.4.94~beta7` en la misma operación. |
| Tráilers automáticos | PARTIAL | `AUTO_PREVIEW_REQUEST_ACCEPTED` y espera de 3 s; una muestra acabó en `no_results` del proveedor, sin reproducción. |
| Tráilers manuales | PARTIAL | Reproducción fullscreen verificada en Beta32; no repetida tras Beta33. |
| Reproducción de episodios | PARTIAL | «Medusa» S01E01 reproducido, pausado, reanudado y detenido en Beta32; no repetido tras Beta33. |
| IPTV/PVR | PARTIAL | Funcionó en Mac con Beta32; no repetido tras Beta33. |
| Checks y tags | PARTIAL | Ojo y «COMPLETA» observados en Beta32; no se repitió matriz visual completa tras Beta33. |
| Trakt bidireccional | PARTIAL | Lectura autenticada comprobada previamente. Escritura real y recuperación multidispositivo no demostradas. |
| Smart Search | PARTIAL | Funcionó en Beta32; no repetido tras Beta33. |
| Kodi Mac | PARTIAL | Versiones, arranque, introducción y Home comprobados tras reinicio. [Captura](BETA33-kodi-home.png). |
| Lenovo | NO VERIFICADO | ADB de TB330FU `192.168.1.215:41583` sin respuesta. `192.168.1.30:5555` corresponde a otro dispositivo y figura offline. |
| Apple TV | NO VERIFICADO | Sin acceso operativo para prueba real de tvOS. |
| Suite automatizada | PASS_TEST | 726 aprobadas, 3 omitidas, 100 subpruebas; las omisiones son fixture ZIP upstream y puerta Stable. |
| Integridad de paquetes | PASS_TEST | ZIP/CRC, XML, AST Python, dependencias, índice y reproducibilidad comprobados para candidatos exactos. |
| Workflows Stable | PASS_TEST | Verificador Stable actual corregido; CI de verificación pasa. No se preparó promoción. |
| Beta publicada | SÍ | GitHub Pages y workflows de Testing completados. |
| Stable publicada | **NO** | Puerta de validación real incompleta. |

## Cambios y causa

`kodi_auto_preview.py` rechazaba películas o series sin TMDb/IMDb/DBID aunque Kodi tuviera título y tráiler. Ahora usa la identidad estable existente con título y año como respaldo en esos dos tipos de medio, también al comprobar que el foco sigue perteneciendo a la solicitud. `setup.py` registra correctamente la presencia de esa identidad. La prueba de regresión cubre ambas rutas. No se alteraron la base de datos ni el matching del catálogo.

Skin beta4 solo actualiza metadatos para ensayar la actualización nativa de Skin con una versión nueva. Se retiró previamente mediante la interfaz de Kodi la regla individual que impedía actualizar Skin. La consulta SQLite de solo lectura después de instalar muestra Skin, Service y XStream habilitados, todos con origen `repository.actweeter.testing` y sin reglas particulares de actualización. La comprobación explícita de Kodi instaló Skin y Service sin escogerlas una por una. Esto prueba instalación automática tras la comprobación, pero no la detección desatendida.

Los workflows históricos 0.4.29 y 0.4.31 fallaban al comparar el índice Stable **actual** de seis complementos con un manifiesto **histórico** de cuatro. Se separó esa referencia histórica y se añadió verificación del Stable actual, incluido MD5. Los dos workflows y el verificador Stable pasan en el commit final. No se cambió ningún archivo de `repo/`.

## Versiones, origen y hashes

| Complemento | Instalado en Mac tras reinicio | SHA-256 del ZIP de Testing |
| --- | --- | --- |
| Skin | `1.2.36~beta4` | `cbdd4ea4bc25f10120fbbc5f8bdecb2cb656f25e7398494412cbdf7fe095de5b` |
| Service | `0.4.94~beta7` | `685f14a8dcf6d032bef5cda7d51edf8d34873fb7583c7145cf3715bb2e177855` |
| XStream | `1.1.2.36~beta3` | `4c33c4cb52d671564e30c510edf92274f1c7ce5b27c8ea527aea2067806503b1` |

Manifiesto: [`manifests/actweeter-beta33-20261027.json`](../../manifests/actweeter-beta33-20261027.json). Índice Testing SHA-256: `f46c4792a09fad451285d35531f6c4991333d2b7e47e7fd40b71dfcd74976629`. Índice Stable antes y después: `7ce09e4d820d8c52ec697d7a2bac5451a1076eec5d89e2234072be490efe54ee`.

Rama `codex/beta33-stable-prep`; commits `a3dbcab` (fuente y paquetes), `ef9d7de` (manifiesto), `228a55f` (verificadores históricos). GitHub Pages del último commit: [run 40452972084](https://github.com/AcTweeteR/TwT-Actualizador/actions/runs/40452972084). Los workflows de instalador Beta, verificación Stable actual, 0.4.29 y 0.4.31 terminaron correctamente en `228a55f`.

## Evidencia runtime y pendientes

El registro tras el reinicio identifica las tres versiones nuevas, `AUTO_PREVIEW_COORDINATOR status=started` e `INTRO_PLAYBACK_TERMINAL event=ended`; Home apareció sin segunda introducción. Antes del reinicio, la muestra Matrix produjo `AUTO_PREVIEW_FOCUS ... identity=present`, `AUTO_PREVIEW_REQUEST_ACCEPTED ... delay=3.00` y `RESOLUTION_FINISHED ... status=no_results`. Después del reinicio otra muestra generó aceptación y cancelación al cambiar el foco. La reparación del filtro de identidad funciona; todavía falta una muestra que demuestre reproducción automática hasta el final y vuelta al foco.

No se modificaron perfiles, cachés, credenciales ni historiales. No hubo escrituras remotas en Trakt. Para abrir Kodi después del cierre hubo que invocar Launch Services fuera del sandbox de la herramienta; el lanzamiento dentro del sandbox devolvía `-10827`, mientras el lanzamiento autorizado abrió Kodi con normalidad. No hay indicio de un defecto de la instalación de Kodi por ese episodio.

Lectura directa y sin escritura de la caché IPTV: los cuatro JSON parsean correctamente y conservan 26.426 películas, 24 categorías de películas, 8.856 series y 27 categorías de series. `PRAGMA integrity_check` devolvió `ok` para `provider_search_1.sqlite` y el índice SQLite de películas. La base auxiliar `cache/xstream_cache.db` no se pudo abrir en modo lectura durante esta comprobación; no se modificó.

La promoción Stable sigue bloqueada por la puerta acordada: autoplay real completo, regresión visual posterior a Beta33, Lenovo, Apple TV y validación segura de escritura Trakt. La suite y la integridad de paquetes no sustituyen esas pruebas de dispositivo. La versión Stable anterior permanece intacta.
