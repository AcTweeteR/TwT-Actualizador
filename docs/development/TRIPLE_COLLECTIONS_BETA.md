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

## Creación automática de listas futuras

- `collection_catalog.py` mantiene un UUID local estable, nombre, tipo y mapeos por servicio y cuenta en SQLite.
- `plan_creation` prepara la creación de listas únicamente cuando hay consentimiento global de creación automática y conexión verificada; no ejecuta operaciones remotas.
- `confirm_remote` exige comprobación posterior de identidad remota y cuenta, y bloquea el rebinding silencioso. Renombrar no pierde el UUID.
- **Falta implementar** adaptadores de creación de listas de Trakt/TMDb, compatibilidad real de tipos, captura de carpetas nuevas en XStream, detección de nombres duplicados remotos y sincronización de membresías. No anunciar esta funcionalidad como activa.
- Suite completa: 395 tests correctos, sin pruebas autenticadas contra servicios externos.

## Restricción solicitada: Mis Colecciones exclusivamente

- La creación de listas sincronizables exige `origin='mis_colecciones'`; se rechaza cualquier otra procedencia, incluso si la sincronización global está habilitada.
- La ruta de `Mis Colecciones` actual en el parche XStream muestra solo las dos carpetas tipadas Favoritos/Pendientes. No existe aún interfaz de creación de listas arbitrarias. No simular que existe.
- Pendientes/Favoritos continúan como colecciones tipadas con sus reglas propias, sin promover carpetas generales de XStream a listas remotas.
- La prueba de exclusión y la suite completa (396 pruebas) pasan. Sin despliegue, sin escrituras en Trakt/TMDb.

## Primera pantalla Kodi para listas personalizadas

- `collections_ui.py` permite crear y enumerar listas locales con UUID estable, sin escrituras remotas.
- `diagnostic_plugin.py` enruta `action=collections`, `action=collection_create` y `action=collection_open` al controlador nuevo.
- Entrada provisional: `plugin://service.actweeter/?action=collections`. No está enlazada todavía al árbol visual `Mis Colecciones` de XStream; la acción `collection_open` es un contenedor vacío.
- Falta gestionar miembros, renombrar/borrar desde UI, conectar la navegación XStream y validar en Kodi real antes de anunciar funcionalidad completa.
- Suite: 398 pruebas correctas.

## Auditoría previa a despliegue: miembros locales

- Se ha añadido almacenamiento local de miembros de colecciones con clave compuesta (lista, tipo, ID TMDb), sin duplicados, y comprobación de compatibilidad película/serie.
- Se ha detectado que pedir un ID numérico manual no verifica la identidad del título. El control de añadir contenido desde UI queda deshabilitado hasta una comprobación real contra TMDb o el detalle del proveedor.
- No hay reproducción funcional desde las filas de colección: se marcan no reproducibles para no simular una ruta de vídeo válida.
- La navegación de Mis Colecciones aún no está integrada en el menú principal de XStream; el acceso de servicio es provisional.
- Suite completa: 399 tests correctos. Sin pruebas E2E Kodi ni API autenticada. DESPLIEGUE BLOQUEADO.

## Renombrado local desde menú contextual

- `Mis Colecciones` incorpora acción contextual «Renombrar colección» que preserva el UUID y los mapeos. No renombra listas remotas hasta existir adaptadores autenticados y lectura posterior verificada.
- Suite completa: 400 pruebas correctas; sin despliegue.

## Enlace a navegación XStream (sin instalación)

- El parche de `premium_routes.py` añade la carpeta `Mis listas` en `Mis Colecciones` para películas y series; abre `plugin://service.actweeter/?action=collections`, manteniendo las rutas existentes de Favoritos y Pendientes.
- Se actualiza exclusivamente el hash fijado de `collections_patch`; no se sustituye el ZIP publicado `1.1.2.19`. Las pruebas comparan dicho ZIP histórico con sus módulos inalterados, y la ruta candidata por separado.
- La suite completa suma 400 tests, todos correctos, incluido el nuevo enlace del menú; no hay ejecución real en Kodi ni despliegue.
- La compilación de un nuevo ZIP queda BLOQUEADA: el ZIP local etiquetado `1.1.2.zip` tiene SHA-256 diferente al `upstream_release_zip_sha256` fijado en el manifiesto. No se relaja el hash ni se atribuye autenticidad a otro artefacto.
- El hash `local_runtime_sha256` de `premium_routes.py` continúa reflejando el ZIP publicado, no el candidato; debe regenerarse solo junto a un build auténtico completo.

## Despliegue Mac real 2026-10-22

- Kodi habitual del Mac cerrado antes del backup; perfil íntegro copiado a `~/Documents/Codex/kodi-master-backups/KODI_BEFORE_COLLECTIONS_BETA_20261022` (~2,2 GB). Comprobados SHA-256 de guisettings, profiles, addon.xml de XStream y servicio y favorites_1.json.
- ZIP original autenticado en `~/Documents/Codex/kodi-staging/xstream-1.1.2.9-audit/upstream-1.1.2.zip`, SHA-256 `915f45708670d07e789bb73b7390a7b5cf30175f818ef5da8ea18c9f13f537fe`.
- Paquete generado en `/tmp/actweeter-collections-candidate.zip`, SHA-256 `b0e97f005514bd1bd8d8486bdb742c84b9dbd90490fd301d807cdb367ce745c2`, versión `1.1.2.20~beta1`.
- Instalado en Kodi Mac habitual junto al servicio fuente 0.4.54; Kodi arranca y reconoce ambas versiones. Coincidencia exacta del addon.xml, addon.py y premium_routes.py instalados contra el ZIP y de collections_ui.py, collection_catalog.py, diagnostic_plugin.py instalados contra fuente.
- 400 pruebas automatizadas PASS. Prueba visual manual de navegación y creación de listas pendiente. No se han autorizado escrituras Trakt/TMDb; no se ha instalado en Lenovo ni alterado Stable.
- La edición del manifiesto `upstream.json` contiene también trabajo preexistente ajeno; no incluirlo en un commit sin revisión de ese trabajo.
