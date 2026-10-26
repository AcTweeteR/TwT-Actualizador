# Beta30 — matching, checks y validación en Kodi Mac Master

Fecha: 2026-10-26. Rama: `codex/beta28-trakt-recovery`. Commit funcional publicado: `3905ea899106bc3431621dbab3f884eb91e57d8d`. Resultado global: **PARTIAL**.

## Cambios y causa

Beta30 corrige en Service y XStream la asociación de resultados IPTV con identidades TMDb mediante título normalizado y año, incluida la omisión de palabras comunes. Exige una coincidencia única y conserva la asociación por proveedor y perfil en `provider_search_*.sqlite`; usa el estado local de vistos aun sin conexión a Trakt. No cambia la base del catálogo ni fuerza una actualización masiva. Las pruebas de regresión comprueban que una asociación ambigua no se guarda y que el estado visto de otra película no se hereda.

El caso de referencia contenía un dato incorrecto: `tmdb:movie:198663` identifica **The Maze Runner / El corredor del laberinto (2014)**; **Chappie (2015)** es `tmdb:movie:198184`. El catálogo real enlaza Chappie con `198184`, y ni el estado local ni la lectura autenticada de Trakt lo marcan visto. Por tanto, **Chappie sin check es el resultado correcto**. Mostrarle el check de `198663` sería un falso positivo. Se corrigieron las fixtures de `test_smart_search.py` y `test_watched_integrity.py` y se añadió el caso negativo explícito. No se alteró el historial personal para satisfacer el criterio original.

## Publicación e instalación

| Componente | Versión instalada en Kodi Mac | SHA-256 del ZIP Testing | Estado |
|---|---|---|---|
| Skin | `1.2.36~beta2` | `01c19ef21e17ef4a3a90bbf9cbda1dc342c21743917483cbc5df934dbbe25ac3` | Sin cambios en Beta30 |
| Service | `0.4.94~beta3` | `5bfe6980a2689f2044241e808e5b26b16984c15fe434b12b03158b9ce0178a86` | `PASS_RUNTIME` |
| XStream | `1.1.2.36~beta3` | `4c33c4cb52d671564e30c510edf92274f1c7ce5b27c8ea527aea2067806503b1` | `PASS_RUNTIME` |

Los ZIP fueron reproducibles en dos construcciones y pasaron CRC, AST Python y XML. Los 21 archivos del feed fueron idénticos entre construcciones. El ZIP upstream conservó su SHA-256 fijado `915f45708670d07e789bb73b7390a7b5cf30175f818ef5da8ea18c9f13f537fe`. El índice Testing publicado tiene SHA-256 `25a5a23f721d2714d9910f7f30d8912b9da378ffa416a68396cc40e33265dde8`; Pages sirvió el índice y ZIP exactos con HTTP 200. GitHub Pages run `40243034093` terminó correctamente para `3905ea8`; también pasaron installer `40243034454` y XStream Candidate `40243034518`.

La instalación se hizo por la interfaz nativa de Kodi, sin copiar archivos al directorio de complementos. XStream se actualizó automáticamente tras refrescar el índice. Service tenía `update_rules=1`: el actualizador registró `INDIVIDUAL_UPDATE_BLOCKED`; se instaló la versión beta3 desde **Versiones → repositorio Testing** y Kodi resolvió la dependencia opcional `Up Next 1.1.0`. El registro posterior indicó `TESTING_UPDATE status=CURRENT`. El flujo de actualización automática de Service sigue **PARTIAL** porque necesitó esa selección manual; no se alteró `Addons33.db` directamente.

## Evidencia real de Kodi

