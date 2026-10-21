# Smart Search 2.0 — desarrollo y aceptación

Fecha: 2026-10-21. Estado: **PARTIAL; no publicado ni fusionado**.
Rama: `codex/smart-search-2026-10-21`.
Base: `ba87dbc352d5e41059d2dc21808dd275ebe5634b` (Performance 3.1).
Continúa la primera candidata `3d4a8c3`; no sustituye el buscador por otro addon.
Implementación 2.0: commits `46d4a5e` y `a5ff314` (locales; no push ni PR).
Revalidación final: servicio **0.4.48**, skin **1.2.30~beta5**; ver el cierre al final.
El informe `SMART_SEARCH_2026-10-21.md` conserva la evidencia de esa primera candidata.

## Alcance y protección

- Solo fuentes de este worktree y ejecución de desarrollo en Kodi Mac original 21.3.
- XStream **1.1.2.14 habilitado**, comprobado mediante JSON-RPC antes y durante las pruebas.
- No se han instalado estos paquetes, sobrescrito addons del Mac ni copiado perfiles.
- No se han usado Lenovo, Apple TV, QA, ni modificado feeds Stable/Testing.
- No hay nuevas dependencias obligatorias ni copia de código/assets de los proyectos estudiados.
- El índice real del proveedor se abre en lectura; el benchmark verifica tamaño/mtime sin cambios.
- No se publican logs completos, rutas de streams, credenciales ni bases de datos.
- No se modifica la configuración ni autenticación Trakt. En la primera pasada se evitó
  VOD por scrobbling activo. La autorización posterior del usuario permite las pruebas
  breves de película/episodio y sus efectos de progreso/scrobbling; se realizaron en el cierre.

## Comparativa de alternativas: código y licencias

Se inspeccionaron manifests, licencias, implementación de búsqueda/fichas y revisiones
concretas en clones temporales de lectura. La actividad indicada es la revisión consultada,
no una garantía de mantenimiento ni una certificación runtime multiplataforma.

