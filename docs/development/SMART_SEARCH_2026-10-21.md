# Smart Search — candidato, no publicado

Base: `ba87dbc352d5e41059d2dc21808dd275ebe5634b`, rama
`codex/smart-search-2026-10-21`. Desarrollo aislado en el worktree
`TwT-Actualizador-smart-search`; otros worktrees y sus dist no se modifican.

## Producto y alcance

Pantalla oscura de estética AcTweeteR, con carátulas, fondo de selección,
sinopsis y filas horizontales dentro de un contenedor vertical nativo:

1. Películas disponibles en el catálogo del perfil activo.
2. Series disponibles en ese catálogo.
3. Programas de EPG en emisión o durante los próximos siete días.
4. Personas: actores, directores y creadores.
5. Más títulos TMDb, con disponibilidad explícitamente sin confirmar.

Filtros Todo/Películas/Series/En TV/Personas/Explorar TMDb. Seleccionar una
persona abre su filmografía; Biografía abre el texto completo. Las fichas de
los títulos disponibles usan `Dialog.info` y los IDs/rutas existentes de
XStream. Buscar y seleccionar una carátula no inicia reproducción automática.
La guía muestra canal y horario; un canal en emisión solo se abre al elegir
explícitamente «Ver canal en directo» en su ficha.

No se guardan búsquedas, no se copian perfiles, no se autentica Trakt y no se
reescribe ninguna base de datos de Kodi o XStream. No hay nueva dependencia
de servicios con claves privadas. Los metadatos usan el TMDb BINGIE Helper ya
disponible y sus rutas verificadas, idioma y caché existentes. Es opcional:
su fallo no elimina resultados locales ni los de EPG.

## Arquitectura

`Custom_1109_BingieSearch.xml` conserva el destino de los accesos existentes
y llama `RunScript(service.actweeter,smart_search)`. No requiere reconstruir
Skin Shortcuts ni reemplazar menús del usuario.

- `smart_search_engine.py`: índice en memoria de identidades/títulos del
  índice SQLite existente `provider_search_N.sqlite`, apertura solo lectura,
  acentos/casefold/artículos/orden de palabras/prefijos, fallback acotado de
  errores tipográficos. Detalles consultados en bloque solo para candidatos.
- `smart_search_sources.py`: contexto del perfil activo, rutas TMDb verificadas
  y guía de las bases `TV*.db` y `Epg*.db` de Kodi 21. La ausencia o diferencia
  de esquema es un estado no disponible, no un resultado vacío exitoso.
  Se excluyen canales ocultos, bloqueados, de radio o con EPG deshabilitada.
- `smart_search_ui.py` y `AcTweeteRSearch.xml`: controles nativos, resultados
  locales tras 200 ms y metadatos tras 650 ms de estabilidad del texto.
  Dos workers de fuentes con una única consulta pendiente reemplazable;
  generaciones invalidan resultados obsoletos. La UI conserva selección al
  enriquecer resultados y no reconstruye filas idénticas.

Límites explícitos de esta versión: 30 resultados locales por tipo, 30 programas,
40 tarjetas por fila y hasta 100 entradas por ruta de metadatos. No son los
widgets de Home ni cambian su límite 20 + EXPANDIR. La filmografía es una
selección limitada, no una promesa de listar toda la obra de cualquier persona.
Una petición del helper ya iniciada no puede cancelarse mediante la API de
Kodi: su resultado se descarta si el usuario ha cambiado la búsqueda.

La coincidencia flexible de consultas **no** se utiliza como unión de identidad
de reproducción. El enriquecimiento exige tipo, palabras equivalentes del
título localizado/original y año compatible. No se anuncia disponibilidad de
una obra de TMDb sin un enlace conservador a un ID real del proveedor.

## Teclado y voz: capacidades verificadas

- Teclado físico y QWERTY propio: el campo se consulta mientras se escribe y
  los resultados permanecen visibles. QWERTY es un panel nativo, no teclas
  simuladas. Incluye Ñ, espacio, borrar y listo.
- «Teclado / voz»: `Dialog.input`, respetando la selección de teclado que Kodi
  tenga configurada. No se cambia ninguna preferencia global.
- tvOS puede elegir su teclado nativo según la opción existente de Kodi. No
  se promete dictado en todos los mandos/idiomas ni se ha probado Apple TV.
- Python no expone el callback de texto parcial del teclado nativo. En ese
  modo los resultados se actualizan al confirmar, no mientras se dicta.

