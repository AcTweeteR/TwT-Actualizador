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
