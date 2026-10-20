# AcTweeteR Performance 3.1 — Arranque en frío del índice de catálogo

Fecha: 20 de octubre de 2026. Candidata: XStream Pro **1.1.2.14**. PR de desarrollo: [#34](https://github.com/AcTweeteR/TwT-Actualizador/pull/34), rama `codex/performance3-catalog-cache`. Validación en dispositivos de esta candidata: **PENDIENTE**.

## 1. Alcance y evidencia previa

Se leyó íntegramente `Reports/2026-10-20-performance3-runtime/PERFORMANCE_3_RUNTIME_VALIDATION.md` y se contrastaron first_use_results, Directory_Latency_Raw/Summary, Content_Parity_Result y Fingerprints_v12/v13. Sus datos reales tienen prioridad sobre los benchmarks sintéticos de este documento.

| Medición real anterior | Lenovo TB330FU | Mac |
|---|---:|---:|
| 1.1.2.13, primera consulta sin índice, recientes | 17,712 s | 3,554 s |
| Segunda consulta | 1,175 s | 0,199 s |
| Tercera consulta | 1,282 s | 0,198 s |
| Recientes, mediana caliente 1.1.2.12 → 1.1.2.13 | 2,789 → 1,215 s | 0,443 → 0,193 s |
| Populares, Lenovo | 3,060 → 1,615 s | — |
| Tendencia, Lenovo | 3,030 → 1,524 s | — |
| Catálogo películas, Lenovo | 2,727 → 1,275 s | — |

La campaña anterior terminó 160 consultas sin errores; 16/16 combinaciones ruta/dispositivo conservaron cantidad y orden mediante huellas HMAC. El SQLite derivado ocupaba aproximadamente 2,6 MB. Esa campaña no instrumentó cada fase de la primera construcción: **no se atribuyen los 17,712 segundos completos a un tiempo interno medido**. Tampoco midió toda la carga visual.

Antes de trabajar se verificaron el worktree limpio y los commits existentes. PR #34 seguía abierta y en borrador, con validación NEEDS_FIX. PR #33 seguía abierta; su corrección CI ya estaba incorporada mediante el commit 9e8dc4f, sin duplicarla. main observado: 19f53e40be0a6553bcc956e1339eb8b119079b76. La versión 1.1.2.14 no estaba ocupada. No se cambiaron AGENTS.md ni instalaciones.

## 2. Causa raíz reconstruida

En 1.1.2.13, `premium_routes.indexed_movie_page` llama a `CatalogIndex.__init__`; si `_valid` falla, el constructor ejecuta `_ensure` sincrónicamente antes de poder devolver los primeros veinte registros. `_ensure` abre/mapea el JSON, extrae `_src`, recorre `_catalog_spans`, deserializa cada objeto, normaliza campos y registra offsets. Crea SQLite, inserta lotes de 512, confirma, publica mediante rename y finalmente consulta los veinte objetos. El widget paga todo el recorrido aunque solo necesite una página.

El código anterior ya agrupaba inserciones y utilizaba una sola confirmación. El problema principal demostrado en el dataset representativo es `_string_end`: recorría los bytes de cada cadena desde Python. Los textos y URLs largos multiplican ese coste; el dataset reducido de la primera Beta no lo representaba adecuadamente.

| Perfilado sintético: 26.337 objetos, JSON de 62.912.146 bytes | v13 | v14 |
|---|---:|---:|
| `__init__`, acumulado | 11450.448 ms (1 llamadas) | 1230.944 ms (1 llamadas) |
| `_catalog_spans`, acumulado | 10888.024 ms (26338 llamadas) | 701.460 ms (26338 llamadas) |
| `_value_end`, acumulado | 10871.759 ms (26339 llamadas) | 683.796 ms (26339 llamadas) |
| `_string_end`, acumulado | 10525.128 ms (421397 llamadas) | 0.011 ms (5 llamadas) |

Estos tiempos incluyen la sobrecarga de cProfile y están anidados: no se suman. En v13, `executemany` suma 53 llamadas y 41,291 ms; no explica el bloqueo principal. El artefacto `performance31-build-profile-2026-10-20.json` conserva los datos. El benchmark sin profiler figura más abajo.

## 3. Alternativas y solución seleccionada

| Estrategia | Evidencia / decisión |
|---|---|
| A: construcción rápida | Escaneo de cadenas/tokens con regex compilada sobre bytes; índices SQL después de insertar, lotes de 512 y una transacción. Reduce mucho la construcción, pero sigue costando más que cargar la primera página heredada. Insuficiente por sí sola. |
| B: fallback y construcción diferida | Elegida junto con A. La invocación del widget no construye el índice. Persiste una petición pequeña y devuelve la ruta original. El servicio de XStream existente construye el derivado durante inactividad. |
| C: construcción incremental entre invocaciones | Evaluada y descartada para esta corrección: exigiría checkpoints y coordinar snapshots/offsets parcialmente procesados. El trabajo fuera de la solicitud, con cancelación y reintento recuperable, elimina el bloqueo sin esa segunda máquina de estados. |

### Recorrido de la candidata

1. `CatalogIndex(..., build=False)` valida metadatos/esquema de solo lectura. Índices válidos de v13 conservan el esquema 2 y se reutilizan sin reescritura.
2. Si faltan, están desactualizados o son incompatibles, `IndexUnavailable` conduce inmediatamente al catálogo original. La petición contiene nombre local de caché, perfil numérico, tipo, huella opaca de generación y tiempo de reintento. No contiene proveedor, credenciales, títulos ni URLs. Si falla la escritura de la petición, el fallback sigue funcionando.
3. `service.py` de XStream integra `IndexBuildWorker` en su bucle ya residente. No cambia service.actweeter ni añade otro complemento/servicio. No se deja un hilo pendiente después de endOfDirectory en la invocación del widget.
4. El servicio comprueba la cola como máximo cada cinco segundos, exige al menos cinco segundos sin entrada y ausencia de reproducción. Cada petición tiene cinco segundos de gracia. Mantiene como máximo un trabajador; un flock no bloqueante evita construir dos veces entre servicios/procesos concurrentes.
5. La construcción comprueba cancelación al inicio, cada 512 objetos y antes de publicar. Entrada reciente (<2 s), reproducción o cierre del servicio cancelan el trabajo. Al cerrar se señala cancelación y se espera hasta dos segundos al trabajador del servicio. Las operaciones del sistema que ya estén ejecutándose no pueden interrumpirse instantáneamente.
6. La transacción trabaja en un archivo temporal único. Después se comprueban quick_check, cantidad, huella actual del JSON y cierre; solo entonces os.replace publica un índice completo. Ningún consumidor recibe tablas a medio construir.
7. Fallo/cancelación conserva la petición y reintenta con espera de 10 a 300 segundos. Reiniciar Kodi conserva la petición; se vuelve a construir desde el JSON autorizado. Bajo el bloqueo del constructor se limpian exclusivamente sus temporales derivados huérfanos. No se borran cachés personales.
8. Un error durante la consulta de un índice también solicita reconstrucción forzada, evitando depender únicamente de la validación superficial de su esquema.

Los usuarios pueden ver repetidamente el fallback mientras siguen navegando y no hay tiempo de inactividad. Es preferible conservar contenido correcto a forzar trabajo durante la interacción. Si el servicio existente no está disponible, el complemento sigue por la ruta original; la aceleración del índice ausente quedará pendiente.

### Invalidez, perfiles y datos dinámicos

| Cambio | Comportamiento |
|---|---|
| JSON actualizado, alta/baja/metadatos/categorías | Tamaño, mtime_ns e inode cambian la generación. El índice anterior no se utiliza. El fallback ve el catálogo actual; se solicita otra construcción. |
| Cambio durante la construcción | La comprobación final cancela la publicación; la siguiente consulta solicita la generación nueva. |
| Playlist/proveedor/perfil | Huella SHA-256 separada por perfil, credenciales de origen y tipo; además se verifica `_src` al construir. No se guardan credenciales en SQLite ni en las peticiones. |
| Filtros, categorías ocultas o control parental | Se calculan desde la configuración actual para cada consulta; no quedan congelados en el índice. |
| Rankings populares/tendencia | Se usan las listas externas cacheadas existentes; si no están vigentes se conserva la ruta original. |
| Vistos, favoritos, progreso, Trakt, continuar viendo | No se indexan como estados. Se mantienen los adaptadores y rutas existentes, fuera del alcance de esta corrección. |
| Fuente expirada/inaccesible | Se conserva la actualización/fallback original; no se añade red al constructor. |
| Reinicio/error/corrupción/poco espacio | Nunca se publica un temporal incompleto; fallback y petición recuperable. |

La huella usa atributos del archivo para evitar releerlo completo en cada widget. Una modificación externa que preserve deliberadamente tamaño, mtime e inode no se detectaría; no es el comportamiento normal del escritor de caché de XStream. No se introduce hash completo por petición.

## 4. Benchmarks sintéticos reproducibles

Equipo de desarrollo: macOS-27.0.1-arm64-arm-64bit-Mach-O. Python: 3.14.6 (main, Jun 10 2026, 10:03:53) [Clang 21.0.0 (clang-2100.0.123.102)]. Datos deterministas con texto largo, Unicode, comillas/barras escapadas y URLs de imágenes ficticias. No hay catálogos privados. Consulta de veinte películas recientes. El equivalente v12 carga JSON, filtra, ordena y deduplica; no ejecuta el proceso Python/Kodi completo. v13 se importa del ZIP anterior inmutable; v14 usa el módulo fuente de la candidata.

Diez repeticiones de ruta heredada; tres primeras construcciones por tamaño; treinta consultas calientes por versión. Se añade una campaña independiente de diez construcciones para el catálogo representativo de 26.337 elementos. P90 usa rango más próximo; el informe runtime anterior interpolaba P90, por lo que debe recalcularse con la misma convención para comparaciones. No se establecen umbrales sensibles al ruido del CI.

| Elementos | JSON MiB | v12 P50 ms | v13 primera P50/P90 ms | v14 primera fallback P50/P90 ms | Constructor v14 P50 ms | Caliente v13/v14 P50 ms | Índice v14 MiB |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1000 | 2.27 | 7.038 | 147.797 / 149.767 | 7.668 / 7.734 | 37.640 | 0.333 / 0.332 | 0.10 |
| 10000 | 22.76 | 74.936 | 1369.298 / 1373.342 | 75.064 / 75.346 | 320.691 | 0.333 / 0.334 | 0.80 |
| 26337 | 60.00 | 202.935 | 3592.770 / 3594.208 | 203.439 / 207.908 | 831.654 | 0.336 / 0.335 | 2.11 |
| 50000 | 113.93 | 390.041 | 6824.359 / 6842.892 | 394.972 / 401.416 | 1572.126 | 0.339 / 0.338 | 4.09 |
| 100000 | 227.90 | 796.486 | 13643.738 / 13645.074 | 804.603 / 812.654 | 3149.766 | 0.339 / 0.339 | 8.33 |

### Repetición representativa: diez primeras construcciones

| Estado sintético, 26.337 objetos | N | P50 pared ms | P90 ms | Mín / máx ms | P50 CPU ms |
|---|---:|---:|---:|---:|---:|
| v12 heredado | 10 | 214.863 | 222.463 | 207.064 / 228.257 | 214.703 |
| v13 primera | 10 | 3688.191 | 3794.387 | 3611.966 / 3816.876 | 3680.418 |
| v14 primera fallback | 10 | 207.060 | 215.579 | 198.082 / 221.202 | 207.012 |
| v14 construcción diferida | 10 | 870.319 | 885.873 | 832.434 / 903.892 | 849.742 |
| v13 caliente | 100 | 0.353 | 0.444 | 0.327 / 0.589 | 0.353 |
| v14 caliente | 100 | 0.351 | 0.392 | 0.328 / 0.683 | 0.351 |
| v14 apertura/validación | 100 | 0.303 | 0.336 | 0.277 / 0.390 | 0.303 |

Las diferencias entre campañas reflejan variabilidad local, no una mejora adicional del código. Las medidas de CPU son tiempo de proceso, no porcentaje de CPU del dispositivo.

Cada comparación comprueba igualdad de diccionarios completos y has_more, no solo IDs. El tiempo caliente de la tabla corresponde a consultar un objeto CatalogIndex ya abierto; el JSON de evidencia también mide apertura/validación por separado. Ninguna cifra de esta tabla mide arranque Python, ListItems, JSON-RPC, imágenes ni renderizado Kodi. El constructor se mide directamente con la misma implementación que usa el trabajador; las pruebas de ciclo de vida verifican su integración con el servicio.

### Fases internas de la construcción nueva, 26.337 objetos

Una repetición instrumentada, tiempos de pared. Las fases desglosadas están contenidas en duration.

| Fase | ms |
|---|---:|
| `index.build.close` | 0.072 |
| `index.build.commit` | 2.392 |
| `index.build.decode` | 161.582 |
| `index.build.duration` | 831.283 |
| `index.build.fields` | 49.406 |
| `index.build.insert` | 20.984 |
| `index.build.publish` | 0.111 |
| `index.build.scan` | 567.949 |
| `index.build.source` | 0.019 |
| `index.build.sql_indexes` | 10.271 |
| `index.build.tables` | 0.459 |
| `index.build.validate` | 3.288 |

En esa muestra, la telemetría registra 0,814 s de CPU usuario y 0,009 s de CPU sistema para unos 0,832 s de pared: el trabajo sintético es predominantemente CPU. El escaneo sigue siendo la fase mayor, pero ocurre fuera de la solicitud. No se extrapola este reparto al almacenamiento de Lenovo.

### Memoria y almacenamiento

Procesos nuevos aislados por versión/tamaño, una muestra por caso. RSS pico absoluto incluye intérprete, módulos, páginas mmap y SQLite; no equivale a memoria Python asignada ni garantiza la RAM en Android. Baseline del proceso antes de construir: aproximadamente 30 MiB.

| Elementos | RSS pico v13 MiB | RSS pico v14 MiB | Índice v13/v14 bytes |
|---:|---:|---:|---:|
| 1000 | 33.00 | 33.03 | 106496 / 106496 |
| 10000 | 54.39 | 54.34 | 880640 / 839680 |
| 26337 | 93.44 | 92.23 | 2338816 / 2207744 |
| 50000 | 147.19 | 147.08 | 4526080 / 4284416 |
| 100000 | 261.41 | 261.31 | 9220096 / 8732672 |

Con 26.337 objetos, tracemalloc mide 129.282.429 bytes pico en la consulta heredada frente a 192.243 bytes en la consulta caliente. Estas medidas son separadas de los tiempos. El índice guarda campos/offsets, no otra copia completa de posters, plots ni URLs. La construcción solo mantiene un lote de 512 filas, pero mmap puede hacer residentes muchas páginas; no se afirma una reducción sustancial del RSS de construcción. Al crear los índices SQL después de insertar, el fichero resultante también es menor en esta muestra.

Los contadores ru_inblock/ru_oublock son cero en estos procesos de macOS, y io_delta aparece vacío: **no permiten medir IOPS ni latencia física de almacenamiento**. No se interpreta cero como ausencia de E/S. Temperatura, presión de memoria, consumo por hilo y rendimiento Android quedan para runtime; no se han consultado dispositivos.

### Reproducción de benchmarks

Desde la raíz de la rama, sin Kodi y sin perfil real:

```sh
python3 source/0.4.32/tools/benchmark_catalog_cold_start.py --repeats 10 --build-repeats 3 --output /tmp/performance31-scaling.json
python3 source/0.4.32/tools/benchmark_catalog_cold_start.py --sizes 26337 --repeats 10 --build-repeats 10 --output /tmp/performance31-reference.json
python3 source/0.4.32/tools/benchmark_catalog_cold_start.py --profile-only 26337 --output /tmp/performance31-profile.json
python3 source/0.4.32/tools/benchmark_catalog_cold_start.py --memory-only --output /tmp/performance31-memory.json
```

Los archivos de referencia están en `docs/development/benchmarks/performance31-*.json`. Las carpetas temporales contienen exclusivamente datos sintéticos y se eliminan al finalizar.

## 5. Telemetría y pruebas

Se conserva performance_diagnostics_enabled, desactivado por defecto, y los relojes monotónicos/correlación existentes. Hay contadores index.missing/valid/stale/invalid, build.started/failed/rows/storage_bytes, fallback.used, rebuild.scheduled/completed/failed, query.rows y tiempos query.duration/build.duration. El constructor agrega scan/decode/fields/insert; emite una línea por intento, no una línea por película. No se registran argumentos, excepciones con contenido privado ni títulos. La telemetría del trabajador tiene correlación propia, independiente de la consulta que lo solicitó.

Archivos responsables:

- `source/0.4.32/third_party/xstream/provider_catalog_index.py`: constructor estricto, parser, publicación y cola/trabajador.
- `source/0.4.32/third_party/xstream/patches/1.1.2/actweeter-catalog-index.patch`: integración en premium_routes y service.py de XStream.
- `source/0.4.32/tests/test_catalog_index_deferred.py`: casos nuevos de fallback/recuperación, servicio y paridad con v12/v13.
- `source/0.4.32/tools/benchmark_catalog_cold_start.py`: comparación y perfilado reproducibles.
- `tools/benchmark_kodi_widget_provider.py`: instrumentación externa JSON-RPC, selección de rutas/propiedades.

**Resultado local: 196 pruebas ejecutadas, 196 correctas**, mediante unittest discover (10,810 s). Se mantienen todas las pruebas anteriores. La suite cubre ausencia, reutilización v13, índice válido/desactualizado/corrupto/incompatible/parcial, catálogo vacío/actualizado, error SQLite/lectura/publicación, poco espacio simulado, dos widgets/dos trabajadores, cancelación por lotes, fuente cambiada en construcción, petición tras reinicio y temporales huérfanos. Las pruebas usan archivos temporales reales y fallos inyectados; no simulan como superada una caída física de Kodi o un disco Android lleno. Se comparan filtros, orden, paginación, rankings, diccionarios completos, URLs e imágenes ficticias.

El parche mantiene los constructores de ListItem y los adaptadores de reproducción/Trakt sin cambios funcionales. La suite no sustituye reproducción ni QA visual real.

## 6. Candidata y construcción

Commit de código: `40c48ba5dba2983827d5ac4390260bedd10a9c75`. Los 130 archivos Stable bajo repo/ se compararon individualmente con los bytes del main base y coinciden.

ZIP: `docs/testing/repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.14.zip`.

SHA-256: `3a31eb9d778c4ae446baa5b4d57f4cc2c4b7d2c63f79a639f3ab79aaa20d29e1`.

Manifest: `manifests/xstream-performance31-cold-start-20261020.json`. Los hashes del fuente/parche/runtime están fijados en upstream.json. Procedencia: upstream 1.1.2, commit 1aa3e67da7c03c6acc3ec7e1ca579a7f645220f4, licencia original CC BY-NC 4.0 preservada. La candidata no cambia esos términos.

Se construyó dos veces desde el ZIP upstream exacto con SHA-256 915f45708670d07e789bb73b7390a7b5cf30175f818ef5da8ea18c9f13f537fe. Los ZIP son idénticos byte por byte; CRC, addon.xml, versión y fuentes Python se verifican en el constructor. El índice Testing se generó con tools/build_test_channel.py, solo como archivos de esta rama sin fusionar. No se ejecutó publicación.

```sh
python3 source/0.4.32/tools/build_xstream_package.py --upstream-zip /ruta/al/upstream-verificado.zip --output /tmp/xstream14-a.zip
python3 source/0.4.32/tools/build_xstream_package.py --upstream-zip /ruta/al/upstream-verificado.zip --output /tmp/xstream14-b.zip
cmp /tmp/xstream14-a.zip /tmp/xstream14-b.zip
shasum -a 256 /tmp/xstream14-a.zip
python3 -m unittest discover -s source/0.4.32/tests -v
git diff --check
```

Stable: todos los archivos bajo repo/ deben seguir idénticos al main base, no solo addons.xml. Hash de repo/addons.xml: ecb76872ab80cdd4cd4230292682fcbda651b4750ddc5e247a01d29b470185a3. No hay cambios de skin, service.actweeter, AGENTS.md, ajustes globales ni perfiles reales.

## 7. Plan exacto para Remote Desktop Commander

**Esta sección es un procedimiento futuro. No se ha ejecutado durante el desarrollo.**

### A. Preparación y primera carga

1. Verificar PR/checks y descargar el ZIP de la rama/commit aprobado. Comprobar SHA-256/CRC/versión contra el manifest; no usar una versión homónima de otra rama. Mantener copias verificadas de addon_data, perfiles Xtream, ajustes, watched/resume/favoritos y bases personales. Guardar hashes localmente, sin volcar datos privados en GitHub.
2. Preparar un perfil de pruebas aislado en cada dispositivo. Para frío, copiar en él el JSON autorizado y la configuración necesaria desde una copia protegida, omitiendo **solo en esa copia** índices derivados y peticiones previas. No borrar índices ni cachés del perfil personal. Mantener Trakt sin acciones remotas. No reiniciar Kodi Master para simular el frío. Si no se puede aislar sin riesgo, dejar ese escenario pendiente.
3. Instalar la candidata mediante un canal Testing de validación aprobado que la sirva. Este commit prepara el índice, pero el feed público actual no ofrece automáticamente un ZIP de una PR sin fusionar. Remote Desktop Commander debe obtener autorización para la distribución de validación antes de utilizarlo. No instalar sobrescribiendo archivos de addon.
4. Activar temporalmente la telemetría de XStream en el perfil aislado. Verificar servicio existente activo. Registrar versión, fuente/generación, cantidad de catálogo, bytes, estado térmico/CPU/memoria, ausencia de sidecar y procesos. No cambiar preferencias globales de actualización.
5. Ejecutar exactamente una consulta de recientes con el comando siguiente; recopilar tiempo externo, counts index.missing/fallback.used/rebuild.scheduled y respuesta de 20 tarjetas más EXPANDIR cuando corresponda. El plugin no debe registrar build.started dentro de su propia correlación.

```sh
python3 tools/benchmark_kodi_widget_provider.py --port 19091 --name Lenovo --samples 1 --widgets movie-recent --properties title art > /ruta/evidencias/Lenovo-first-use.jsonl
# Repetir en Mac con --port 9090 --name Mac y archivo distinto.
```

6. Dejar la interfaz sin entrada/reproducción y capturar el log agregado del servicio: build.started, fases, filas/bytes, duration y rebuild.completed. Comprobar que se produce un sidecar válido; no asumir un plazo fijo de cinco segundos. Registrar arranque del servicio y tiempo hasta finalización. Mientras se construye, comprobar respuesta UI y una consulta concurrente: debe usar el fallback, sin esperar al bloqueo del constructor.
7. Repetir en el perfil aislado simulando actividad continua y reproducción apropiada: la construcción debe posponerse/cancelarse, sin bloquear ni dañar el JSON. Dejar luego inactividad y verificar recuperación. Para obtener diez primeras cargas, utilizar diez copias sintéticas/aisladas o snapshots autorizados; nunca borrar las cachés personales para repetir.

### B. Caliente: repetir las ocho rutas equivalentes

El script runtime original confirmó view=series_recent para series recientes. Se conservan exactamente las rutas del registro, actweeter_expand=1 y limit=20. Se añaden favoritos como QA aparte, sin mezclarlo con las 160 referencias. Se usan las mismas propiedades title/art solicitadas en el benchmark anterior.

```sh
python3 tools/benchmark_kodi_widget_provider.py --port 19091 --name Lenovo --samples 10 --properties title art --widgets movie-recent movie-popular movie-trending movie-catalog series-recent series-popular series-catalog series-continue > /ruta/evidencias/Lenovo-v14-hot.jsonl
python3 tools/benchmark_kodi_widget_provider.py --port 9090 --name Mac --samples 10 --properties title art --widgets movie-recent movie-popular movie-trending movie-catalog series-recent series-popular series-catalog series-continue > /ruta/evidencias/Mac-v14-hot.jsonl
```

Ejecutar primero solo un dispositivo si se instrumentan recursos con alta frecuencia. Para repetir el intercalado Lenovo/Mac del benchmark previo, usar su mismo calendario con destino de evidencias nuevo; no volver a ejecutar benchmark_1.1.2.13.py sin cambiar su carpeta de salida, porque sobrescribe la evidencia anterior. Recoger P50/P90/min/max/variabilidad, errores, cantidad y huella ordenada, y recalcular ambos P90 con la misma regla. Nunca comparar una ruta con distinto número de resultados como si fuese equivalente.

Muestrear CPU agregada y por hilo, RSS/PSS, hilos, E/S y temperatura si ADB/sysctl permiten lecturas. Usar rutas/PIDs detectados, no grabar comandos con credenciales. Correlacionar recursos por intervalo con el log del plugin y el del constructor. Registrar cache hit/miss, lecturas originales, consultas externas y fases de index.query.duration. Si una medida no está disponible, marcar N/D. No elevar permisos ni eludir restricciones para completarla.

### C. Paridad y carga visual

Comparar v12/v13/v14 sobre el mismo snapshot, perfil, configuración y estados cacheados. Obtener huellas HMAC ordenadas de ID, tipo, metadatos esenciales, artwork y ruta de reproducción en memoria; conservar la clave solo localmente y no publicar URLs/títulos. El benchmark sencillo aporta una huella de etiquetas/uniqueid, no prueba por sí solo todos los metadatos ni artwork. Exigir cantidad/orden/contenido iguales en las 16 rutas/dispositivo previas.

Abrir Inicio/Películas/Series, Spotlight y categorías; buscar, abrir ficha, favoritos y continuar viendo; verificar vistos/progreso sin cambiarlos innecesariamente. Comprobar Trakt sin alterar estados remotos y reproducción/tráilers en un perfil de pruebas adecuado. Comparar hashes de ajustes y bases relevantes; justificar toda mutación esperable de caché frente a cualquier cambio personal.

Grabar pantalla con referencia temporal monotónica/entrada visible: primer título útil, primer póster, imágenes visibles completas, respuesta a navegación y ficha. El tiempo Files.GetDirectory no equivale al renderizado. Si el vídeo no permite un marcador fiable, declarar esa métrica no medible. Comprobar que el trabajo idle no degrada animaciones ni navegación.

### D. Recuperación controlada y aceptación

En el perfil aislado: índice ausente, cabecera/esquema inválido, catálogo actualizado con altas/bajas, cambio de perfil/proveedor y cancelación/fallo de publicación. Simular errores de escritura solo con datos sintéticos y permisos de esa carpeta; no llenar el almacenamiento del dispositivo ni alterar permisos personales. Nunca modificar playlists/estados remotos para provocar estos casos. Confirmar fallback, ausencia de parciales y recuperación posterior.

| Puerta runtime | Referencia de aceptación |
|---|---|
| Primera consulta Lenovo | Próxima a la heredada (~2,8 s recientes), sin bloqueo de 17,712 s ni build síncrono en su correlación. |
| Caliente Lenovo | Conservar aproximadamente 1,2 s recientes, 1,6 s populares, 1,5 s tendencia, 1,3 s catálogo; comparar P90 y ruido de sesión. |
| Mac caliente | Conservar aproximadamente 0,19 s recientes, sin empeoramiento relevante. |
| Correctitud | Igualdad completa; sin errores, pérdida de estados ni contaminación entre perfiles. |
| Servicio/recuperación | Cola termina en índice válido cuando existe inactividad, cancelación recuperable y un solo constructor. |
| Seguridad | Ajustes personales íntegros, sin cambios en Stable ni preferencias globales. |

Estas referencias son objetivos, no resultados de 1.1.2.14. Si hay regresión de contenido, no aprobar aunque el tiempo mejore. Si hay contención del constructor, medirla antes de ajustar límites. Al finalizar, desactivar telemetría, comprobar restauración del estado personal y decidir aprobación o NEEDS_FIX. No publicar ni fusionar automáticamente.

## 8. Prioridades restantes

| Prioridad | Hallazgo / acción | Confianza y validación | Riesgo |
|---|---|---|---|
| 1 | Eliminar la construcción síncrona y acelerar el scanner (implementado) | Alta en código/sintético; falta confirmar primera carga y vida del trabajador en Kodi real. | Contención durante idle; se debe medir. |
| 2 | Conservar consultas calientes y resultados v13 (implementado) | Pruebas y benchmarks equivalentes; faltan 160 consultas runtime v14. | Cambios de snapshot/configuración durante pruebas. |
| 3 | Arranque Python ~460–473 ms Lenovo medido anteriormente | Sigue sin optimizarse; analizar imports por fase en otra Beta. | Mezclarlo aquí impediría atribuir las mejoras. |
| 4 | Medir pósteres, fanart/renderizado y competencia con widgets | No hay medida nueva de carga visual; no se concluye que SQLite la resuelva. | Calidad/funcionalidad: no se reducen imágenes ni widgets. |

No se han cambiado algoritmos de ranking, cantidades de widgets, calidad visual, Trakt, reproducción, favoritos ni preferencias globales. La siguiente decisión se basa en la campaña runtime, no en extrapolar los milisegundos sintéticos al Android.
