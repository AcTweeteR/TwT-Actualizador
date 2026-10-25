# Beta24 — lanzamiento ARCADE y auditoría de estados vistos

## Versiones

- Skin AcTweeteR `1.2.32~beta10` (único complemento propio modificado).
- Service AcTweeteR `0.4.85` y XStream Pro `1.1.2.28~beta20`, sin cambios.
- IAGL `4.0.6`, servido por el repositorio oficial `repository.zachmorris 1.0.4`.
- SHA-256 de la skin: `91d14d8941451c7a0a47611a692ab6cebb74ab4583446796d162ebd52981c254`.
- SHA-256 del índice Testing: `d13d8504ba3fd2d3391f6a3baa576e174999522ad78305efaa6a2e90516647d7`.
- SHA-256 del contenido de `addons.xml.md5`: `32b61b09bb7892342fa9d3a7bc20d905`.

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
- Tras reintentar el arranque de ARCADE con Beta24 se documentará si se llega a IAGL. La navegación más allá del acuerdo requiere consentimiento expreso a los términos externos. RetroPlayer y disponibilidad de núcleos no se probaron porque no se ejecutaron juegos.

## Pruebas y despliegue

- Suite completa contra los ZIP exactos de XStream y skin Beta24: `649 passed`, `0 skipped`.
- Skin construida dos veces con resultado idéntico (SHA-256 indicado arriba). El índice y el MD5 reproducidos desde la Beta candidata coinciden byte por byte con los publicados en `docs/testing`.
- Validaciones automatizadas de CRC, identidad/versiones, dependencias, XML, AST Python y empaquetado están incluidas en la suite y aprobaron.
- Revisión de cambios: solo se sube la versión/cambio de acción de Skin, sus pruebas y el artefacto Testing. Stable no participa.
- CI, publicación, instalación por el actualizador estándar y prueba real de la acción ARCADE: pendientes de completar en la ejecución que genera esta versión.

## Limitaciones conocidas

- No se acepta el acuerdo de Archive.org ni se descargan juegos. Esto impide validar navegación interna posterior a la pantalla de términos.
- Trakt conserva estado `AUTHORIZATION_UNVERIFIED` en Kodi Master; no se hicieron escrituras remotas.
- Indicadores visuales de Trakt, Smart Search, widgets, PVR y reproducción real quedan `PARTIAL`/`NOT_TESTED` hasta observar muestras verificadas.
