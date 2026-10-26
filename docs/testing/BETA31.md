# Beta31 — checks de episodios y actualización automática de Service

Fecha: 2026-10-26. Rama: `codex/beta28-trakt-recovery`. Commit de código y publicación: `7ca5fc0dca35cff03cd7a462baa6651ee0eee5ca`. Resultado global: **PARTIAL**.

## Corrección y causa

En Smart Search, Service confiaba en el `playcount` genérico de `Files.GetDirectory` para episodios y temporadas. En Kodi Mac Master, los diez episodios de la temporada 1 de **Tierra de mafiosos (2025)** llegaban con `playcount=1`, mientras el historial local del perfil solo tenía cinco episodios vistos. El resultado visible eran diez checks falsos. `WatchedState.badge` ahora consulta el JSON persistido del perfil y el inventario del proveedor; un estado exacto de episodio TMDb tiene prioridad. Una temporada no hereda un check por el `playcount` de su carpeta. Se añadió una prueba de regresión en `source/0.4.32/tests/test_smart_search.py`. El cambio no sustituye la base de datos ni los catálogos IPTV.

El cuadro de Smart Search también tenía un marcador duplicado en Android; se corrigió en `source/0.4.32/addons/service.actweeter/resources/skins/Default/1080i/AcTweeteRSearch.xml`. La comprobación en Android es estática; no se probó allí en runtime.

El bloqueo anterior de actualización automática de Service procedía de la opción individual **Auto actualizar** desactivada en Kodi (`update_rules=1`). Se activó desde la interfaz nativa, sin modificar SQLite ni la preferencia global. Después de publicar beta4, Kodi instaló Service automáticamente desde Testing, sin refresco manual del repositorio ni selección manual de versión. No se detectó una incompatibilidad de comparación de versiones `~beta` en este ciclo.

## Publicación e instalación

| Complemento | Versión instalada en Kodi Mac | Origen en Addons33.db | Estado |
|---|---|---|---|
| Skin | `1.2.36~beta2` | `repository.actweeter.testing` | Sin cambios |
| Service | `0.4.94~beta4` | `repository.actweeter.testing` | `PASS_RUNTIME`, actualización automática |
| XStream Pro | `1.1.2.36~beta3` | `repository.actweeter.testing` | Sin cambios |

Los tres están habilitados. La tabla `update_rules` ya no tiene una regla para Service. `kodi.log` registró `service.actweeter v0.4.94~beta4 installed` el 26-10-2026 a las 12:16:59. [Captura del gestor](evidence-beta31/service-auto-updated.png).

ZIP de Service: SHA-256 `cc3ad29d4c3e27570c8be8b2d33bb18f61d7afb2e7da24fd21676a10f0821ce3`. Índice Testing: SHA-256 `cd8fb2ea6335ad3d7bca2cd1645e2e44566bdd212745ce5339788348516e6495`. Ambos coincidieron con los archivos servidos por GitHub Pages. Dos construcciones consecutivas generaron ZIP y feed idénticos; el feed completo contenía 21 archivos idénticos. El ZIP upstream de XStream mantuvo el hash fijado `915f45708670d07e789bb73b7390a7b5cf30175f818ef5da8ea18c9f13f537fe`.

CI del commit: [instalador](https://github.com/AcTweeteR/TwT-Actualizador/actions/runs/40313612747), [candidato XStream](https://github.com/AcTweeteR/TwT-Actualizador/actions/runs/40313612643), [ruta Beta](https://github.com/AcTweeteR/TwT-Actualizador/actions/runs/40313612787), [reproducibilidad Testing](https://github.com/AcTweeteR/TwT-Actualizador/actions/runs/40313612758) y [Pages](https://github.com/AcTweeteR/TwT-Actualizador/actions/runs/40313612009) terminaron con éxito. Tres verificaciones históricas de Stable siguen fallando por su discrepancia de manifiesto anterior; no se interpretan como CI global correcto.

## Pruebas y evidencia de Kodi Mac Master

| Área | Resultado | Evidencia y alcance |
|---|---|---|
| Checks de películas | `PASS_RUNTIME` para muestra Beta30 | El corredor del laberinto (2014) visto; secuelas no vistas y Chappie (2015) sin falso positivo. Ver [BETA30](BETA30.md). No se repitió esta muestra tras beta4. |
| Checks de serie/temporada | `PASS_RUNTIME` para muestra parcial | Tierra de mafiosos: temporadas 1 y 2 sin check completo. [Antes](evidence-beta31/tierra-seasons.png). |
| Checks de episodios | `PASS_RUNTIME` para muestra corregida | Temporada 1: E1, E2, E3, E4 y E7 con check; E5, E6, E8, E9 y E10 sin check. Coincide con el JSON local. [Antes: diez checks falsos](evidence-beta31/tierra-episodes-s1.png) · [Después: cinco correctos](evidence-beta31/tierra-episodes-s1-after.png). Temporada 2: cinco episodios sin check. [Captura](evidence-beta31/tierra-episodes-s2-after.png). |
| Smart Search | `PASS_RUNTIME` para navegación de esta serie | Búsqueda, apertura del resultado IPTV, temporadas y episodios desde la interfaz real. La vuelta al listado restauró resultados sin repetir consultas. |
| Actualización automática Service | `PASS_RUNTIME` | Instalación espontánea de beta4 desde Testing después de retirar la regla individual mediante la UI; versión y origen corroborados en `addon.xml` y SQLite en modo lectura. |
| Trakt lectura | `PASS_RUNTIME` de solo lectura | Consulta autenticada real: 20 películas vistas en la página consultada, 18 series, seis progresos de películas, uno de episodio y recomendaciones. La cuenta/token no se imprimió. |
| Trakt escritura y bidireccionalidad | `NO VERIFICADO` | No se hizo escritura remota ni se demostró restauración en instalación nueva; las operaciones ambiguas se conservaron. |
| IPTV/VOD/PVR y tráilers | `NO VERIFICADO` en beta4 | No hubo reproducción real ni prueba visual de tráiler posteriores a esta instalación. |
| Persistencia tras segundo reinicio | `NO VERIFICADO` | Se comprobó el estado instalado y el historial local; no se confirmó un ciclo completo de cierre y nuevo arranque de Kodi tras beta4. |
| Android/tvOS | `NO VERIFICADO` en dispositivo | No se modificaron Lenovo ni Apple TV. |

Suite completa con los ZIP candidatos exactos: **717 passed, 1 skipped, 4 deselected, 96 subtests**. La omisión y las cuatro exclusiones son contratos de Stable fuera del alcance de Testing. ZIP CRC, 74 archivos Python AST, tres XML y checksum del índice pasaron. En el tramo de log de la instalación beta4 revisado no hubo líneas `ERROR` ni `EXCEPTION` a las 12:xx; esto no equivale a una auditoría de todos los logs ni de todas las funciones.

## Integridad y límites

`repo/addons.xml` Stable conserva SHA-256 `7ce09e4d820d8c52ec697d7a2bac5451a1076eec5d89e2234072be490efe54ee`; `repo/` no cambió. No se hicieron escrituras en Trakt ni instalaciones directas en complementos, ni se alteraron perfiles, catálogos, Lenovo o Apple TV.

La corrección queda demostrada para los episodios de la muestra en Smart Search y para la actualización automática de Service. Quedan pendientes la validación visual de widgets y colecciones, una muestra de temporada completa, reproducción real IPTV/VOD/PVR, tráilers, persistencia tras reinicio confirmado y pruebas de sincronización remota de escritura segura. Por ello no se declara PASS global.
