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
