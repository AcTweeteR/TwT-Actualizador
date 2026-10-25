# Beta24 — lanzamiento ARCADE y auditoría de estados vistos

## Versiones

- Skin AcTweeteR `1.2.32~beta10` (único complemento propio modificado).
- Service AcTweeteR `0.4.85` y XStream Pro `1.1.2.28~beta20`, sin cambios.
- IAGL `4.0.6`, servido por el repositorio oficial `repository.zachmorris 1.0.4`.
- SHA-256 de la skin: `91d14d8941451c7a0a47611a692ab6cebb74ab4583446796d162ebd52981c254`.
- SHA-256 del índice Testing: `d13d8504ba3fd2d3391f6a3baa576e174999522ad78305efaa6a2e90516647d7`.
- MD5 declarado para `addons.xml`: `3ab15cf8cd5d9237d73dc3d798a6384e` (coincide con `addons.xml.md5`; SHA-256 del archivo de checksum: `167c513980683a53cddc79b1679f1c9ad1b4a4f0bad7e583516b7a4708a053c1`).

## A. Auditoría Trakt

| Responsabilidad | XStream Pro | script.trakt | Service AcTweeteR | Resultado |
|---|---|---|---|---|
| OAuth y API | OAuth, consultas de interfaz, historial, listas, colección, recomendaciones y progreso | OAuth/sync de biblioteca Kodi | credenciales consentidas y lecturas de contraste | implementado; autenticación y sincronización remota en vivo no verificadas en esta validación |
| Películas y episodios vistos | proyección local sobre identidades exactas y propiedades nativas Kodi | sincronización de elementos de biblioteca y scrobbling | snapshot de solo lectura y puente explícito de acciones | no se hicieron escrituras remotas |
| Progreso y scrobbling | progreso de UI y scrobbling desde reproducción XStream | scrobbling de reproducción Kodi | no duplica el observador de reproducción de script.trakt | riesgo de eventos duplicados conservado; no se retiraron almacenes ni sincronizadores sin prueba de equivalencia |
| Watchlist/colecciones/recomendaciones | endpoints de XStream | funciones de biblioteca propias del add-on | no es fuente de esos datos | funciones se conservan en XStream |
| Check visual | `playcount`, resume e identidad verificada | proyecta datos de biblioteca Kodi | invalida estados/widgets al cambiar datos | preferencia de indicador habilitada; comprobación visual de todas las superficies sigue pendiente |

La última comparación autenticada registrada en Beta22 daba 1.830 registros locales y 3.235 eventos coincidentes con la exportación, y 1.028 IDs TMDb de películas vistas coincidentes. No se repitió una consulta remota autenticada en esta ejecución. Las seis operaciones dudosas siguen pendientes: cinco episodios sin identidad externa inequívoca y una reanudación sin referencia exacta de reproducción. No se forzaron por título ni se borraron.

## B. Checks de vistos

| Superficie | Código/pruebas | Kodi Mac Master |
|---|---|---|
| Películas, series, temporadas y episodios | propiedades `playcount`/resume, inventario completo para marcar temporada/serie, fallo cerrado ante inventario desconocido; suite aprobada | `PARTIAL`: la preferencia del indicador está habilitada, pero no se encontró una muestra visible con estado confirmado para certificar los checks |
| Widgets, Smart Search, fichas, colecciones, favoritos y pendientes | contratos y pruebas automatizadas incluidos en la suite | `NOT_TESTED` visualmente por superficie; no se alteró historial Trakt para fabricar ejemplos |
| Continuar viendo | la proyección local conserva resume y la invalidación selectiva de widgets está cubierta por pruebas | `PARTIAL`: el comportamiento y el renderizado en la interfaz no se certificaron en esta sesión |

No se atribuye sincronización remota demostrada a partir de una instantánea local. XStream y `script.trakt` mantienen responsabilidades existentes; no se añadió un sincronizador duplicado ni se retiraron funciones.

## C. Arcade