| Proyecto / revisión | Compatibilidad y licencia observadas | Ventaja concreta | Decisión |
|---|---|---|---|
| [TMDb Helper](https://github.com/jurialmunkey/plugin.video.themoviedb.helper/tree/82322a612add92dc11410da6084abfffbf874ea5), 6.18.0, actualizado 19-10 | Python >=3.0.1; GPL-3.0-or-later; añade requests/PIL/signals/jurialmunkey/infotagger/qrcode | Rutas comunes de detalles, reparto, créditos y relacionados; caché de API | Reutilizar las rutas y API exportada del **BINGIE Helper ya disponible**, no instalar otro helper ni copiar reproductores/claves |
| [Skin Info Service](https://github.com/MikeSiLVO/script.skin.info.service/tree/989aad6a930bf6148afcfbd2df9febe10862fd58), 2.0.1~beta12, actualizado 18-10 | Python >=3.0.1, JSON >=13.5.0; GPL-3.0-only | `lib/dialog/actor.py`: filmografía/carrera; `lib/infrastructure/workers.py` y `tasks.py`: trabajo diferido y sincronización | Implementación propia pequeña de ficha bajo demanda y pila de contexto; no añadir su servicio, edición de metadatos ni operaciones Trakt |
| [Arctic Fuse 3](https://github.com/jurialmunkey/skin.arctic.fuse.3/tree/926eb1de9ea8899471c31b518ecd528272cb4503), 3.4.1, actualizado 20-10 | `xbmc.gui` 5.17.0; **CC BY-NC-SA 4.0**; requiere skinvariables/texturemaker/helper | `1080i/Includes_Search.xml`: edit nativo, filas/modos, panel informativo, autocomplete y estados vacíos | Adoptar conceptos de filas, foco estable y estados, conservando recursos AcTweeteR; no copiar XML/assets ni su arquitectura generada |
| [Global Search Omega oficial](https://kodi.tv/addons/omega/script.globalsearch/), 9.0.7 | GPL-2.0-only; Python 3.0.0; disponible para Omega. La entrada del repo-scripts se hereda de `matrix`, no estaba directamente en `omega` | Categorías y regreso con contexto para biblioteca local; JSON-RPC Kodi | Mantener agrupación y navegación propias; no reemplazar el buscador IPTV/EPG por uno limitado a biblioteca |
| [XStream Pro](https://github.com/Pesicp/XStreamPro/tree/307c981165e42188827f207153b5df4d2c6e5deb), publicación 04-06 | **CC BY-NC 4.0**, atribución PesicP; iconos Tabler MIT. Distribuye ZIP; inspeccionados 1.1.2 y 2.0.4 sin instalarlos | Búsqueda global Xtream/M3U y rutas reales de temporadas/episodios/selección de fuente | Conservar nuestro 1.1.2.14/Performance 3.1 y sus rutas. No migrar a 2.x ni adoptar búsquedas entre perfiles o copiar historiales |

Global Search upstream [revisión b7656ec](https://gitlab.com/ronie/script.globalsearch/-/tree/b7656ecdc727583d139bdcf9eb79e0e3736761a0)
es 9.2.2 y declara Python 3.0.2: no se considera automáticamente compatible con Omega
por ser más reciente. Se inspeccionó `lib/gui.py` (historial por nivel y consultas a la
biblioteca), distinguiéndolo de la versión 9.0.7 del repositorio Kodi.

La compatibilidad anterior es revisión de manifest/API, no PASS runtime en Android/tvOS.
No se redistribuyen paquetes de estos terceros en la candidata. Se conserva la dependencia
opcional preexistente de `plugin.video.tmdb.bingie.helper`; sin ella funcionan catálogo/EPG.

### API TMDb realmente utilizada

Se contrastaron en el BINGIE Helper instalado las rutas `search`, `details`, `cast`, `crew`,
`recommendations`, `similar`, `stars_in_movies`, `stars_in_tvshows`, `crew_in_movies` y
`crew_in_tvshows` (`addon/consts.py`, `items/basedir.py`).

Para títulos alternativos se usa `tmdbbingiehelper_lib.api.tmdb.api.TMDb.get_request_lc`,
exportado expresamente por `addon/permissions.py`. No se importan claves ni se eluden
permisos. Se aprovecha su caché; máximo tres consultas nuevas por búsqueda, 80 alias/título,
64 entradas locales. Fallos opcionales no impiden mostrar el proveedor.

**Limitación verificada:** ejecutar el archivo suelto con `RunScript(ruta)` carece del
contexto registrado de addon que necesita parte de la API del helper. Se captura el fallo
y se conserva la búsqueda por JSON-RPC, títulos canónicos/originales y catálogo local.
El adaptador de alias pasa tests con API simulada, pero su funcionamiento con el addon
instalado desde Beta sigue **NOT_TESTED**. No se ha falseado `xbmcaddon.Addon()`.

## Cambios implementados

### Motor y rendimiento

- Coincidencias exactas/normalizadas antes de aproximadas; prioriza términos iniciales
  del título y conserva normalización de acentos, artículos y orden de palabras.
- Deduplicación por identidad/tipo; ediciones equivalentes con año conocido se agrupan,
  remakes ambiguos de año desconocido no se fusionan por suposición.
- Unión TMDb→IPTV exige tipo, identidad de título y año compatibles. No confirma
  disponibilidad por popularidad ni simple parecido. Los alias pasan la misma validación.
- Los trabajadores comparten una instantánea inmutable de los 18.004 títulos; una
  recarga reemplaza listas/diccionarios, no modifica el snapshot publicado.
- Trabajadores separados para catálogo, EPG y TMDb; una consulta pendiente reemplazable
  por fuente. Resultados obsoletos descartados mediante generación/serial.
- Debounce local 120 ms, EPG 450 ms, remoto 650 ms. Una petición plugin de Kodi en curso
  no puede cancelarse: se descarta su respuesta, no se afirma cancelar la red subyacente.
- EPG tiene cancelación mediante SQLite progress handler y no hace una petición por canal.
- Caché TMDb 24 consultas/10 minutos, enfriamiento de 10 s tras error. La interfaz
  conserva resultados locales mientras falla el enriquecimiento externo.

### Fichas y navegación

- Overlay propio con póster, sinopsis/biografía, original, géneros y dirección disponibles.
- Reparto y equipo con fotografías; directores identificados se priorizan para no quedar
  cortados por el límite visual. Filmografía de películas/series, recomendaciones y similares.
- Historial de ocho niveles conserva filas, filtros, selección y foco, sin repetir consultas
  al volver. Cambio de perfil descarta contexto y comprueba el perfil antes de ficha nativa.
- Series IPTV → temporadas → episodios mediante **rutas devueltas por XStream**, sin
  fabricar URLs de reproducción. Validación de host, modo, perfil e ID de serie; episodios
  duplicados del proveedor se agrupan por serie/temporada/episodio.
- Insignias visibles EN IPTV / TMDb / PERSONA / TV-EPG. Datos descubiertos no disponibles
  no reciben acciones de reproducción.
- Fila nativa horizontal y contenedor vertical, teclado físico, QWERTY propio y diálogo
  nativo Kodi. **Dictado tvOS no validado**; no se promete búsqueda progresiva mientras
  el diálogo modal nativo no entrega el texto. El edit/QWERTY propios sí son progresivos.
- Máximo visual de 40 resultados/fila y 100 elementos por consulta de temporadas/episodios;
  no se presenta esto como una filmografía exhaustiva o paginación infinita.

### Archivos principales

- `source/0.4.32/addons/service.actweeter/resources/lib/smart_search_engine.py`
- `source/0.4.32/addons/service.actweeter/resources/lib/smart_search_sources.py`
- `source/0.4.32/addons/service.actweeter/resources/lib/smart_search_ui.py`
- `source/0.4.32/addons/service.actweeter/resources/skins/Default/1080i/AcTweeteRSearch.xml`
- Manifiestos/changelogs servicio/skin; README; builders e identidades de tests de candidata.
- `source/0.4.32/tests/test_smart_search.py`, pruebas de empaquetado/metadatos/autoplay.
- `tools/benchmark_smart_search.py` y JSON de resultados sin contenido privado.

No se cambian Skin Shortcuts, XStream, el coordinador de tráilers ni Trakt. El cierre
acota tres expresiones/fallbacks compartidos de la skin para el contexto modal de información.

## Benchmark reproducible con catálogo real

Resultado: `docs/development/benchmarks/smart-search-2-real-mac-2026-10-21.json`.
Baseline: motor de `3d4a8c3`; candidata: motor de esta rama. 18.004 títulos reales.
Host Python 3.14.6/macOS arm64; Kodi ejecuta su propio Python, por tanto no son cifras
del renderer ni del proceso completo Kodi. Tres índices nuevos, 20 rondas calientes,
200 prefijos simulados sobre el catálogo real. No se vacía la caché de disco del SO.

| Medida | Antes | Después | Interpretación |
|---|---:|---:|---|
| Índice nuevo + consulta, P50 | 148,446 ms | 148,937 ms | Prácticamente igual; no hay mejora demostrada de arranque |
| Índice nuevo, P90 | 163,429 ms | 149,794 ms | Tres muestras; no extrapolar a todos los dispositivos |
| Pico tracemalloc, dos trabajadores | 37,862 MiB | 19,720 MiB | ~48 % menos por compartir snapshot, no memoria total de Kodi |
| Prefijos calientes, P50 | 0,492 ms | 0,594 ms | Pequeño coste adicional de ranking/deduplicación |
| Prefijos calientes, P90 | 1,189 ms | 1,155 ms | Similar |
| `maquina guerra`, P50 / resultados | 0,215 ms / 2 | 0,264 ms / 2 | Acentos/artículos no bloquean coincidencias |
| `matrix`, P50 / resultados | 0,257 ms / 6 | 0,297 ms / 6 | Ranking mejorado, no más rápido |
| `matrx`, P50 / resultados | 0,665 ms / 6 | 0,692 ms / 6 | Tolerancia a error conservada |
| `guerra`, P50 / resultados | 1,437 ms / 50 | 1,780 ms / 50 | Consulta ambigua amplia |

En Kodi real se observó `matrx`: seis resultados, 207 ms de motor con índice recién
creado y **391 ms** cambio de consulta→publicación local (`search.local_ready_ms`, incluye
debounce/pump). Es una observación, no un percentil ni comparación UI antes/después.
Detalles Matrix vía helper: 629 ms; búsqueda nativa proveedor Matrix: 229 ms; temporadas
Breaking Bad: 929 ms; episodios: 427 ms. Son solicitudes individuales con caché no controlada.

Repetición (ruta del índice debe facilitarse localmente, nunca subir la base):

```sh
python3 tools/benchmark_smart_search.py --index /ruta/privada/provider_search_1.sqlite \
  --output /ruta/local/resultados.json
python3 -m unittest discover -s source/0.4.32/tests -q
```

## Pruebas reales en Kodi Mac

La ventana se ejecutó **desde las fuentes**, usando el EventClient oficial y RunScript,
sin instalar addons ni crear un perfil QA. Entradas mediante CUA, no eventos simulados
en tests. Consultas locales JSON-RPC verificaron versión/habilitación y ausencia de playback.
Las capturas se observaron durante la sesión; no se incluyen logs personales en Git.

| Caso | Resultado | Evidencia / limitación |
|---|---|---|
| XStream habilitado 1.1.2.14 | PASS_RUNTIME | Addons.GetAddonDetails enabled=true antes/después |
| Escritura física y resultados progresivos | PASS_RUNTIME | `matrix` y `breaking bad`: filas con carátulas reales sin modal de espera |
| Consulta errónea `matrx` | PASS_RUNTIME | Seis títulos IPTV; fallo remoto no elimina resultados |
| Ficha avanzada Matrix | PASS_RUNTIME | Póster, 1999, original The Matrix, sinopsis, géneros y Lana/Lilly Wachowski |
| Reparto → Keanu Reeves → filmografía → Back | PASS_RUNTIME | Fotografías; 12 películas y una serie confirmadas en proveedor; regreso a Matrix/selección sin nueva consulta |
| Breaking Bad → temporadas | PASS_RUNTIME | Cinco temporadas recibidas del proveedor y mostradas |
| Temporada 1 → episodios | PASS_RUNTIME | Siete episodios únicos, T1/E1…E7, imágenes y sinopsis; proveedor devolvía duplicados |
| Episodio piloto → overlay | PASS_RUNTIME | Título correcto S01E01 y sinopsis; no se reproduce automáticamente |
| Cruceta y Back entre contextos | PASS_RUNTIME | Resultados, overlay, temporadas, episodios y regreso a Home |
| Apertura ficha nativa heredada del episodio | PARTIAL | Título/sinopsis correctos, **logo y datos secundarios conservan contenido de Home**; corrección fuente preparada, no instalada |
| Teclado nativo Kodi | PASS_RUNTIME apertura/cancelación | Diálogo español QWERTY visible y cancelación conserva consulta; dictado no probado |
| QWERTY propio | PASS_RUNTIME casos ejecutados | Cruceta: letras, Ñ, espacio, borrar, LISTO y Back; ver cierre |
| EPG: búsqueda → programa → canal | PASS_RUNTIME | `noticias`: 30 programas; Noticias 24H/La 1 → botón explícito Ver canal en directo; imagen de RTVE observada y JSON-RPC type=channel, speed=1. Canal de prueba detenido con X |
| Persona por nombre incompleto | PASS_RUNTIME | `tom crui` → Tom Cruise → filmografía IPTV → biografía → Back; director incompleto no repetido |
| VOD película/episodio | PASS_RUNTIME | Matrix y Breaking Bad S01E01: reproducción, avance temporal, pantalla completa, parada y retorno; ver cierre |
| Ratón | PASS_RUNTIME casos ejecutados | Limpiar, Matrix Reloaded, volver a resultados, QWERTY, categoría Personas y Biografía; no certifica todos los hitboxes |
| Táctil físico | NOT_TESTED | Solo revisión estructural; ningún dispositivo Android/tvOS utilizado |
| Android / tvOS / voz | NOT_TESTED | Dispositivos no tocados |

### Fallos descubiertos, corregidos y pendientes

1. Una rama de navegación a temporadas había quedado en el trabajador local y causaba
   `NameError` al ejecutar la búsqueda. Se movió al trabajador remoto; se añadieron tests
   que ejecutan ambos trabajadores, no solo inspección de texto. Se repitió Breaking Bad
   en Kodi y se recorrieron temporadas/episodios con éxito.
2. La cabecera de exploración del proveedor decía «Títulos relacionados»: corregida y
   cubierta por test. Es texto de presentación, no un cambio en rutas.
3. La ficha nativa heredada mezcla título del episodio con logo/datos anteriores de Home.
   También reproducido con Matrix: logo de My Nanny Stole My Life y duración 1h23,
   frente a 2h16 de Matrix en el reproductor. `Home.ShowViewSubMenu=show` permanece
   durante el modal; `IsMainMenuOpened` no excluía DialogVideoInfo y habilitaba los
   fallbacks de Home. Corrección compartida y tests añadidos, sin limpiar propiedades
   globales. Su efectividad visual instalada continúa pendiente: ver bloqueo del cierre.
4. El lanzamiento desde archivo carece del contexto de addon requerido por la API opcional
   de alias. No se sustituye por importación privada ni se considera validado con mocks.
5. Las llamadas remotas de directorio no exponen cancelación física: una petición lenta
   puede retrasar el enriquecimiento posterior, pero no el trabajador local ni la EPG.
6. Abrir un canal cierra la ventana de búsqueda; al detener la TV se vuelve a Home,
   no se restaura automáticamente esa consulta EPG. No se promete continuidad de contexto
   en ese recorrido de reproducción; la pila de contexto sí se verificó al explorar personas.

## Validación automatizada y paquetes

Primera pasada: **252 pruebas PASS_AUTOMATED**, incluidas 56 Smart Search. Cierre: **262
pruebas PASS_AUTOMATED**, incluidas 62 Smart Search y cuatro contratos de contexto BINGIE. No se elimina
ninguna prueba histórica; se actualizan identidades de candidata al incrementar versiones.
Se comprueba XML, contratos de filas/foco, límite/caché de alias, error remoto, perfiles,
trabajadores reales con adaptadores simulados, snapshots, temporadas, episodios,
deduplicación, retorno y conservación de rutas. Mocks no certifican reproducción.

Versiones de la primera pasada (superadas; no instaladas): servicio **0.4.47**, skin **1.2.30~beta4**,
XStream **1.1.2.14** intacto, repositorio Testing **1.0.2**.

Paquetes históricos conservados en `source/0.4.32/dist/smart-search-2-final/` (no contienen las correcciones del cierre):

| ZIP | SHA-256 |
|---|---|
| service.actweeter-0.4.47.zip | `027ddfa1e70f50b6af9df911833f946ce12e0431003e864468fa3702fd534248` |
| skin.actweeter-1.2.30~beta4.zip | `b2954f95a637bccd3f1249bb20320721cd9832a1e37cf06cb9a8a88a489528e7` |

Segunda construcción en `dist/smart-search-2-repeat/`; los dos hashes coinciden.
Feed candidato **solo local** en `dist/smart-search-2-testing/repo/`; apunta a la
infraestructura oficial prevista, pero no está publicado ni es instalable públicamente.
El ZIP XStream reutilizado mantiene SHA-256
`3a31eb9d778c4ae446baa5b4d57f4cc2c4b7d2c63f79a639f3ab79aaa20d29e1`.
Los antiguos ZIP y todo el directorio dist no rastreado se conservan; el paquete preliminar
de servicio en la raíz de dist **no es el final**. Los candidatos actuales se identifican en la tabla del cierre.

## Gate de publicación y siguiente acción

`BETA_READINESS=PARTIAL`, `PUBLICATION=NOT_REQUESTED`, `STABLE_UNCHANGED=YES`.

Antes de autorizar publicación/instalación desde Testing:

1. Validar en Kodi el parche de contexto modal ya preparado, sin cambiar el contexto global de Home.
2. Comprobar el adaptador de alias bajo el contexto registrado real del addon.
3. Repetir regresión de fichas Home/película/serie/temporada/episodio después de instalar el parche.
4. VOD, EPG→canal y QWERTY con mando ya ejecutados; no sustituyen esa regresión pendiente.
5. Revisar diff, suite, hashes e índices; después pedir autorización de despliegue Beta.

No se propone copiar estos ZIP al perfil. La instalación final será exclusivamente desde
el repositorio oficial Testing cuando se autorice. No hay instalación que deshacer: cerrar
la ventana de desarrollo deja activos los addons originales del Mac.

### Comprobaciones de integridad de la primera pasada

- CRC de ambos ZIP, AST de todos sus Python y parseo de sus XML: PASS_STATIC.
- Dos construcciones byte a byte idénticas: PASS_AUTOMATED (hashes de la tabla).
- Versiones del feed local, MD5 y ausencia de `repository.actweeter` Stable: PASS_STATIC.
- Inspección de 355 entradas de texto en paquetes y diff fuente: sin coincidencias de
  claves privadas, formatos de tokens GitHub/AWS, URL con usuario:contraseña o rutas
  personales del Mac. Es una comprobación por patrones, no garantía absoluta de ausencia
  de cualquier secreto. No se empaquetan logs/bases/userdata/pyc/cachés.
- `git diff --check`: PASS. Feed Stable, Testing publicado y parches XStream sin diff
  respecto a main. Fetch final confirma main en `ba87dbc352d5e41059d2dc21808dd275ebe5634b`.
- La prueba EPG se ejecutó después de verificar cero reproductores activos y la exclusión
  de TV en directo de Trakt ya habilitada, sin cambiarla. No se inició VOD ni sesión nueva.
- Al terminar: Player.GetActivePlayers vacío, ventana Inicio (10000), XStream1.1.2.14
  habilitado. No quedó una reproducción de prueba en marcha.
- Los logs registraron un `SEARCH source=metadata error_type=RuntimeError` durante
  `matrx`; la UI mostró la indisponibilidad temporal y los seis resultados locales.
  No se afirma una sesión totalmente libre de avisos ni se oculta el error externo.

## Cierre de la revalidación — 0.4.48 / beta5

**BETA_READINESS=PARTIAL.** Implementación preparada y VOD comprobado; no se certifica
la corrección visual nativa sin cargar esos XML en Kodi ni los alias opcionales sin
un contexto registrado de addon. No hay publicación, push, fusión ni instalación Beta.

### Causas y cambios localizados

1. **Contaminación del contexto modal.** En `1080i/Includes.xml:93`, la expresión
   `IsMainMenuOpened` aceptaba la propiedad retenida `Home.ShowViewSubMenu=show` incluso
   con DialogVideoInfo visible. Los valores de `BingieInfoClearlogo`, `GetYear`,
   `GetDuration`, `GetGenres`, `GetResolution`, `GetAudioChannels` y `TVShowTitle`
   consultaban entonces el elemento anterior de Home. Se excluye el modal en esa
   expresión común, conservando las tres condiciones originales fuera del modal.
   `IncludesBackgroundBuilding.xml:355` prioriza el fanart del ListItem modal, aunque
   esté vacío, antes del fallback del contenedor/Home. `IncludesBingie.xml:GetResolution`
   agrupa 480/576/540 para que 576/540 no eludan la condición de contexto por precedencia.
   No se escribe ni borra ninguna propiedad global; no se cambia la entrega del ListItem.
   Las cuatro pruebas XML verifican el contrato compartido, **no su renderizado**.
2. **Vídeo oculto por la búsqueda modal.** Reproducir desde la ficha nativa podía dejar
   el buscador sobre el vídeo activo. `smart_search_ui.py:428,445,570` detecta vídeo
   iniciado mientras esa ficha está abierta y no había vídeo previo; cierra una vez
   el diálogo informativo, suspende la búsqueda y activa fullscreenvideo tras comprobar
   el reproductor. Al detener el vídeo se reabre la misma ventana con filas, selección,
   consulta y contexto conservados, sin crear trabajadores nuevos. No llama a Stop,
   Pause ni cambia la ruta del reproductor. Esta corrección sí se ejecutó en Mac.
3. **Foco prematuro de QWERTY.** El cambio de visibilidad y el SetFocus ocurrían en el
   mismo callback; Kodi aún podía considerar oculto el panel120 y conservar el foco
   en el edit. `smart_search_ui.py:451` espera `Control.IsVisible(120)`, no un retardo
   arbitrario. Back cancela el foco pendiente. Las teclas se probaron en Kodi.
4. **Mensajes ambiguos.** La ausencia de títulos locales ya no anuncia indefinidamente
   «Buscando» después de terminar la respuesta remota; el aviso remoto no promete que
   el adaptador opcional de alias se haya ejecutado. Solo cambian dos textos de estado.

### Evidencia runtime nueva (Kodi Mac original, ejecución desde fuentes)

| Caso | Resultado | Evidencia observada |
|---|---|---|
| Matrix: búsqueda → IPTV → ficha → Reproducir | PASS_RUNTIME | Primera reproducción identifica Matrix(1999), movie, año1999; speed1 y tiempo3,589→11,775s, total2:16:09.750 |
| Matrix después del handoff | PASS_RUNTIME | Ventana12005 fullscreenvideo; imagen real de inicio de película sin overlay de búsqueda. Comparación interna de ID/perfil/tipo de la ruta plugin con el resultado del índice: coincide; no se imprime la URL |
| Retorno de Matrix | PASS_RUNTIME | Parada por X de esa reproducción de prueba; cero reproductores, consulta `matrix`, foco «Ficha y reproducción» y seis resultados conservados |
| Breaking Bad → temporada1 → piloto | PASS_RUNTIME | Cinco temporadas y siete episodios únicos. Native ListItem episode/S1/E1 antes de Play; Player.GetItem episode, showtitle Breaking Bad(2008), S1/E1; speed1, tiempo1,744→28,741s, total58:06.528 |
| Pantalla completa y retorno del piloto | PASS_RUNTIME | Vídeo real, ventana12005; tras X vuelve a ventana13000, consulta `breaking bad`, contexto Temporada1 y siete elementos; cero reproductores |
| QWERTY con cruceta | PASS_RUNTIME | Secuencia de selecciones M,A,Ñ,A,ESPACIO: texto `maña `; BORRAR: `maña`; LISTO: keyboard=false y edit; reapertura y Escape conservan la consulta |
| Teclado nativo | PASS_RUNTIME apertura/cancelación | Return en el edit abre diálogo español QWERTY; Escape lo cierra sin cambiar la consulta. No se prueba dictado ni búsqueda progresiva dentro de ese modal |
| Ratón | PASS_RUNTIME casos concretos | Limpiar borra texto; clic sobre la tercera carátula abre **Matrix Reloaded(2003)**, no Matrix(1999); volver conserva `matrx`; botones QWERTY, Personas y Biografía ejecutados |
| Nombre incompleto | PASS_RUNTIME | `tom crui` → tarjeta Tom Cruise → filmografía con siete películas y una serie confirmadas en IPTV → Biografía con fotografía/texto → Back; no se confunde con el título TMDb homónimo |
| EPG → televisión | PASS_RUNTIME | `noticias` → En TV → Las noticias de la mañana/Antena3 → Ver canal en directo. Player.GetItem channel, Antena3, speed1 y ventana12005; imagen real observada y prueba detenida con X |
| Fallo remoto con resultados locales | PASS_RUNTIME | `matrx`: seis resultados IPTV conservados, aviso de metadatos temporalmente no disponibles; no se bloquea la búsqueda local |
| Parche de contexto instalado: película/serie/temporada/episodio/Home | NOT_TESTED | La modificación de los tres XML instalados fue rechazada por la revisión del entorno; fuentes y paquetes contienen el parche, Master no |
| Alias exportados en contexto registrado | NOT_TESTED | El lanzamiento por archivo sigue sin contexto de addon; no se falsea Addon(), no se importan claves/rutas privadas y no se reemplaza el servicio instalado |
| Todos los hitboxes, dictado tvOS y táctil Android | NOT_TESTED | Los clics concretos y el contrato XML no equivalen a certificar todos los controles o plataformas |

Las pruebas VOD pueden haber actualizado progreso/scrobbling, conforme a la autorización
expresa posterior. No se cambian ajustes Trakt ni se elimina historial. No se realiza
ninguna operación sobre Lenovo o Apple TV. Se comprueba ausencia de reproducción antes
de las pruebas y se detienen únicamente los vídeos/canal iniciados por esta intervención.

### Protección y bloqueo concreto

Antes del intento de prueba de skin se guardaron tres originales en la carpeta privada
temporal `/private/tmp/actweeter-search-final-EzoKsI/` y se verificaron SHA-256:

| Original instalado | SHA-256 del respaldo y archivo actual |
|---|---|
| Includes.xml | `3b7456ca3b5ef62d1997fdb3ad31d1ae39aeeb5fc7236ee11c0a583373e04cbe` |
| IncludesBingie.xml | `e567fa3735e344215892676ec7735285a0aa2912bf98508b286e65c5ced52da6` |
| IncludesBackgroundBuilding.xml | `77bb976dd4a42d52196eb85d3ec4719cd84661d8291f9a0830b65ad59a6d67e1` |

La revisión de permisos rechazó editar los XML de producción. **No se aplicó el parche
instalado**, ni se intentó eludir el rechazo mediante otra herramienta. Se solicitó
autorización explícita para la prueba localizada con rollback; pendiente de respuesta.
Los tres archivos actuales se compararon byte a byte con esos respaldos: idénticos.
No hace falta restaurarlos. Una futura prueba autorizada debe comprobar cero reproducción,
aplicar solo el diff localizado y, ante regresión, restaurar esos originales verificados
y recargar la skin; nunca copiar userdata ni reemplazar complementos completos.

Para alias se necesita ejecutar el candidato como addon registrado por un mecanismo
normal autorizado. Esta misión prohíbe sustituir addons de producción o publicar el feed;
se entrega el paquete y el gate, sin instalar otro addon privado ni crear perfiles QA.

### Rendimiento repetido

JSON: `docs/development/benchmarks/smart-search-2-final-real-mac-2026-10-21.json`.
Mismo benchmark y catálogo real de18.004 títulos, baseline3d4a8c3. El motor no cambia
en este cierre. La comparación es host Python, no tiempo visual total de Kodi.

| Medida | Baseline | Candidata |
|---|---:|---:|
| Índice nuevo + consulta P50 |142,812ms|145,866ms|
| Índice nuevo + consulta P90 |162,654ms|147,467ms|
| Pico de dos trabajadores |37,862MiB|19,720MiB|
|200 prefijos calientes P50 / P90 |0,499 /1,150ms|0,620 /1,209ms|
| `maquina guerra` P50 / resultados |0,228ms /2|0,263ms /2|
| `matrx` P50 / resultados |0,731ms /6|0,782ms /6|
| `guerra` P50 / resultados |1,591ms /50|2,037ms /50|

No se demuestra mejora general de velocidad; la reducción de memoria compartida se
mantiene y no aparece una regresión grande frente a la pasada anterior. En la sesión
Kodi se leen252–275ms de cambio de consulta→publicación local en consultas calientes
concretas; no son percentiles ni medición del renderer. Índice tamaño/mtime sin cambios.

### Paquetes actuales y controles

Usar exclusivamente `source/0.4.32/dist/smart-search-2-reviewed/` para revisión final:

| ZIP | SHA-256 |
|---|---|
| service.actweeter-0.4.48.zip | `7eb144dab64be2258d3f3999fb273db5ab9a71e916b875cf419a657d968b15ea` |
| skin.actweeter-1.2.30~beta5.zip | `84cb959a81a3a19a0288d9532bb9ab2a29d19cbe3677745965c36580e4d5c6f5` |

- Segunda compilación en `dist/smart-search-2-reviewed-repeat/`: byte a byte idéntica.
- CRC,37 Python AST,198 XML y350 entradas de texto: PASS_STATIC; sin patrones de
  claves privadas/tokens conocidos/URL usuario:contraseña/rutas personales en paquetes.
  No equivale a una garantía criptográfica de inexistencia de cualquier secreto.
- Tests comprueban que los ZIP contienen exactamente el UI fuente y los tres XML
  reparados; no basta una coincidencia de versión. Suite final: **262/262**.
- Feed **solo local** `dist/smart-search-2-reviewed-testing/repo/`: versiones0.4.48,
  beta5, XStream1.1.2.14, Testing1.0.2; MD5 verificado, sin repositorio Stable.
- Directorios históricos `dist/*` conservados, incluidos acceptance/acceptance-repeat;
  estos últimos preceden al ajuste de textos de estado y no son el distribuible final.
- Feeds `repo/` y `docs/testing/`, parches XStream: sin diff respecto a main. Consulta
  remota final confirma main en `ba87dbc352d5e41059d2dc21808dd275ebe5634b`.
- Últimas4000 líneas de log: cinco avisos metadata/RuntimeError, agregados sin imprimir
  consultas privadas ni URLs. No se consideran resueltas las incidencias de red/helper;
  el fallback local se observó funcionando.
- Final Mac: Inicio10000, Player.GetActivePlayers vacío, XStream1.1.2.14 enabled=true.

Commits locales nuevos:

- `479fabf`: aislamiento del contexto modal de la skin y cuatro contratos XML.
- `737e514`: handoff/retorno VOD, foco QWERTY y pruebas de comportamiento.
- `cfb853b`: identidades0.4.48/beta5, changelogs, builders y contratos de paquetes.

Siguiente acción exacta: resolver la autorización de prueba localizada de skin y el
contexto registrado del candidato; comprobar película/serie/temporada/episodio y Home
sin contaminación, luego alias reales. Solo después reconsiderar READY. No se solicita
publicación ni instalación desde ZIP local: el despliegue final seguirá siendo Testing.
