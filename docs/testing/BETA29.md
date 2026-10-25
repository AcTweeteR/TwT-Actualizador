# Informe forense — Beta29 Trakt y estado visto

Fecha: 2026-10-25  
Base: Beta28, `beeb67c61bd506c61219e1db3ad7eece311184a8`  
Rama: `codex/beta28-trakt-recovery`  
Commit de la candidata Beta29: `0a01ee459ee036afb5eb94bdfb788503cbbaef44`

## Resultado

Beta29 está publicada en Testing e instalada en Kodi Mac Master mediante el repositorio de Kodi. La ruta lateral de Trakt vuelve a estar visible y abre el menú de Trakt de XStream. Las pruebas automáticas de contrato del menú, integridad de estado visto e integración Trakt pasan.

El cierre global queda **PARTIAL**: no se verificaron en pantalla estados vistos de elementos con identidad exacta conocida ni se hizo una lectura autenticada de Trakt. No se hicieron escrituras remotas ni se modificó el historial personal.

## A. Qué se perdió y qué se recuperó

| Funcionalidad | Evidencia del origen/problema | Corrección | Resultado |
|---|---|---|---|
| Acceso lateral a Trakt | En la historia revisada no aparece una entrada permanente `TRAKT` en la fuente de Skin Shortcuts antes de Beta29. El commit Beta28 no modificó esa fuente. No se puede atribuir la desaparición a una fusión concreta con la evidencia Git disponible. | Añadida la entrada persistente a `mainmenu.DATA.xml`; la migración de Service conserva los accesos personalizados del perfil. | `PASS_RUNTIME`: visible en Inicio; abre el menú Trakt de XStream y permite volver a Inicio. |
| Visibilidad de rutas Trakt | La ruta de XStream ya existía; su disponibilidad estaba ligada indebidamente a la autorización/configuración pública. | La ruta permanece disponible y muestra el flujo de Trakt aunque el estado de conexión no permita sincronizar. | `PASS_TEST`; apertura del menú `PASS_RUNTIME`. Autorización remota: `NO VERIFICADO`. |
| Estado visto desconocido | El código podía reducir ausencia/error de estado a “no visto”, haciendo desaparecer checks válidos durante fallos de consulta. | `content_state.py` conserva el estado desconocido separado de visto/no visto y mantiene la proyección exacta existente. | `PASS_TEST`; estado visto en elementos reales: `PARTIAL`. |
| Películas/episodios/temporadas | Beta28 ya contenía proyección por identidad exacta e inventario dinámico; no se encontró evidencia de que toda esa lógica se hubiera perdido. | Se mantuvo la base actual y se añadieron contratos para unknown y para las superficies del menú. | Automatizado: `PASS_TEST`; visual con muestras identificadas: `NO VERIFICADO`. |
| Sincronización Trakt | XStream conserva autenticación/rutas y su transporte; Service mantiene la cola/proyección local. `script.trakt` sigue siendo un complemento independiente de Kodi. | No se añadió un segundo sincronizador ni se fusionaron ramas completas. Se conservaron los límites de identidad e idempotencia existentes. | Bidireccionalidad con cuenta real: `PARTIAL`; no se hicieron escrituras remotas. |
| Cambios locales de ramas paralelas | `TwT-Actualizador-trakt-unified-beta` y `TweeteR-Kodi` contienen cambios sin confirmar. La inspección selectiva encontró cambios que retiraban protecciones de intro/playcount/resume, entre otros. | Se conservaron intactos; no se hizo cherry-pick masivo ni se sobrescribió su estado. | `PASS_STATIC` para conservación; integración selectiva pendiente de revisar cualquier cambio funcional adicional. |

La historia Git no demuestra qué fusión eliminó el acceso anterior. Beta29 restituye el acceso como fuente mantenible de Skin Shortcuts, pero no se atribuye una causa más específica de la que permiten los commits.

## B. Estado Trakt y checks

| Superficie | Tests | Kodi Mac Master | Estado |
|---|---|---|---|
| Menú lateral y menú Trakt | Contrato y paquete candidato | Entrada `TRAKT` visible; abre Trending/Popular/Lists de XStream y regresa a Inicio | `PASS_RUNTIME` |
| Películas vistas | Proyección/identidad cubierta por la suite | No se comprobó una película con identidad y estado remoto/local confirmados | `PARTIAL` |
| Series, temporadas y episodios | Inventario y estado desconocido cubiertos por tests | Sin muestra exacta visual confirmada; no se marcaron contenidos | `PARTIAL` |
| Widgets, Spotlight y fichas | Contratos estáticos y tests de estado | Home real carga Spotlight y carrusel “Continuar viendo”; no se acreditó el check de una entidad identificada | `PARTIAL` |
| Smart Search, colecciones y listados | Incluidos en la suite previa de Beta29 | No recorridos visualmente en esta comprobación | `NO VERIFICADO` |
| Persistencia tras reinicio | Migración/contrato probado | No se hizo un segundo reinicio para comprobar persistencia del check | `NO VERIFICADO` |