- Fuente: proyecto oficial de Zach Morris y su repositorio firmado/verificado `repository.zachmorris 1.0.4`; no se incorporaron forks.
- IAGL `4.0.6` queda instalado y habilitado por el instalador nativo de Kodi. El ZIP de juegos, ROMs y colecciones no se descargó.
- El primer lanzamiento muestra los términos de Archive.org. Se eligió “Do not Agree”; no se aceptó en nombre del usuario.
- El registro de Kodi mostró que `ActivateWindow(Programs,plugin://plugin.program.iagl/,return)` no podía abrir este complemento (`xbmc.python.pluginsource`, proporciona `video game`). La Beta24 cambia la acción a `RunAddon(plugin.program.iagl)`, el built-in de Kodi para lanzar complementos, y fija una regresión del contrato del menú.
- La posición y el nombre `ARCADE` después de `RIVULET` se vieron en Home; no hubo recorte ni solapamiento en la captura. Rivulet conserva su entrada.
- El icono mostrado en Master reutiliza el glifo rojo existente de Rivulet por la fuente de iconos compartida; es legible pero no es un mando dedicado.
- Con Beta24, al seleccionar ARCADE se ejecutó `RunAddon(plugin.program.iagl)`, Kodi registró `IAGL: Lets Play!` y cargó `IAGL-TOU.xml`; la pantalla de términos de Archive.org apareció. Se seleccionó “Do not Agree”, volvió a Home y no se aceptaron condiciones. Kodi registró `GetDirectory`/`RunAddon` al cerrar el flujo rechazado; la pantalla sí se abrió antes de ese rechazo. La navegación interna posterior queda sin probar mientras no se acepten los términos. RetroPlayer y disponibilidad de núcleos no se probaron porque no se ejecutaron juegos.

## Pruebas y despliegue

- Suite completa contra los ZIP exactos de XStream y skin Beta24: `649 passed`, `0 skipped`.
- Skin construida dos veces con resultado idéntico (SHA-256 indicado arriba). El índice y el MD5 reproducidos desde la Beta candidata coinciden byte por byte con los publicados en `docs/testing`.
- Validaciones automatizadas de CRC, identidad/versiones, dependencias, XML, AST Python y empaquetado están incluidas en la suite y aprobaron.
- Revisión de cambios: solo cambió el paquete Skin y sus pruebas; XStream y Service no se versionaron ni empaquetaron como cambios nuevos. Stable no participa.
- CI del instalador Beta y CI de publicación Pages finalizaron con `success` (ejecuciones `40150337002` y `40150336673`). Pages sirve el índice Testing con checksum `3ab15cf8cd5d9237d73dc3d798a6384e` y el ZIP Beta10 con SHA-256 indicado arriba.
- Instalación real mediante el actualizador nativo de Kodi: PASS. El gestor mostró temporalmente `0%` mientras comprobaba actualizaciones; al terminar, Kodi registró Skin `1.2.32~beta10`, Service `0.4.85` y XStream `1.1.2.28~beta20`. La tabla `installed` de `Addons33.db` confirmó que los complementos propios están habilitados y proceden de `repository.actweeter.testing`. No se copiaron archivos directamente a `addons/`.
- Prueba real de ARCADE: PASS hasta abrir la pantalla IAGL de términos; navegación interna después del acuerdo: NOT_TESTED. Stable conserva el SHA-256 de índice `14adccd38d1004e3b1a547025377d1c1c091eadff95cf6233a47ebcf986bf5b1`.

## Limitaciones conocidas

- No se acepta el acuerdo de Archive.org ni se descargan juegos. Esto impide validar navegación interna posterior a la pantalla de términos.
- Trakt conserva estado `AUTHORIZATION_UNVERIFIED` en Kodi Master; no se hicieron escrituras remotas.
- Indicadores visuales de Trakt, Smart Search y widgets siguen `PARTIAL`/`NOT_TESTED`: no se encontró una muestra con estado remoto/local inequívoco que permitiera certificarlos sin alterar Trakt.
- PVR IPTV Simple registró la carga de 1.291 canales, 46 grupos y EPG durante la sesión; no se comprobó una navegación manual de canales ni se inició reproducción. No se concluye PASS_RUNTIME de PVR.
- El log muestra un error de resolución al terminar el flujo de IAGL después de rechazar sus términos (`GetDirectory` para plugin IAGL / `RunAddon`). No se observó otra excepción de la skin en el tramo revisado; no se atribuye la resolución fallida a la acción inicial porque IAGL ya había cargado su pantalla de términos.
