# Colecciones triples · Kodi / Trakt / TMDb

## Estado validado 2026-10-22

- Motor puro `triple_collections.py` añadido a la rama `codex/trakt-sync-mac-2026-10-21`. Sin desplegar y sin operaciones remotas.
- Modelo: dos colecciones separadas, Pendientes y Favoritos, para películas y series únicamente. El contenido local exige correspondencia TMDb verificable; canales y accesos directos no se exportan.
- Importación inicial de las tres fuentes: unión aditiva, sin eliminación. Rechaza snapshots incompletos, cuentas ajenas, duplicados de fuentes y tipos incorrectos.
- Las diferencias posteriores se calculan desde baselines persistidos completos; aún faltan coordinador transaccional, checkpoints, origen del cambio, vector por elemento y mediación de conflictos. **No usar `delta` directamente para borrar contenido remoto**.
- Kodi/XStream usa `favorites_1.json`; 'Favoritos' contiene una serie en el Mac y los folders de Pendientes pueden no existir. No se ha alterado el archivo.
- Trakt tiene OAuth propio autorizado en XStream; `script.trakt` continúa como único scrobbler. TMDb tiene consulta de metadatos/clave API, pero no se ha validado en este servicio una sesión propia de usuario con permisos para listas.
- Antes de activar escrituras: autorización explícita de cuenta TMDb, descubrir listas reales de ambas cuentas, respaldar colecciones, validar todas las páginas, confirmar cuentas/perfiles, operar con dry-run y verificar lectura posterior a cada escritura.
- Stable y tablet Lenovo intactas. No anunciar sincronización triple funcional hasta pruebas reales en Kodi y ambas APIs.

## Auditoría incremental de cuentas y seguridad

- `account_registry.py` describe Trakt/TMDb y admite nuevos servicios mediante descriptores validados, sin almacenar tokens.
- `collection_journal.py` conserva snapshots completos y verificados por cuenta, origen y colección en SQLite. No transforma fallos de red en listas vacías. La observación por defecto es solo lectura y no avanza el checkpoint.
- Pruebas específicas de aislamiento entre cuentas, rechazo de snapshots incompletos, symlinks de base de datos y confirmación explícita.
- Suite completa: 388 pruebas superadas. No hay pruebas de extremo a extremo con APIs autenticadas ni prueba dentro de Kodi; no activar sincronización todavía.
- Pendiente crítico: confirmar contratos oficiales TMDb de watchlist/listas v3/v4, flujo OAuth de usuario, permisos y paginación; implementar conectores de transporte independientes, almacenamiento seguro de credenciales y UI Kodi; detectar cambios concurrentes, conflictos, reintentos e idempotencia; respaldar antes de activar escritura; probar Mac y Lenovo antes de publicación.

## Conector TMDb v3 aislado

- `tmdb_account_transport.py`: solicitud de token temporal, URL de autorización, canje por sesión, lectura de identidad de cuenta, lectura paginada de watchlists de películas/TV y operación de watchlist protegida por aprobación explícita.
- El conector es inerte sin un requester HTTPS inyectado y credenciales del usuario. Las pruebas usan respuestas simuladas; no hay cuenta TMDb real vinculada ni escrituras remotas.
- La sesión de TMDb no se copia a XStream ni a script.trakt. Aún faltan almacenamiento de sesión local seguro, interfaz de autorización en Kodi y confirmación por relectura tras escrituras.
- Auditoría: 392 tests correctos. Detectado y corregido durante pruebas el paso de paginación como parámetro URL en lugar de cuerpo GET.
