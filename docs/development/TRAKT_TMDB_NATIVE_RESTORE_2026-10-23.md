# Importación de vistos Trakt por identidad TMDb — 23/10/2026

## Resultado

Se separó la proyección de vistos destinada a las vistas TMDb de la reconciliación del catálogo Xtream. La primera usa claves namespaced de TMDb dentro del almacén coordinado `WatchedMovies`; la segunda conserva la resolución estricta de referencias del proveedor. El importador TMDb no consulta ni necesita el catálogo/end-point Xtream.

Las claves nuevas son `tmdb:movie:<id>` y `tmdb:episode:<id>:s<season>:e<episode>`. La ruta TMDb de XStream y el menú de visto usan las mismas claves. Las entradas numéricas antiguas de `WatchedMovies`/`WatchedEpisodes` no se interpretan como estado TMDb: podrían ser IDs Xtream coincidentes. Se conservan intactas en disco, pero no se importan ni se cuentan como vistos TMDb. Las marcas explícitas `tvshow:<id>` y `season:<id>:<season>` siguen funcionando.

Los tombstones TMDb `False` bloquean la aplicación y prevalecen en la interfaz. La cola acepta el destino `tmdb` únicamente para operaciones `watched` con TMDb ID numérico válido y coordenadas exactas de episodio. La ruta `provider` sigue requiriendo referencia y verificación del catálogo. No se añadieron escrituras a Trakt ni scrobbling; `script.trakt` mantiene esa responsabilidad.

Los registros de reproducción remotos no se convierten en `ResumePoints`: XStream indexa esos puntos por URL del proveedor, y una identidad TMDb no autoriza a inventar una URL. Esta candidata conserva los avances locales y difiere la importación de playback sin referencia local exacta.

## Previsualización sobre el perfil Mac

Se leyó el export verificado `READ_ONLY_EXPORT_VERIFIED` de 1.830 registros y 3.235 eventos, y los almacenes activos `watched_movies_p1.json`, `watched_episodes_p1.json` y `resume_points_p1.json`. No se modificaron.

| Resultado | Cantidad |
|---|---:|
| Películas vistas importables por TMDb | 1.028 |
| Episodios vistos importables por TMDb | 796 |
| Vistos ya presentes en la clave TMDb namespaced | 0 |
| Conflictos/tombstones TMDb | 0 |
| Registros vistos sin TMDb ID válido | 0 |
| Entradas de playback diferidas por falta de URL local verificada | 6 |

Los JSON de vistos y reanudación tuvieron SHA-256 idénticos antes y después de la previsualización. Los contadores son una proyección de solo lectura, no una restauración aplicada. Los IDs numéricos heredados no se consideran evidencia TMDb ni se suman como existentes; requieren una política/migración explícita si se desea recuperar estados antiguos cuya procedencia ya no puede distinguirse.

## Verificaciones

* Suite completa contra el ZIP beta7: **527 pruebas PASS, 0 fallos, 0 omitidas**.
* Integración contra el ZIP XStream candidato: ejercita el consumidor real, `history.py` del paquete, persistencia coordinada en almacenes temporales, acuse durable, repetición idempotente, ausencia de catálogo Xtream, colisión de IDs y temporada cero mediante la función `_is_watched` extraída del paquete. Resultado beta7: **PASS** (2 pruebas de integración); no es runtime dentro de Kodi.
* Previsualización usando el código extraído del ZIP exacto Service 0.4.66 contra los almacenes reales Mac: mismos recuentos (1.028/796), cero conflictos y hashes sin cambio. Es una ejecución del módulo empaquetado fuera del proceso Kodi, no `PASS_REAL`.
* Pruebas del importador/previsualización aislados: cobertura de películas, episodios, temporadas cero, IDs ausentes, tombstones, colisiones numéricas y no escritura. **PASS** (3 pruebas tras el ajuste de colisiones).
* Reproducibilidad: dos builds por artefacto deben producir SHA-256 idéntico; comprobar hashes finales al cerrar la suite.
* Índice Beta privado: creado localmente con el builder oficial; valida repositorio Testing 1.0.2 y dependencia Service/XStream beta5. No se publicó.
* Kodi Master runtime: **NOT_TESTED**. No se instalaron los candidatos ni se ejecutó una ruta de sincronización dentro de Kodi.
* Stable, Lenovo y Apple TV: no modificados.

## Artefactos candidatos privados

Versiones propuestas: Service **0.4.66**, XStream **1.1.2.28~beta7**, skin **1.2.32~beta1** (sin cambios funcionales de skin; solo paquete de distribución reproducible). La beta6 privada se descartó después de que la prueba revelara que XStream normalizaba temporada `0` a cadena vacía; beta7 corrige la normalización y esa regresión pasa en la suite.

| Artefacto local | SHA-256 |
|---|---|
| `/private/tmp/actweeter-service-tmdb-beta7-final.zip` | `39fc85a92df473bdd6d8674f1289f5beac69efe23277e32c1b2bf5443341383c` |
| `/private/tmp/actweeter-xstream-tmdb-beta7.zip` | `92083f189572b0eb8b456b17ebfb67953144e890a97f0e633d968f84bdc365b7` |
| `/private/tmp/actweeter-skin-tmdb-beta7.zip` | `3e7cf74ad59cd7d9b3ee8be9b399f4974816890a2f2dd31ed9cfea3e9121d08b` |
| Índice privado `addons.xml` | `a9d2fe9b3aba53c46211ccbbd37dded6d01501b111a3d096da1d06e7a9db906d` |

El MD5 del índice privado es `354ba9174d9fe10cb18c79e19b079b50`. Los tres ZIP se reconstruyeron dos veces con SHA-256 idéntico, CRC correcto, raíz/manifiesto válidos y sin cachés, bases de datos, `.pyc` ni userdata. El índice local final es `/private/tmp/actweeter-tmdb-beta7-final-private-index/addons.xml`; anuncia Testing 1.0.2, Service 0.4.66 y XStream beta7 con dependencia coherente. No modifica el canal público Testing ni Stable.

## Actualización estándar (no ejecutada)

Tras aprobación de los resultados, licencia y publicación Beta, actualizar desde Kodi por el repositorio `repository.actweeter.testing` usando el gestor nativo de complementos (Buscar actualizaciones/Actualizaciones disponibles). Actualizar XStream y Service según la dependencia declarada, reiniciar Kodi solo si Kodi lo solicita y validar primero la vista TMDb. No instalar ZIP manualmente ni habilitar sincronización automática como parte de esta candidata. La importación requiere la autorización/consentimiento ya existente; la validación de runtime debe ocurrir antes de aplicar al perfil real.

## Riesgos y límites

1. No hay `PASS_REAL`: el comportamiento visual solo está probado mediante el predicado real empaquetado, no dentro del proceso Kodi.
2. Los seis puntos de reanudación Trakt no pueden trasladarse con seguridad a XStream sin URL de proveedor verificada; el preview no los aplica.
3. Los vistos históricos guardados bajo IDs numéricos sin namespace son inherentemente ambiguos. La candidata los conserva, pero ya no los trata como TMDb para evitar colisiones falsas con Xtream.
4. Publicación Beta y revisión de licencia/redistribución XStream quedan pendientes.
