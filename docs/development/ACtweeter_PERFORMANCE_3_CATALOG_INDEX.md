# AcTweeteR Performance 3.0 — índice del catálogo de películas

## Estado

Desarrollo local terminado para la primera etapa de películas. La Beta candidata XStream Pro 1.1.2.13 y el índice Testing están preparados en esta rama; no se han instalado en Kodi ni publicado. Las mediciones en Lenovo y Mac quedan pendientes para Remote Desktop Commander.

## Causa medida y alcance

Las mediciones de XStream 1.1.2.12 muestran que cada petición vuelve a cargar y deserializar el JSON completo de `xtream_streams_movie`: 26.337 películas. En Lenovo, leer el JSON cuesta aproximadamente 0,98–0,99 s y preparar el catálogo alrededor de 1,02 s; construir 20 ListItem cuesta unos 31 ms. La consulta Xtream no fue la causa en las rutas medidas. Las duraciones internas están anidadas y no deben sumarse.

La etapa implementada cubre películas de Catálogo, Recientes y Populares/Tendencia cuando el ranking ya está en caché. Series, favoritos, continuar viendo, reproducción y rutas de actualización mantienen el recorrido existente. Si la caché de ranking vence, no se cambia su generación: esa petición usa el recorrido anterior.

## Arquitectura

El JSON de XStream sigue siendo la fuente autoritativa. Un SQLite lateral, separado por perfil, proveedor y tipo, guarda solo el ID del proveedor, nombre normalizado, año, categoría, TMDb ID, fecha `added`, ordinal y offsets de bytes al objeto JSON original. No duplica URLs de reproducción, imágenes, descripciones ni credenciales. Al construir un ListItem se leen y deserializan únicamente los objetos visibles.

La tabla usa índices por orden de catálogo, fecha de añadido e identidad nombre/año. Recientes y catálogo recorren resultados del índice hasta reunir la página y un elemento de margen; la página siguiente y el botón de expansión solo necesitan saber si existe otro resultado. La vista popular resuelve los rankings cacheados a IDs de proveedor y conserva el rechazo de títulos ambiguos.

Categorías ocultas, categorías de control parental, elementos ocultos, categoría seleccionada, paginación y deduplicación se aplican en cada petición. Favoritos, progreso, vistos y Trakt siguen fuera del índice y mantienen las funciones existentes.

## Invalidación y recuperación

La clave lateral incorpora una huella SHA-256 del perfil, proveedor y tipo, sin guardar esos valores. La validez compara tamaño, `mtime_ns`, inode y versión del esquema con el JSON. El escritor de caché actual usa reemplazo atómico, por lo que cada actualización genera una huella distinta. Los filtros de usuario y las categorías se consultan dinámicamente.

La reconstrucción recorre el JSON con `mmap`, valida `_src`, crea un SQLite temporal con nombre único y lo publica con `os.replace`. Dos constructores simultáneos pueden hacer trabajo redundante, pero no publican una base parcial: la última base completa sustituye a la anterior. Si el índice está corrupto o el almacenamiento falla, la ruta indexada falla cerrada y el dispatcher continúa por la ruta original. El JSON y los ajustes no se modifican durante una lectura del índice.

Limitación: la huella depende del reemplazo atómico que usa XStream. Una edición externa del JSON en el mismo inode, conservando tamaño y fecha, no queda detectada; ese tipo de edición no forma parte del escritor soportado.

## Benchmark sintético

Ejecutado en macOS con 10 repeticiones por tamaño, datos sintéticos deterministas y 20 resultados solicitados. `legacy` mide parseo JSON completo, filtrado/ordenación/deduplicación y selección; `indexed_warm` mide solo la consulta caliente y lectura de 20 objetos. `build_ms` es una única construcción inicial. No son tiempos de Kodi ni de Lenovo.

| Entradas | JSON | Índice | Construcción inicial | Catálogo: anterior p50/P90 | Catálogo: índice caliente p50/P90 | Recientes: anterior p50/P90 | Recientes: índice caliente p50/P90 | Pico Python, anterior → índice |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1.000 | 0,15 MB | 0,11 MB | 23,3 ms | 2,15 / 3,68 ms | 0,24 / 0,35 ms | 2,32 / 2,35 ms | 0,23 / 0,26 ms | 0,86 → 0,15 MB |
| 10.000 | 1,56 MB | 0,88 MB | 151,9 ms | 22,14 / 23,61 ms | 0,35 / 0,43 ms | 23,90 / 24,61 ms | 0,35 / 0,39 ms | 7,55 → 0,15 MB |
| 26.337 | 4,15 MB | 2,32 MB | 387,8 ms | 62,86 / 68,67 ms | 0,51 / 0,57 ms | 67,14 / 74,79 ms | 0,49 / 0,53 ms | 20,70 → 0,15 MB |
| 50.000 | 7,92 MB | 4,49 MB | 729,4 ms | 122,90 / 136,81 ms | 0,52 / 0,55 ms | 132,96 / 148,06 ms | 0,54 / 0,61 ms | 37,62 → 0,15 MB |
| 100.000 | 15,87 MB | 9,16 MB | 1.452,3 ms | 259,23 / 287,65 ms | 0,57 / 0,61 ms | 282,15 / 316,69 ms | 0,59 / 0,63 ms | 75,23 → 0,15 MB |

