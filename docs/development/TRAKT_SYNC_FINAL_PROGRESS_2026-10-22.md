# Trakt ↔ Kodi AcTweeteR — cierre de continuidad (2026-10-22)

## Resultado

**PARTIAL — no es candidato para publicar ni desplegar.** Esta rama corrige
defectos de integración del snapshot y refuerza su contrato; no implementa la
sincronización incremental automática ni demuestra el recorrido en Kodi real.

## Estado de fuentes

- Rama aislada: `codex/trakt-sync-final-2026-10-22`, base `6e44c345`.
- Código del worktree: servicio `0.4.54`, skin `1.2.32~beta1`; el constructor
  local de XStream todavía fija `1.1.2.20~beta1`.
- Feed Testing público consultado: servicio `0.4.54`, skin `1.2.32~beta1`,
  XStream `1.1.2.22~beta1`, Testing repo `1.0.2`.
- Los manifiestos locales no reconstruyen actualmente el XStream publicado
  `1.1.2.22~beta1`. No se generó ZIP con la versión antigua ni se publicó.
- La instalación Mac leída previamente coincide con service `0.4.54`, skin
  `1.2.32~beta1` y XStream `1.1.2.22~beta1`. Lenovo se dejó sin cambios.

## Cambios de esta continuación

- Conectada la acción `trakt_restore` al router de Kodi y añadidos enlaces
  explícitos a la exportación GET nativa de XStream y a la recarga de exportes.
- La UI obtiene el perfil activo de XStream desde su ajuste público, usa ese
  perfil al leer y preparar la vista previa, y referencia sus archivos
  `watched_*_pN.json` (ya no fija el perfil 1).
- Los almacenes ausentes se proyectan como objetos vacíos solo en el staging
  temporal; no se crean archivos activos.
- El importador rechaza snapshots sin `schema_version` reconocido, marca
  `complete=true`, estructuras completas, hash y vínculo cuenta/perfil.
- El snapshot deja de consultar recomendaciones no necesarias para restaurar
  vistos/reanudación; el export conserva únicamente respuestas `/sync/*`, no
  ajustes de cuenta ni credenciales.
