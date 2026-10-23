# Kodi Mac — Smart Search, vistos y navegación de episodios

Fecha: 2026-10-23  
Rama: `codex/trakt-unified-beta-2026-10-22`  
Estado: **PARTIAL** — integración y paquetes comprobados; instalación/runtime dentro de Kodi pendientes.

## Correcciones

- Se reparó la ruta de búsqueda del proveedor usada para filtrar temporadas y episodios. El ZIP instalado tenía un fallback por título fuera del bucle, que solo examinaba el último elemento cacheado. El parche del constructor recorre el catálogo completo y acepta el fallback únicamente cuando hay una coincidencia exacta única; la coincidencia por TMDb conserva prioridad. La prueba ejecuta la función extraída del ZIP candidato, cubriendo tanto un resultado no situado al final como títulos ambiguos.
- Smart Search lee, sin escribir, `watched_movies_pN.json` del perfil XStream activo. Reconoce claves TMDb exactas para película, serie, temporada y episodio, además de ID de proveedor exacto solo para resultados IPTV disponibles. Las series parciales se muestran como `EPISODIOS VISTOS`; no se confunden con series completas.
- Las filas de temporada/episodio heredan la identidad TMDb de la serie en un campo separado utilizado solo para leer el estado. No se asigna el ID TMDb de la serie como identidad del episodio ni se fabrican URLs.
- La lectura de vistos se reutiliza mientras no cambien tamaño/mtime del archivo; errores, perfiles ausentes e identidades inválidas fallan cerrados.
- Se conservaron los cambios locales preexistentes de `trakt_live_queue.py`, `trakt_auto_routes.py` y `trakt_live_consumer.py`, y se actualizaron sus hashes bloqueados en el manifiesto. No se activó consentimiento ni hubo llamadas de escritura a Trakt.

## Las dos pruebas que fallaban

- `test_xstream_snapshot_patch_and_sources_are_locked`: fallaba porque los tres fuentes locales conservados habían cambiado sin actualizar sus hashes de bloqueo. Se sincronizaron los hashes del manifiesto y se añadió el hash del parche de navegación.
- `test_native_snapshot_transport_never_refreshes_or_posts`: exige inspeccionar el ZIP exacto mediante `ACTWEETER_XSTREAM_LIVE_ZIP`; la ejecución anterior no proporcionaba ese artefacto y por eso fallaba. Se construyó el ZIP con el builder oficial y se ejecutó la prueba sobre ese ZIP, sin quitar ni omitir el test.

## Verificación automatizada y paquetes

- Suite completa con los ZIP exactos: **555 tests, OK, 0 fallidos, 0 omitidos**.
- Los tests inspeccionan el ZIP de XStream, la ruta del consumidor Trakt y la búsqueda de series, además de los casos de Smart Search, perfiles, vistos parciales y cambio del almacén.
- `git diff --check`: PASS. AST Python y XML de la fuente Service y de ambos paquetes: PASS.
- Builds reproducibles; CRC correcto. Feed Testing generado solo en el directorio de Reports, sin publicación. MD5 del índice correcto; Stable `repo/addons.xml` idéntico a HEAD.

| Artefacto | Versión | SHA-256 |
|---|---:|---|
| Service | 0.4.68 | `442749bef4a9328bc9972d974ee3646d5c5f413c051e7d837174f68eb6dbac5d` |
| XStream Pro | 1.1.2.28~beta8 | `2f20d60a57249d6aff6f9fc45dfbdca9a66fc9405f78f44e9b6e77acbaa8ce4f` |
| Feed Testing local | — | `736e33256895d156ebfb8dcfadfbc5dea899709ad8c59fc79cfcb6968047c307` |

Los ZIP y el feed de prueba están en `Reports/2026-10-23-smart-search-watched-beta/`. El candidato privado Service 0.4.67 generado antes de cerrar la propagación de identidad quedó supersedido por 0.4.68; no se publicó.

## Datos y estado del Kodi activo

- Versiones instaladas, no modificadas: Service 0.4.66; XStream 1.1.2.28~beta7; Skin 1.2.32~beta1.
- El almacén actual contiene 1.028 vistos de película y 796 vistos de episodio bajo claves TMDb. El lector nuevo reconoció todos los 1.824 con la clave exacta. SHA-256 de `watched_movies_p1.json` coincide con el backup suministrado; `watched_episodes_p1.json` también coincide. No se alteraron bases de datos, favoritos, avances ni credenciales.
- `trakt_live/consent.json` no existe y `enabled()` devuelve false. No se habilitó ni ejecutó sincronización automática.
- Kodi responde como proceso activo, pero JSON-RPC en `127.0.0.1:8080` no está disponible y no hay control UI local disponible para usar el gestor de complementos ni verificar el estado del reproductor. Por eso no instalé ZIP directamente, no reinicié Kodi y no afirmo PASS_RUNTIME. Los paquetes están preparados para la instalación nativa.

## Logs y límites pendientes

- El log registra un refresco de catálogo fallido con `ProviderFetchError`, `provider_snapshot_incomplete`, duración 87.024 ms; no expone la causa subyacente. Es un fallo de consulta del proveedor preexistente, no una regresión demostrada de este cambio.
- El log también contiene solicitudes 404 a la raíz de imágenes TMDb sin ruta de imagen. `tmdb.image_url()` de XStream devuelve vacío ante una ruta ausente, y no se localizó en estos cambios el constructor del URL observado; se deja sin parche especulativo.
- Las advertencias `resumetime`/`totaltime` proceden de dependencias instaladas (`script.module.metadatautils` y `script.skinvariables`), no del código modificado.
- Pendiente de runtime en Kodi: instalar desde el gestor nativo, abrir Smart Search y comprobar los badges, navegar temporadas/episodios y verificar retorno/reproducción. No se verificó visualmente la interfaz.
