# Identidad disponible en Kodi Mac para Trakt — 2026-10-23

Estado: PARTIAL. Inspección local de solo lectura; sin instalación ni aplicación de estados.

## Recorrido demostrado

| Fuente | Identidad y persistencia | Uso seguro por Trakt |
| --- | --- | --- |
| Catálogos Xtream | 13.003 películas y 5.117 series; listados JSON por perfil con IDs internos, arte y texto; ningún ID externo nativo en la muestra completa | Pertenencia del ID del proveedor, no identidad TMDb |
| Smart Search (`provider_search_1.sqlite`) | 13.003 películas, 5.116 series; columnas de título, año, póster, fanart, sinopsis y puntuación, sin TMDb/IMDb | No establece identidad externa |
| Índice lateral de películas | 26.426 filas por categorías, 13.003 IDs internos únicos, cero TMDb no vacíos; offsets al catálogo JSON | Lectura rápida de miembros, no identidad externa |
| Ficha XStream | `_enrich_movie_info` obtiene `vod_info` bajo demanda o por prefetch y lo guarda como `data_cache_p1_vod_info_ID.json`; `_enrich_series_info` usa `series_info` | Sí, cuando el detalle del proveedor aporta un ID externo consistente con el miembro actual |
| Metadatos Premium | `premium_routes.enrich` busca TMDb por título/año si falta ID; conserva arte, reparto y el TMDb resultante en `premium_meta` JSON | Pista visual; la búsqueda por título no prueba que el stream corresponda a ese TMDb |
| Caché TMDb XStream | SQLite `meta_cache`: 43 películas y 17 series, indexadas por TMDb; `kv_cache` contiene 574 respuestas HTTP TMDb | No enlaza el TMDb con un ID Xtream |
| Videoteca Kodi (`MyVideos131.db`) | Cero películas, series, episodios y filas `uniqueid` | No ofrece relaciones para estos títulos plugin |
| Mis listas | SQLite con 4 listas y cero miembros; los miembros usan TMDb, no ID Xtream | No aporta enlace proveedor → TMDb |
| `series_changes_p1.json` | 38 inventarios de episodios; cero IDs TMDb en esos inventarios | Coordenadas e ID de episodio solo después de verificar la identidad de la serie |

El arte, la sinopsis y la puntuación ya llegan desde la lista del proveedor: Smart
Search tiene póster en 12.969 películas, sinopsis en 12.605 y puntuación en 12.567.
Esos campos no demuestran una correspondencia externa. Los caches de detalles
del proveedor y Premium ya eran leídos por los indexadores Trakt; no había una
base de datos de identidades omitida. La cobertura anterior procedía en parte
de aceptar resultados Premium obtenidos por título/año como identidad verificada.

## Corrección de seguridad

`verified_vod_records` y `verified_show_records` mantienen los datos Premium solo
como ampliación de una identidad ya establecida por catálogo, detalle del proveedor
o inventario. Un Premium aislado ya no permite marcar como vista una película ni
un episodio. Se añadieron dos pruebas de regresión específicas y se actualizaron
las tres fixtures que antes consideraban Premium suficiente por sí solo.

La corrección no cambia fichas, Smart Search, widgets, cachés ni estados reales.
Los ID Xtream nunca se interpretan como ID TMDb. Los detalles obtenidos cuando se
abra una ficha seguirán disponibles para el mismo indexador tras guardarse en
las cachés actuales; el checkpoint de generación ya detecta esos archivos.

## Cobertura y vista previa

| Métrica | Antes | Tras exigir identidad independiente |
| --- | ---: | ---: |
| Películas del proveedor con identidad externa | 172 | 170 |
| Series del proveedor con identidad externa | 121 | 0 |
| Episodios exactos | 35 | 0 |
| Registros Trakt emparejados | 43 | 8 |
| Registros Trakt pendientes de identidad | 1.787 | 1.822 |

Snapshot nuevo v2: 1.830 registros y 3.235 eventos. Preview de solo lectura:
2 películas vistas se añadirían, 3 ya constan vistas, 2 avances se actualizarían,
8 avances locales se conservarían y 1 quedaría diferido. No se añadirían episodios
ni avances nuevos. Cero identidades ambiguas detectadas con la evidencia actual;
**cero contenidos confirmados como ausentes**. Los hashes de los almacenes activos
permanecieron iguales. La cifra de 5 películas recuperables / 35 episodios citada
como línea base no equivalía a cambios nuevos seguros.

Tres muestras de preparación local: wall p50 435,993 ms, CPU p50 435,136 ms,
memoria Python máxima 77.827.783 bytes; comprobación de generación p50 1,780 ms.
No son mediciones de latencia visual. No hubo consultas externas en esta fase.

## Verificación y límite actual

497 pruebas PASS, cero fallos y cero omisiones, usando el ZIP candidato XStream
1.1.2.28~beta1 en las pruebas de integración. ZIP Service privado construido
desde estas fuentes, manifest 0.4.59, CRC correcto, SHA-256
`1bf51deb5b20b6efc6fe764c7f9c83e6906f20ea7b6fe4e0277f620befaf359c`.
Este ZIP tiene contenido distinto al candidato 0.4.59 anterior: **no debe
instalarse ni publicarse bajo la misma versión**; el versionado corresponde a una
fase posterior. No se modificó XStream instalado ni el paquete XStream candidato.

El proveedor Xtream resolvió DNS pero agotó el tiempo de conexión TCP en el
único probe autorizado. Sin obtener `vod_info` / `series_info` adicionales no se
puede demostrar más identidad externa. La interfaz visual puede seguir mostrando
arte correcto sin saber de forma verificable qué ID Trakt corresponde al stream.
La muestra requerida de fichas con Kodi abierto y la validación visual no se
ejecutaron; no se considera PASS_RUNTIME. La próxima investigación útil es medir
la cobertura tras recuperar la conectividad del proveedor y validar la procedencia
de cada nuevo ID antes de ampliar la importación.