La suite no transforma “desconocido” en “no visto”. Las cinco operaciones de episodios sin identidad inequívoca y la operación de película sin referencia exacta continúan pendientes; no se inventaron identificadores ni se descartaron operaciones.

El archivo local de tokens había sido reportado como existente en el estado previo. En esta comprobación no se leyó ni imprimió su contenido y no se validó su vigencia contra Trakt. La presencia de la ruta en la interfaz no demuestra autorización ni sincronización remota.

## C. Kodi Mac Master y paquetes

Versiones instaladas, activas y registradas con origen `repository.actweeter.testing` en `Addons33.db`:

| Complemento | Versión | SHA-256 del ZIP Testing |
|---|---|---|
| Skin AcTweeteR | `1.2.36~beta2` | `01c19ef21e17ef4a3a90bbf9cbda1dc342c21743917483cbc5df934dbbe25ac3` |
| Service AcTweeteR | `0.4.94~beta2` | `5be1aaaf9bbce2b2dedb1a9a8140f196d3124d7348b8f3b486bee49a65c5e880` |
| XStream Pro | `1.1.2.36~beta2` | `8c983b494608cae131839d2840244460b00032de59d2b4163a64d55205b0e38d` |

`Addons33.db` devolvió `integrity_check=ok`. Se compararon los ficheros instalados con los ZIP: Service (189 ficheros) y XStream (116) coinciden; Skin coincide salvo `1080i/script-skinshortcuts-includes.xml`, archivo que Kodi genera/usa para el estado local de Skin Shortcuts. Se preservó ese archivo de perfil; la interfaz efectiva sí muestra `TRAKT` y `ARCADE`.

La actualización se instaló con Kodi, no copiando archivos a `addons/`. No se modificaron historiales, credenciales, configuración del perfil ni bases de datos. Existe una copia de seguridad verificable del perfil en `RecoveryBackups/Beta28-forensic-20261025T204928+0100`.

## D. Pruebas y logs

- Suite completa sobre los ZIP candidatos exactos de Beta29, en la ejecución previa: **709 aprobadas, 1 omitida y 96 subpruebas aprobadas**. La omisión quedó informada, no se ocultó.
- En esta continuación, suite focalizada con ZIPs exactos: **67 pruebas aprobadas, 0 errores, 0 fallos y 0 omitidas**. Incluyó `test_menu_contract`, `test_watched_integrity`, `test_trakt_series_inventory`, `test_trakt_live_queue_runtime`, `test_trakt_outbox`, `test_trakt_tmdb_projection` y `test_trakt_resume_bridge`.
- Hashes de los tres ZIPs confirmados; el índice Testing registrado para Beta29 tiene MD5 `1b88aa92d64e828ecf11426f8b3c16a1` y SHA-256 `6954bd541e0b7f6c9d5e760eebd68c4b237e9f293ab0728daa3400fc0ef3f27a`.
- La validación previa de Beta29 incluyó construcción reproducible, XML, Python/AST, CRC y hashes. En esta continuación no se pudo repetir la suite completa porque el Python disponible no tiene instalado `pytest`; no se instaló una dependencia en el entorno.
- En el tramo de instalación/uso revisado no aparecen `Traceback` ni excepciones Python. Sí aparecen errores Kodi de recursos HTTP 404 y fallos repetidos de `GetDirectory` en tareas en segundo plano. Sus URLs/rutas se omitieron por privacidad y su relación con la restauración no quedó demostrada; requieren diagnóstico separado.

## E. Forense de repositorios y Stable