En 26.337 filas, los tiempos sintéticos calientes de la selección bajaron ~99,2% en catálogo y ~99,3% en recientes. El índice ocupa ~56% del JSON sintético y conserva solo columnas de consulta; el coste de almacenamiento y su tiempo de primera construcción deben validarse con el catálogo real. El pico Python se midió con `tracemalloc`, no incluye RSS completo del proceso ni las páginas mapeadas del sistema operativo.

Resultados crudos y reproductor: [benchmark JSON](benchmarks/performance3-catalog-index-2026-10-20.json) y [benchmark_provider_catalog_index.py](../../source/0.4.32/tools/benchmark_provider_catalog_index.py).

## Pruebas locales

Las ocho pruebas nuevas cubren orden y equivalencia de objetos/URLs, categorías ocultas, deduplicación, orden de ranking, aislamiento de proveedor y perfil, caché vacía, modificación de catálogo, corrupción, concurrencia de construcción y aplicación del parche al paquete Testing 1.1.2.12. La herramienta compara IDs, cantidad y `has_more` frente a la ruta anterior para catálogos sintéticos de 1.000, 10.000, 26.337, 50.000 y 100.000 filas.

La integración no cambia la skin ni AcTweeteR Service. La instrumentación previa continúa desactivada por defecto; añade tiempos de apertura/consulta y contadores de hit, build, invalidación, elementos indexados y bytes del índice cuando se activa.

## Paquete candidato

- Add-on: `plugin.video.xstream-pro` 1.1.2.13.
- Base upstream 1.1.2, commit `1aa3e67da7c03c6acc3ec7e1ca579a7f645220f4`, CC BY-NC 4.0 conservada.
- SHA-256 del ZIP upstream: `915f45708670d07e789bb73b7390a7b5cf30175f818ef5da8ea18c9f13f537fe`.
- SHA-256 de la Beta candidata: `d6a3a9b5bd88b6c858972d4fbe0a5f2d01fe507f2ab4758989b9a719fbd1147e`.
- El constructor se ejecutó dos veces; los ZIP resultaron idénticos. CRC, manifiesto, versión, Python empaquetado y hashes pasan las validaciones del constructor.
- El índice Testing en esta rama incorpora 1.1.2.13. El índice Stable `repo/addons.xml` conserva SHA-256 `ecb76872ab80cdd4cd4230292682fcbda651b4750ddc5e247a01d29b470185a3`.

## Validación runtime pendiente

1. Verificar los backups existentes y el SHA-256 del ZIP candidato antes de cualquier operación.
2. Remote Desktop Commander instalará desde un Testing publicado por separado; esta rama no publica ni instala el paquete.
3. Mantener activada temporalmente `performance_diagnostics_enabled` y registrar el estado de ajustes antes de la prueba.
4. En Mac, ejecutar `python3 tools/benchmark_kodi_widget_provider.py --port 9090 --name Mac --samples 10`. En Lenovo, crear el forward TCP 19091→9090 y ejecutar el mismo script con `--port 19091 --name Lenovo-TB330FU --samples 10`. La primera muestra representa la primera consulta natural; las siguientes capturan caliente.
5. El script cubre catálogo, recientes, populares, tendencia, series recientes/populares/catálogo, continuar viendo y favoritos. Compara conteos y una huella SHA-256 del orden/IDs sin imprimir títulos, URLs ni credenciales. Buscar, TV/EPG, navegación visual, primer póster y respuesta del mando requieren observación separada en Remote Desktop Commander; JSON-RPC no mide de forma fiable cuándo termina el renderizado.
6. Ejecutar además inicio, navegación Home→Películas/Series/TV/Buscar y apertura de fichas; repetir los widgets equivalentes con la misma cuenta y red. Separar datos de primera construcción y caché caliente sin borrar cachés.
7. Comparar duración externa JSON-RPC e interna `catalog_index.open`, `catalog_index.query`, `provider.streams`, `cache.json.read`, ListItem y finalización. Capturar CPU, memoria, cantidad de consultas y errores.
8. Comparar IDs, orden, cantidad, categorías, URLs de reproducción, metadatos, películas, series, favoritos, progreso, Trakt y reproducción.
9. Revisar que el índice se invalida al refrescar catálogo y al cambiar de perfil; forzar una corrupción solo en una copia de prueba, nunca en el perfil real.
10. Desactivar telemetría y comprobar que el ajuste previo queda restaurado. Publicación requiere aceptación de runtime y revisión del cambio.

## Limitaciones y riesgos

- Las cifras sintéticas son de macOS, no predicen el rendimiento Android ni la carga visual de Kodi.
- La primera consulta después de una actualización antigua construye el índice de forma síncrona; el benchmark sintético tardó ~387 ms para 26.337 objetos en este Mac. La medición de primera carga en Lenovo es obligatoria.
- La ruta Popular/Tendencia usa el índice solo con la lista de ranking vigente; un ranking vencido conserva el recorrido antiguo.
- Series no están optimizadas todavía. Arranque Python, red, carga/render de pósteres y primer ListItem siguen sin cambios.
- No se ha probado el comportamiento dentro de Kodi 21.3, Android, macOS o tvOS. La Beta queda pendiente de validación en dispositivos.