| Función | Resultado | Evidencia y límite |
|---|---|---|
| Inicio y menú Trakt | `PASS_RUNTIME` | Home abrió; el acceso TRAKT y sus categorías Trending, Popular, Lists y Collections se mostraron. [Captura del menú](BETA30-trakt-menu.png). |
| Smart Search | `PASS_RUNTIME` para búsqueda local de películas | La búsqueda “El corredor del laberinto” devolvió tres títulos IPTV en unos 210 ms; “Chappie” devolvió uno en 222 ms. |
| Película vista / no vista | `PASS_RUNTIME` para esta muestra | El título de 2014 mostró check rojo y «VISTO»; las secuelas de 2015 y 2018 no. Tras reiniciar Kodi, el check seguía presente en la misma búsqueda (227 ms). [Captura](BETA30-watched-maze-runner.png). |
| Chappie | `PASS_RUNTIME` para identidad correcta; criterio original no aplicable | El resultado IPTV quedó asociado a `198184` y sin check. El ID `198663` suministrado era de otra película. |
| Estado local y SQLite | `PASS_STATIC` | `provider_search_1.sqlite`: `integrity_check=ok`; asociación Chappie guardada por perfil. Los JSON de vistos se conservaron. Copia preventiva de datos de perfil en `/private/tmp/actweeter-beta30-preinstall-20261026`. |
| Trakt autenticado | `PASS_RUNTIME` para lectura | GET `/users/settings` HTTP 200 y cinco páginas de `/sync/watched/movies` HTTP 200: 1.028 películas TMDb únicas, con `198663` vista y `198184` ausente. No se imprimieron tokens ni cuenta. |
| Trakt hacia Kodi | `PARTIAL` | Lectura remota y proyección visual de una película vista demostradas; no se comprobó renovación del token ni restauración en instalación nueva. |
| Kodi hacia Trakt | `NO VERIFICADO` | No se hizo escritura real de prueba ni se comprobó scrobbling remoto, para preservar el historial. |
| Reinicio y persistencia del menú | `PASS_RUNTIME` | Kodi mostró splash, introducción y Home; TRAKT siguió en el menú. La búsqueda y el check de la película vista persistieron. `kodi.log` registró `INTRO_PLAYBACK_TERMINAL event=ended` a las 04:58:57, sin la antigua excepción «Kodi is not playing» en ese arranque. |
| Series, temporadas, episodios, widgets, colecciones, tráilers y reproducción | `NO VERIFICADO` en esta continuación | La suite cubre contratos relevantes, pero faltan muestras visuales y reproducción real posteriores a Beta30. |
| PVR | `PARTIAL` | Kodi cargó 1.291 canales, 46 grupos, 777 canales EPG y 156.724 entradas EPG; no se reprodujo una emisión. |

El log tras instalar no mostró una excepción Python de AcTweeteR en las acciones revisadas. Persisten errores de `GetDirectory` de `plugin.video.themoviedb.helper` hacia tareas ausentes y un `GetDirectory` fallido al volver de la ventana 1109; no se ha demostrado que sean causados por Beta30. No se hicieron pruebas visuales de Android/tvOS ni cambios en esos dispositivos.

## Pruebas y estado del repositorio

Con los ZIP candidatos exactos en `ACTWEETER_XSTREAM_LIVE_ZIP`, `ACTWEETER_SERVICE_LIVE_ZIP`, `ACTWEETER_SKIN_LIVE_ZIP`, el upstream fijado y el índice Beta: **720 passed, 1 skipped, 96 subtests** en 27,98 s. La prueba omitida es el contrato de publicación Stable, deliberadamente fuera de esta misión. Las pruebas focalizadas de matching/estado visto: **116 passed, 8 subtests**. `git diff --check` sin errores.

`repo/` Stable no tiene diferencias. El índice Stable conserva SHA-256 `7ce09e4d820d8c52ec697d7a2bac5451a1076eec5d89e2234072be490efe54ee`. CI histórico de Stable sigue fallando por la discrepancia de manifiesto de `0.4.31` (`7ce09e…` frente a `ca6781…`), anterior y ajena a Beta30. No se modificó Stable, Lenovo ni Trakt remoto.

## Pendientes concretos

1. Validación real de checks de series, temporadas, episodios y otras superficies, con identidades verificadas.
2. Pruebas reales de tráilers e IPTV/VOD/PVR, y persistencia de estados de series tras reinicio.
3. Demostrar renovación de token y escritura bidireccional segura sin alterar indebidamente el historial personal.
4. Resolver por qué `update_rules=1` impide la actualización automática de Service en Kodi Master.
5. Investigar los errores de TMDb Helper/ventana 1109 si se reproducen funcionalmente.

No se declara PASS global. Las seis operaciones Trakt previamente pendientes se conservaron; no se asignaron identidades aproximadas ni se vació la cola.