Referencias oficiales Kodi 21.3:
[GUIEditControl::OnClick](https://github.com/xbmc/xbmc/blob/21.3-Omega/xbmc/guilib/GUIEditControl.cpp#L305),
[GUIKeyboardFactory](https://github.com/xbmc/xbmc/blob/21.3-Omega/xbmc/guilib/GUIKeyboardFactory.cpp#L83),
[Python Keyboard](https://github.com/xbmc/xbmc/blob/21.3-Omega/xbmc/interfaces/legacy/Keyboard.cpp),
[DarwinEmbedKeyboardView](https://github.com/xbmc/xbmc/blob/21.3-Omega/xbmc/platform/darwin/ios-common/DarwinEmbedKeyboardView.mm).

## Evidencia Mac, sesión 2026-10-21

Se ejecutó la ventana desde las fuentes con Kodi Mac abierto, sin instalar ni
sobrescribir complementos, sin modificar configuraciones y sin reiniciar.
Antes de ejecutarla no había reproductores activos. No se utilizó Kodi QA,
Lenovo ni Apple TV. XStream aparece instalado pero **deshabilitado**: se respeta
ese estado y no se afirma validación end-to-end del proveedor.

| Comprobación | Estado | Evidencia/alcance |
|---|---|---|
| Escritura física progresiva | PASS_RUNTIME | «maquina guerra» muestra carátulas TMDb antes de abrir otro diálogo |
| Personas y filmografía | PASS_RUNTIME | «Tom Cruise», fila de personas, selección de actor y carga de obras |
| Biografía y regreso | PASS_RUNTIME | Foto/texto completo, Volver y retorno a la búsqueda |
| Cruceta y ratón | PASS_RUNTIME | Campo → filtros → persona; selección y apertura de Biografía |
| QWERTY | PASS_RUNTIME | Apertura de tres filas, Right/OK añade `w` al campo; resultados se actualizan |
| Teclado nativo | PASS_RUNTIME | Dialog.input abre Spanish QWERTY de Kodi Mac; cancelación sin cambiar ajustes |
| EPG | PASS_RUNTIME | «noticias» produce fila En TV, 30 programas con canal/horario |
| Reproducción de canal | NOT_TESTED | No se inicia contenido durante estas pruebas |
| Películas/series locales → ficha | NOT_TESTED | XStream deshabilitado; pruebas del motor sí usan índice real y fixtures |
| Voz tvOS / Android | NOT_TESTED | No se accede a esos dispositivos |
| Actualización desde Testing | NOT_TESTED | Candidato aún no publicado |

Medición **real del backend Mac**, no benchmark de dispositivo Android/tvOS ni
latencia completa de interfaz: índice existente con 18.004 títulos, primera
carga 251,87 ms. Consultas calientes: «maquina guerra» 2,23 ms (2 resultados),
«máquina de guerra» 1,76 ms (2), «matrix» 1,98 ms (7), «casa papel» 1,03 ms (3).
EPG «noticias»: 230,8 ms (30 resultados). El fallback de typo se endureció
después de la primera medición; no se atribuyen las cifras anteriores a una
medición nueva de ese fallback. La red TMDb tiene latencia independiente.

## Pruebas y distribución

Suite final: **229 tests PASS** (base: 196, nuevos: 33). Se añaden contratos de normalización, coincidencias,
identidades, perfiles, SQL solo lectura, cambios de índice, cancelación,
coalescing, errores de red, confianza de rutas, caché, EPG y estructura nativa;
también selección conservada al llegar metadatos, regreso de fichas y ausencia
de reproducción al seleccionar un resultado. Los mocks no validan reproducción.

Versiones propuestas: servicio `0.4.46`, skin `1.2.30~beta3` (requiere servicio
`0.4.46`). XStream y repositorio no cambian. Stable y el feed Testing público
permanecen sin cambios. Los ZIP se construyen únicamente con los scripts
versionados. Dos reconstrucciones idénticas byte a byte, CRC correcto,
AST de los 37 Python del servicio y XML de los 3 XML del servicio y 195 de la
skin comprobados. No se distribuyen bases de datos, logs o capturas de perfil.

SHA-256:

- `service.actweeter-0.4.46.zip`: `48f376a043f7060d9e287544be977b711b9531bff60c597e2047d2420dbaa791`
- `skin.actweeter-1.2.30~beta3.zip`: `f67bb8dd13e4be0b3465a7c8ff2e5d618f4b0cd5e5b60097f9bf3b4f17ce5102`
- XStream reutilizado `1.1.2.14`: `3a31eb9d778c4ae446baa5b4d57f4cc2c4b7d2c63f79a639f3ab79aaa20d29e1`

Feed candidato **local, no servido ni instalado**:
`source/0.4.32/dist/smart-search-testing/repo/addons.xml`.
Índice SHA-256 `4ff28d37c75dd425b0c0cae6906c9591aa7fb6c634a28bf958d24001684499a3`;
MD5 calculado por el constructor y verificado en las pruebas. Los artefactos
dist están excluidos de Git; se reconstruyen desde este código. Revisión de
patrones de secretos en los nuevos módulos y pruebas: sin coincidencias; esto
no pretende ser una auditoría completa de dependencias de terceros.

Instalación final: revisión del candidato → publicación de ambos paquetes y
sus metadatos en **Testing** → actualización normal desde Kodi. No instalar
los ZIP privados para saltar este proceso. Para rollback se conservan los
artefactos publicados anteriores; la ventana anterior requiere el par previo
de skin/servicio. Esta implementación no migra datos persistentes que requieran
deshacer cambios de esquema.

Gates pendientes antes de publicación: prueba con XStream habilitado,
película/serie correctas al abrir sus fichas, enriquecimiento canonical real,
actualización del par desde Testing y prueba de voz en dispositivo compatible.