- La secuencia `f74013d` → `5f9a7c3` → `beeb67c` está en la historia de Beta28; los commits no sustituyen la base Beta28 por una arquitectura antigua.
- El repositorio `trakt-unified-beta` conserva sus cambios sin confirmar. El repositorio de reconstrucción `TweeteR-Kodi` también conserva sus cambios locales. `trakt-sync-completion` está limpio; `TwT-Actualizador` está limpio. El repositorio indicado como `TwT-Actualizador-git-admin` no se encontró en la ruta suministrada.
- No se incorporaron cambios de ramas completas: la comparación mostró regresiones potenciales en cambios locales antiguos y Beta28 ya tiene partes de la lógica de estado/inventario que esos cambios pretendían cubrir.
- Los artefactos del canal Stable (`repo/`) no aparecen en el diff de Beta29. La Beta publicada añade paquetes e índice al feed Testing. El SHA-256 local actual de `repo/addons.xml` es `7ce09e4d820d8c52ec697d7a2bac5451a1076eec5d89e2234072be490efe54ee`, igual al archivo del padre de Beta29. Informes anteriores registran otro hash (`14adccd3…`), por lo que queda una discrepancia histórica de Stable sin resolver y no se ha intentado corregirla.
- El commit Beta29 actualizó rutas de candidatos en workflows de verificación para que apunten a Beta29. No publicó ni sustituyó ZIPs o índices Stable; el workflow de verificación Stable sigue notificando una discrepancia histórica de manifiesto/índice.
- `repository.actweeter.qa` ya estaba deshabilitado y `repository.actweeterqa` no tenía fila instalada en la auditoría previa; no se borraron ni alteraron.

## Clasificación final

- Menú lateral Trakt: `PASS_RUNTIME`.
- Instalación Beta y procedencia Testing: `PASS_RUNTIME`.
- Tests focalizados: `PASS_AUTOMATED`.
- Estado desconocido y contratos de vistos: `PASS_AUTOMATED`.
- Checks visibles de datos reales y sincronización Trakt autenticada: `PARTIAL` / `NO VERIFICADO`.
- Integridad de perfil y Addons33.db: `PASS_STATIC`.
- Stable: sin artefactos Stable modificados por Beta29; discrepancia histórica de hash/manifiesto pendiente.
- Resultado global de la recuperación: **PARTIAL**, no PASS global.

## Continuación forense — 2026-10-25

### Trakt y estado local

Se repitió una lectura autenticada de solo lectura utilizando el transporte de snapshot de XStream ya instalado. La petición terminó con `snapshot_complete=true`: 1.846 registros únicos y 3.251 eventos, sin identidades sin resolver en la respuesta. No se refrescó ni se renovó el token y no se hizo ninguna escritura remota.

La comparación por identidad exacta encontró 1.028 películas vistas remotas frente a 1.029 claves TMDb locales: 1.028 coincidentes, ninguna remota ausente localmente y una clave solo local. Esa diferencia se preservó; no se interpretó como una orden para borrar o marcar contenido. Para episodios, 812 identidades remotas y 812 locales coincidieron exactamente por TMDb de serie, temporada y episodio.

Las seis operaciones pendientes siguen intactas. Cinco se aplazan porque el catálogo/inventario activo no permite verificar la relación exacta entre la serie del proveedor y su identidad externa (`provider_identity_not_verified_in_catalog`); la sexta carece de referencia exacta de reproducción (`exact_playback_reference_missing`). No se aplicaron por título ni se descartaron.

En el perfil real, la proyección local exacta devuelve `visto` para una película y un episodio cuyas identidades están presentes, y `desconocido` para una identidad sin estado guardado. El catálogo de proveedor contiene 26.476 películas y 8.871 series, pero no aporta IDs externos en sus filas; tampoco hay registros de metadatos de serie verificables en la caché inspeccionada. Por ello no se pudo demostrar en datos reales la completitud dinámica de temporadas y series. El estado parcial/desconocido permanece diferenciado; no se redujo a “no visto”.

La lectura autenticada demuestra que el token instalado sirve para GET en este momento. No demuestra escritura ni bidireccionalidad completa. El código asigna la lectura/proyección local al Service, las acciones explícitas de marcado a XStream y el scrobbling de reproducción a `script.trakt`; no se hicieron escrituras de prueba. Sigue sin demostrarse si una acción manual coincidente con un scrobble activo puede producir una duplicación remota.

### Interfaz y límites de validación

La interacción de interfaz de esta continuación permitió recorrer la barra lateral real de Kodi Mac Master y abrir Trakt. La captura mostró la entrada `TRAKT` junto con `RIVULET` y `ARCADE`; la vista de Trakt mostró `OPCIONES` y listados Trending/Popular. Después Kodi volvió a Inicio y renderizó Spotlight/XStream. La accesibilidad de macOS solo expone la ventana de nivel superior, así que la evidencia visual proviene de las capturas de CUA, no del árbol AX. Esto valida la presencia y apertura del menú, pero no los checks de elementos identificados, Smart Search ni colecciones; autorización y secciones personales de Trakt siguen `NO VERIFICADO`.

La auditoría de 4.000 líneas recientes encontró errores de directorio en `plugin.video.themoviedb.helper` por carpetas propias ausentes (`log_tagger`, `log_library`, `timer_report`) y seis excepciones de reproductor atribuidas en el propio registro a `plugin.video.themoviedb.helper` y `plugin.video.tmdb.bingie.helper`. No hay evidencia de que esos mensajes provengan de AcTweeteR. También hay avisos repetidos de propiedades Kodi obsoletas `resumetime`/`totaltime` cuyo llamador no se pudo atribuir con seguridad; quedan pendientes. Los errores HTTP 404 de recursos de metadatos sí se explican por el generador del canal Testing descrito a continuación.