- El lector solicita `extended=progress` para `/sync/watched/shows`, necesario
  para inventariar episodios con los cambios de paginación/respuesta de Trakt
  de 2026 ([discusión oficial de Trakt](https://github.com/trakt/trakt-api/discussions/775)).
- El constructor XStream ya incluye el parche snapshot y copia sus dos módulos
  desde fuentes versionadas, con SHA-256 fijados; los tests detectan que falte.

## Verificación ejecutada

- `python3 -m unittest discover -s source/0.4.32/tests -q`: **441 PASS**.
- `compileall` de service, constructor XStream y helper snapshot: PASS.
- `git diff --check`: PASS.
- El test de aislamiento aplica el parche al fixture distribuido `1.1.2.19`,
  comprueba CRC y el hash esperado de `addon.py`: PASS. Esto no demuestra que
  el constructor reproduzca el Beta público `1.1.2.22`.
- Los tests de snapshot son sintéticos; no se contactó Trakt, no se creó un
  export real y no se tocó estado remoto.

## No verificado / bloqueos funcionales

- **GET real desde Kodi:** NOT_TESTED. Kodi Master está ejecutándose, pero
  JSON-RPC no estaba disponible; no se lanzó la ruta XStream ni se escribió un
  snapshot en el perfil. La pantalla ahora tiene el enlace, pero el código no
  está instalado allí.
- **Aplicación local / Continue Watching:** NOT_TESTED en Kodi. Las escrituras
  activas no se ejecutaron. El commit de stores exige Kodi detenido y no existe
  una ruta incremental que aplique deltas durante la ejecución de forma segura.
- **Sincronización incremental y scheduler:** NO IMPLEMENTADOS. No hay todavía
  checkpoint de actividad/account/profile, aprobación persistente de sync
  automático, backoff ni reconciliación periódica conectados al servicio.
- **Cobertura real del catálogo:** NOT_TESTED; falta snapshot real y el índice
  actual del proveedor.
- **Catálogo completo de episodios:** la ruta depende de que `extended=progress`
  entregue el inventario requerido; solo se cubre con fixtures.
- **Distribución Beta:** no preparada/publicada. Antes se necesita reconciliar
  los inputs exactos de XStream `.22`, revisar la licencia CC BY-NC 4.0 y
  reconstruir el artefacto probado sin downgrade.
- **Lenovo runtime:** NOT_TESTED en esta continuación. No se hizo ADB install,
  modificación de perfil ni copia de datos.

## Seguridad y dispositivos

- Trakt remoto: solo pruebas simuladas; **sin POST/PUT/PATCH/DELETE**.
- Perfil activo de Kodi/XStream: no aplicado ni restaurado; no se modificaron
  favoritos, progreso, historial, credenciales o sesión Trakt.
- Stable, Apple TV y Lenovo: sin cambios.
- Kodi Master permanece abierto; no se reinició.

## Próximo paso seguro

Reconciliar el constructor con la fuente exacta del Beta XStream `1.1.2.22`
(sin reemplazarlo por `.20`), confirmar la ruta snapshot instalada mediante el
gestor Beta en un despliegue autorizado y ejecutar un export GET desde Kodi.
Solo después se puede medir cobertura y diseñar una sincronización incremental;
no se debe habilitar auto-aplicación hasta disponer de un escritor local seguro,
account/profile binding persistente y prueba de recuperación.

## Continuación de integración unificada (22-10-2026)

El worktree `codex/trakt-unified-beta-2026-10-22` parte de `main` oficial
`51c0d02d0d7c22e3d52b221e4b68f6664751d4bb` y contiene la integración del
segundo clon (`8ccbb7f`) más la preparación segura de avances de la primera
rama. El merge está todavía local y sin publicar.

### Cambios de esta continuación

- XStream `.22` no era reproducible desde el constructor `.20`. Se reconciliaron
  las modificaciones observadas en el ZIP `.22`; el constructor produce ahora
  el candidato siguiente `1.1.2.23~beta1`, no un ZIP `.22` renumerado. En la
  comparación de archivos, 103/107 miembros son idénticos; las diferencias son
  el aviso de modificaciones, `addon.xml` y los dos módulos de snapshot/sync.
  SHA-256 del ZIP público `.22`: `b21b114590cfbde4f0b798f62e97a274b0853173ed96a2f4719aeaa1d924d601`.
  El archivo upstream fijado para reconstruir es `.20` (SHA-256
  `915f45708670d07e789bb73b7390a7b5cf30175f818ef5da8ea18c9f13f537fe`); no se
  cambió solo su número de versión.
- Se actualizó el lock del parche de Mis listas y se recuperaron los cambios de
  inventario `series_changes`/`series_state` observados en `.22`.
- `trakt_sync._pages` ahora rechaza una página final vacía cuando el servidor
  anuncia una respuesta multipágina; conserva una respuesta vacía válida de una
  sola página. Hay prueba de regresión.
- La preparación local de restauración incorpora avances únicamente si existe
  una referencia de reproducción XStream exacta para el perfil, identidad y
  coordenadas del episodio. Nunca crea URLs. Los avances remotos sin fecha,
  ambiguos, cercanos al final o más antiguos que el estado local quedan
  diferidos. El resultado se escribe exclusivamente en staging temporal; los
  almacenes activos no se modifican.
- El escritor local admite los tres stores watched-movies, watched-episodes y
  resume, con backup checksumado, commit atómico, rollback condicionado a hashes
  intactos y recuperación de interrupciones. Exige Kodi detenido; no se ofrece
  una vía de aplicación desde la UI mientras Kodi corre.
- No se añadió una aplicación desde la UI mientras Kodi está activo, ni un
  scheduler que escriba archivos que XStream pudiera mantener cargados.

### Validación reproducible

- Suite completa: **453 PASS** (`python3 -m unittest discover -s source/0.4.32/tests -q`).
- `git diff --check`: PASS.
- ZIP de servicio, XStream y skin: CRC PASS; índices locales anuncian servicio
  `0.4.55`, skin `1.2.32~beta1`, XStream `1.1.2.23~beta1` y repo Testing
  `1.0.2`. ZIP e índice se guardaron solo en `/private/tmp`.
- SHA-256 servicio: `21e073fdb8d118458ddd5c1a2001563a0bc51401624feb458dd14f955213fc11`; dos builds independientes dieron el mismo hash.
- SHA-256 skin: `3e7cf74ad59cd7d9b3ee8be9b399f4974816890a2f2dd31ed9cfea3e9121d08b`.
- SHA-256 XStream: `5eebc025b64bac1553c5c170bff075a9024134d010ad3e137e265bc91559fdd3`.
- SHA-256 del índice privado: `6c975846720ea47e8dde74878714d398271a972bd5d96c402a7dfef25e6df1f4`; MD5 calculado del XML: `3b8b71670687e9deb1149c28062c8b04`.

### Aún no completado / no publicar

- La licencia XStream observada es CC BY-NC 4.0 y el propio manifiesto advierte
  que no debe tratarse como autorización de distribución pública irrestricta.
  Por eso los artefactos siguen siendo candidatos privados; no se publicaron
  ni se alteraron Stable/Testing.
- Sincronización incremental automática, aprobación persistente por cuenta y
  perfil, aplicación segura con XStream activo, checkpoints y cobertura de
  catálogo siguen sin estar implementados/verificados. No se habilitaron.
- Esta continuación no hizo llamadas a Trakt, no leyó ni copió credenciales y
  no aplicó cambios al perfil activo. No se logró validar runtime en Kodi Mac
  ni Lenovo; ADB quedó bloqueado por la política del sandbox.
- Commit local de consolidación: `82e4d3b` (`Merge Trakt sync and profile-safe
  restore into Beta base`). No se hizo push. La rama mantiene el estado
  `PARTIAL`; el commit no implica aprobación de publicación.

Resultado actual: **PARTIAL — no apto para publicación ni instalación**.

### Reanudación de trabajo (22-10-2026)

- Rama comprobada: `codex/trakt-unified-beta-2026-10-22`, HEAD `93aca2e`;
  árbol limpio al iniciar esta reanudación. No se usó ADB ni se accedió a
  Lenovo, Apple TV o Stable.
- Versiones fuente de la rama: service `0.4.55`, skin `1.2.32~beta1`, XStream
  candidato `1.1.2.23~beta1`. Kodi Master instalado, leído sin modificar:
  service `0.4.54`, skin `1.2.32~beta1`, XStream `1.1.2.22~beta1`.
- La API JSON-RPC de Kodi en `127.0.0.1:8080` rechazó la conexión. El log
  `/Users/alberto/Library/Logs/kodi.log` existe, pero no contiene eventos
  `trakt_snapshot`, `trakt_sync` ni `trakt_restore`; su última escritura fue
  22-10-2026 23:28 CEST. Por tanto no hay evidencia de exportación GET ni de
  aplicación de restauración en runtime durante esta sesión.
- XStream `.23` se inspeccionó desde el ZIP candidato. `history.py` carga los
  almacenes JSON en memoria y cada `_save()` hace `os.replace()` atómico, pero
  no implementa exclusión mutua compartida con otras instancias ni recarga y
  mezcla los datos actuales antes de guardar. Una escritura directa del
  servicio puede ser sobrescrita por un objeto XStream con snapshot antiguo;
  además no hay confirmación de que las cachés de “Continuar viendo” hayan
  observado el cambio. No se añadió un escritor en vivo especulativo ni se
  escribió en el perfil activo.
- Verificación de licencia: el artefacto retiene `LICENCE.txt` y atribuciones.
  CC BY-NC 4.0 permite compartir/adaptar solo con fines no comerciales,
  atribución, enlace a la licencia e indicación de modificaciones; que un ZIP
  sea gratuito o esté en un repositorio público no resuelve por sí solo el
  carácter comercial del uso. La distribución del candidato continúa bloqueada
  hasta aclarar ese contexto o contar con permiso adicional del titular.
  Referencias: [texto legal CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/legalcode.en),
  [resumen de licencia](https://creativecommons.org/licenses/by-nc/4.0/deed.en),
  [repositorio upstream XStream Pro](https://github.com/Pesicp/XStreamPro).
- Suite repetida en esta reanudación: **453 pruebas PASS** (`unittest`, 16.711 s).
- El ZIP candidato XStream existente conserva SHA-256
  `5eebc025b64bac1553c5c170bff075a9024134d010ad3e137e265bc91559fdd3`.
  No se reconstruyó ni instaló durante esta reanudación.

Resultado tras reanudar: **PARTIAL**. La restauración offline y la preparación
en staging siguen siendo reproducibles; la escritura live, la sincronización
incremental conectada al servicio, el checkpoint/consentimiento persistente y
la validación Trakt runtime en Master no están demostrados. No publicar ni
instalar el candidato todavía.

## Experimento de concurrencia XStream (23-10-2026)

Commit: `da9b32d` (`Coordinate XStream history store writes`). No se hizo push.

### Alternativas evaluadas

| Opción | Evidencia en esta continuación | Decisión |
|---|---|---|
| Escritura mediante los stores de XStream | La pérdida upstream se reproduce con dos instancias reales de `history.py`; el candidato coordina `_save()` y hace merge bajo bloqueo de proceso y de sistema operativo. | Base seleccionada para proteger los JSON existentes. |
| Cola persistente consumida por XStream | No implementada ni probada; falta definir el contrato de identidad/cuenta y el acuse durable. | Pendiente antes de que el servicio entregue deltas live. |
| API local directa | No implementada ni probada; añade un transporte y un punto de exposición sin resolver por sí solo el ciclo de vida de cachés. | No seleccionada por ahora. |
| Coordinación común de persistencia | Probada en los stores JSON reales de XStream dentro de directorios temporales; locks por ruta, reload/merge/write y reemplazo atómico existente. | Implementación actual. |
| Aplicación diferida/offline | La restauración en staging sigue disponible y segura con Kodi detenido; no demuestra aplicación live ni refresco de UI. | Fallback, no solución live. |

### Implementación y evidencia

- Se añadieron `history_store_coordinator.py` y su parche versionado al
  constructor. Coordina `WatchedMovies`, `WatchedEpisodes` y `ResumePoints`;
  los cambios externos no escriben directamente en los almacenes. ResumePoints
  conserva la entrada con timestamp más nuevo y omite muestras cuya diferencia
  sea menor de 60 s, salvo el guardado terminal explícito.
- El monitor de reproducción de XStream conserva el muestreo existente, pero
  persiste el avance como máximo cada 60 s y fuerza la última muestra al salir.
  No se añade polling de Trakt ni un scrobbler nuevo.
- Prueba upstream, sobre la `history.py` del ZIP fijado: dos instancias cargan
  el mismo JSON, escriben IDs distintos y la segunda escritura reemplaza la
  primera. Resultado: pérdida reproducida.
- Prueba candidato, usando sus clases XStream reales en subprocess y perfil
  temporal: escrituras stale de películas y episodios se fusionan; dos avances
  con timestamps distintos conservan el más reciente; también se cubre el caso
  donde la instancia obsoleta cargó el valor nuevo como baseline. 24 procesos
  concurrentes conservan todos sus IDs. Una muestra subminuto no toca el mtime;
  el guardado forzado final sí persiste.
- Los JSON corruptos fallan cerrados. Un fallo simulado de `os.replace` no
  altera el archivo comprometido; un guardado posterior conserva los datos
  confirmados y no trata la operación interrumpida como aplicada.
- Suite completa: **455/455 PASS**, incluida la comparación con upstream y la
  integración del ZIP candidato. `git diff --check`: PASS.
- ZIP de XStream `1.1.2.24~beta1`, construido dos veces desde el upstream
  bloqueado `1.1.2` y el mismo conjunto de fuentes/parches: SHA-256 idéntico
  `b58c0e1640907a8ac396216f1ca158bd1cab4f4d9d1212702fa035ff82449198`; CRC,
  versión, sintaxis Python y presencia del coordinador pasan en el constructor.
- Tests y manipulación de datos se ejecutaron en directorios temporales. No se
  tocó el perfil activo, no hubo llamadas a Trakt, ni operaciones remotas de
  escritura, ni acceso a Lenovo/ADB, Apple TV o Stable.

### Límites y siguiente trabajo

- Esto resuelve la pérdida entre escrituras de los stores, pero **no** es aún
  un escritor live de Trakt: `service.actweeter` no envía una cola de deltas al
  proceso de XStream, no hay recibo durable ni binding comprobado cuenta/perfil/
  proveedor, y la vista «Continuar viendo» no se ha observado actualizarse en
  Kodi abierto.
- No se ha implementado sincronización inicial/incremental, scheduler de cinco
  minutos, consulta de actividad, checkpoint, autorización persistente ni
  backoff conectado al servicio. No se hicieron GET reales desde Kodi.
- La prueba usa clases XStream reales con shims de Kodi sobre un perfil temporal;
  no equivale a runtime Kodi. La instancia activa de Kodi Master no se instaló
  ni modificó.
- Código candidato todavía privado y sin publicación. La revisión de licencia
  CC BY-NC 4.0 sigue bloqueando una distribución pública hasta aclarar el uso
  no comercial o contar con permiso del titular.
- La integración con lectores que retienen objetos en memoria aún requiere un
  mecanismo de invalidación/refresco; el merge-on-write protege persistencia,
  pero no demuestra que cada objeto ya cargado refleje una escritura ajena.

Resultado actualizado: **PARTIAL**. La concurrencia de persistencia JSON entre
instancias XStream queda reproducida y corregida en las pruebas aisladas; la
sincronización automática completa y su comportamiento en Kodi Master siguen
pendientes y no se declara resuelta.

## 2026-10-23 — puente durable de operaciones (sin activar sincronización)

Se añadió una primera conexión local de solo entrada Service → XStream. El
servicio puede convertir un plan de importación ya verificado en un lote
consentido, limitado y ligado a cuenta, perfil y huella del proveedor; lo
escribe atómicamente en su directorio privado y solicita su consumo mediante
`RunPlugin`. XStream vuelve a comprobar su cuenta Trakt nativa, perfil activo,
proveedor y estado de reproducción, aplica solo adiciones mediante sus clases
`WatchedMovies`, `WatchedEpisodes` y `ResumePoints` y confirma después de releer
los stores con instancias nuevas. Referencias de reproducción solo se aceptan
si existen exactamente en el perfil XStream; nunca se fabrican URLs. Repetir
el lote es idempotente y un lote con reproducción activa se aplaza.

Archivos principales añadidos:

- `addons/service.actweeter/resources/lib/trakt_live_queue.py`
- `addons/service.actweeter/resources/lib/trakt_live_sync.py`
- `third_party/xstream/trakt_live_consumer.py`
- `third_party/xstream/patches/1.1.2/actweeter-trakt-live-queue.patch`
- pruebas de cola y de integración aislada con los stores reales del ZIP.

Verificación local inicial: **461/461 pruebas PASS** (incluye la integración con las
clases reales de XStream en un directorio temporal, no Kodi runtime),
`git diff --check` PASS, ZIP CRC PASS y reconstrucción reproducible PASS.
Service `0.4.56` SHA-256
`1f7df6aba491fc7389754ce15fabd8505df3c66a3f834b88afd4e7dd5983c830`;
XStream `1.1.2.25~beta1` SHA-256
`c45fcc5b7509142b86e3688f080670629178a5bf6d107dfde987cc31ed65dc51`.
Son artefactos privados en `/private/tmp`; no publicados ni instalados.

**No es todavía sincronización automática ni un checkpoint de actividad
remota.** El archivo llamado checkpoint solo conserva recibos de lotes
aplicados. No hay scheduler, GET Trakt ejecutado, comparación de actividad,
preparación automática de lotes, consentimiento persistente de sincronización
ni refresco de los objetos XStream ya residentes en memoria. El puente tampoco
ha sido ejecutado dentro de Kodi. No se escribió en stores reales, en Trakt ni
en el perfil activo; tampoco se accedió a Lenovo o Apple TV. El runtime actual
de Mac continúa en versiones anteriores al candidato y JSON-RPC localhost no
está disponible. Resultado de esta iteración: **PARTIAL**, no listo para
instalar o habilitar sincronización live.

### Endurecimiento del recibo y reconstrucción final

Se añadió una regresión para recibos malformados/duplicados: el servicio ahora
los rechaza sin avanzar el estado. Suite final: **462/462 PASS**. Se
reconstruyeron los ZIP con nombres nuevos (el empaquetador rechazó sobrescribir
los previos): Service `0.4.56-r2` SHA-256
`c1ae6dac5fd1afd8d1fcafb5c3da12125bfcaaab09429e7cf784a7450a590d80` y XStream
`1.1.2.25~beta1-r2` SHA-256
`1212542f11d105618cc1ded9eb15798c63c0ae1268b048c4461a1c62d4c280ad`;
integridad CRC PASS. Siguen siendo artefactos locales privados, no publicados
ni instalados.