### Corrección del generador Testing

El índice Beta declaraba imágenes relativas de skin, XStream y repositorios externos, pero el generador solo publicaba ZIPs y changelogs. Los recursos no se copiaban al directorio `repo/<addon_id>/`, lo que hacía que Kodi Pages devolviera 404. Se actualizó `tools/build_test_channel.py` para extraer únicamente los recursos locales declarados en el `addon.xml` del ZIP que se publica, rechazando rutas inseguras y fallando si falta el recurso dentro de ese mismo ZIP. No se cambia el índice, los ZIPs, sus hashes ni las versiones; Stable no participa.

La salida construida dos veces con los mismos ZIP Beta29 produjo 21 archivos idénticos byte a byte. Se validaron y copiaron en la salida temporal ocho recursos laterales: skin (icono/fanart), XStream (icono/fanart), Rivulet e IAGL (icono/fanart). La prueba de canal comprueba igualdad byte a byte con los recursos de los paquetes, rechaza `../` y conserva el índice Stable.

El commit `28880a70fed9829ad249f3bee3023cbe7d4037ff` (`Fix Testing repository metadata assets`) ya está publicado en `main`. El workflow de GitHub Pages `40235908318` completó `build`, `deploy` y `report-build-status` con éxito. Tras el despliegue, las comprobaciones HTTP HEAD dieron **200** para el índice Testing y los ocho sidecars de Skin, XStream, Rivulet e IAGL. No se sustituyeron ZIPs ni se cambió el índice.

El workflow de instalador Beta `40235908856` también terminó con éxito. En la verificación del commit, `verify-current-stable` pasó; `verify-new-stable` falló en la reconstrucción histórica de Stable por la discrepancia ya registrada entre SHA-256 esperado `ca6781c5c0c7723a2c79681d4ffef85bf8780d8a6588d6e0f767cafd8780e839` y reconstruido `7ce09e4d820d8c52ec697d7a2bac5451a1076eec5d89e2234072be490efe54ee`. Ese fallo no tocó Stable ni sus artefactos; queda separado de la publicación Beta.

### Pruebas de esta continuación

- `source/0.4.32/tests/test_official_test_channel.py`: **16 aprobadas**.
- Suite Beta canónica (`source/0.4.32/tests`) con el ZIP exacto XStream Beta29 configurado como `ACTWEETER_XSTREAM_LIVE_ZIP`: **698 aprobadas, 9 omitidas, 4 excluidas por la misma configuración CI de Beta y 92 subpruebas aprobadas**.
- Las nueve omisiones se conservaron visibles: falta el ZIP upstream pinned para el build reproducible de Device Code; no hay paquete/test ZIP de concurrencia XStream; faltan staging exactos de Skin/Service/índice en contratos de publicación; y se excluye deliberadamente la publicación Stable. No se rebajaron aserciones.
- Un primer `pytest` sobre todos los directorios históricos del repositorio falló al recopilar módulos de test duplicados entre snapshots `source/0.4.29`–`0.4.32`; se repitió el comando canónico del workflow Beta sobre `source/0.4.32/tests`, que pasó con las exclusiones Stable configuradas por CI.

## Clasificación actualizada

- Lectura autenticada de Trakt: `PASS_RUNTIME` para GET; escritura y sincronización bidireccional: `PARTIAL`.
- Coincidencia exacta de películas y episodios locales/remotos: `PASS_STATIC` para los recuentos comparados; una película local adicional quedó preservada.
- Check local exacto y estado desconocido: `PASS_TEST`; muestra visual en Kodi: `PARTIAL`.
- Completitud real de serie/temporada: `PARTIAL` porque el inventario del proveedor no aporta IDs externos verificables.
- Corrección de sidecars Testing: `PASS_AUTOMATED` por construcción reproducible y `PASS_RUNTIME` para disponibilidad HTTP del índice y los ocho recursos tras Pages. Los ZIPs/versiones instalados no cambiaron; Kodi ya tenía Beta29.
- Despliegue Pages e instalador Beta: `PASS_RUNTIME` en los jobs publicados; verificación histórica de Stable: `FAIL` por discrepancia preexistente del manifiesto/índice, sin cambios en Stable.
- Suite Beta canónica: `PASS_AUTOMATED` con las omisiones y exclusiones enumeradas.
- Resultado global: **PARTIAL**; no se afirma cierre visual ni bidireccionalidad remota.
