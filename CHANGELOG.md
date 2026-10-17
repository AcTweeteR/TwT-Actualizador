# Changelog AcTweeteR

## AcTweeteR 0.4.30 — migración de interfaz al actualizar

- El servicio 0.4.30 vuelve a comprobar la migración de Skin Shortcuts aunque
  el asistente inicial ya esté reclamado durante el proceso Kodi actual.
- Conserva backup y consentimiento antes de sustituir DATA o preferencias
  personalizadas; la migración solo se verifica tras inspeccionar la salida
  generada por Kodi.
- No cambia la skin, los controles radiobutton, XStream ni datos personales.
  Tacto y reproducción de tráilers siguen pendientes de validación runtime.

## AcTweeteR 0.4.29 — actualización oficial de feed

- Skin 1.2.28 y servicio 0.4.29 corrigen la selección del layout expandible:
  deja de evaluarse una URL `plugin://` dinámica como expresión booleana y
  usa metadatos explícitos de Skin Shortcuts.
- Migración v9 marca únicamente las rutas XStream de lista para las que el
  paquete distribuido implementa expansión; conserva expresiones de refresco,
  filtra parámetros sensibles y deja intactos los DATA personalizados sin
  consentimiento. La migración crea backup antes de cambiar datos propios.
- Se reconstruyeron ZIP de skin/servicio y el índice; XStream Pro 1.1.2.7 y el
  repositorio Kodi 1.0.3 se reutilizan sin cambios.
- 9 pruebas específicas PASS, AST Python y análisis XML estático PASS. No son
  validación runtime. Instalación/actualización, EXPANDIR, widgets, tráilers,
  distintivos, colecciones y navegación táctil en Lenovo: NOT_TESTED después
  de esta candidata.
- Publicado en el feed oficial de Kodi desde el commit `76428bf`; los paquetes
  0.4.28 siguen disponibles para rollback. La instalación/actualización real
  en Lenovo aún debe comprobarse mediante Kodi.

## AcTweeteR 0.4.28

- Skin 1.2.27 y servicio 0.4.28; repository.actweeter 1.0.3 sin cambios.
- Widgets elegibles limitados a 20 contenidos, con `EXPANDIR` rojo adicional
  únicamente en rutas cuya expansión está verificada.
- Favoritos/Pendientes en Mis colecciones para Películas y Series; distintivos
  de novedades con fondo rojo y texto blanco.
- Integra en las fuentes distribuidas los cambios estructurales de hit testing
  y movimiento de touch10, sin afirmar que el tacto esté validado en runtime.
- XStream Pro 1.1.2.7 conserva licencia y atribuciones CC BY-NC 4.0; solo uso
  no comercial.
- 605 pruebas automatizadas PASS. Instalación limpia, actualización y
  navegación runtime en Lenovo/tvOS no probadas.
- La versión 0.4.27 permanece disponible para rollback.

## AcTweeteR 0.4.27 — hotfix de controles de ficha

- Revierte el prototipo de controles `button` de la skin 1.2.23. En ambos
  diseños de ficha se restauran los `radiobutton` nativos de Play, Resume y
  Trailer, incluidos sus IDs, pilas de acciones, condiciones de visibilidad,
  texturas y enlaces de navegación.
- El cambio experimental correlacionado envolvía los botones push dentro de
  grupos y alteraba el hit target/semántica del control. La regresión de
  botones fue confirmada por el usuario en Apple TV y Android tras instalar
  0.4.26; la reversión no demuestra todavía la recuperación runtime.
- No se modifica `input.enablemouse`, ni el scroll, el foco del ratón, XStream,
  Trakt, PVR o los datos del usuario. El problema táctil preexistente de
  Android queda separado y sin resolver.
- 590 pruebas automatizadas PASS. Validación runtime de botones pendiente del
  usuario; no se presenta como PASS.
- Skin 1.2.24; servicio 0.4.26, XStream Pro 1.1.2.5 y repository 1.0.3 sin
  cambios respecto a los artefactos publicados en 0.4.26.

## AcTweeteR 0.4.26 — prueba de interacción táctil

- Skin 1.2.23 sustituye experimentalmente los controles de acción Play,
  Resume y Trailer de las fichas por botones push de Kodi, conservando IDs,
  acciones, condiciones y navegación. Es una hipótesis de interacción; no se
  considera una corrección táctil confirmada.
- Servicio 0.4.26 incorpora trazas de diagnóstico optativas, desactivadas por
  defecto, sin registrar títulos, rutas, URLs, credenciales ni tokens.
- Scroll y comportamiento del ratón no cambian. La prueba runtime táctil queda
  pendiente del propietario; mando, teclado y reproducción requieren también
  validación en Kodi.
- 590 pruebas automatizadas PASS (586 en la suite normal y las 4 pruebas de
  sockets locales reintentadas por separado con permisos de loopback).
- XStream Pro 1.1.2.5 y repository.actweeter 1.0.3 no cambian.
- La incidencia de cierre queda `CLOSED_NOT_REPRODUCIBLE`: no se ha confirmado
  una corrección técnica; reabrir si vuelve a reproducirse.

## AcTweeteR 0.4.25 — estable

- Skin 1.2.22: conserva las correcciones de foco/BingieInfo, Spotlight abriendo
  la ficha sin autoplay, objetivos táctiles y sinopsis ampliadas. La validación
  táctil runtime Android sigue pendiente.
- Servicio 0.4.25: reduce comprobaciones ociosas de XStream, evita parsear
  repetidamente Skin Shortcuts mientras genera los DATA y mantiene las métricas
  opcionales desactivadas por defecto.
- XStream Pro 1.1.2.5: reconcilia el índice local leyendo las filas previas una
  vez por tipo dentro de la transacción, eliminando el SELECT por elemento sin
  cambiar esquema ni semántica de IDs. Se conservan licencia y avisos CC BY-NC.
- 581 pruebas automatizadas PASS; instalación/actualización runtime, Android,
  tráilers Android y rendimiento en dispositivos no se declaran validados.
- La incidencia de cierre de Kodi sigue abierta. El propietario aceptó el
  riesgo únicamente para esta versión 0.4.25.

## AcTweeteR 0.4.24 — estable

- Skin 1.2.20: incorpora scrollbar vertical nativo de Kodi en Home, conectado
  al contenedor de widgets, para ofrecer una zona táctil de desplazamiento más
  predecible.
- Aumenta los objetivos táctiles de las acciones de las fichas y añade acceso
  a la sinopsis completa mediante el visor paginado/desplazable nativo.
- Conserva los gestos de carruseles y el foco con mando/teclado. La validación
  táctil runtime en Android permanece PENDING; no se afirma como corregida.
- Servicio 0.4.23, XStream Pro 1.1.2.4 y repository 1.0.3 no cambian; no se
  alteran credenciales, progreso ni configuraciones.
- 563 pruebas automatizadas PASS. La incidencia crítica de cierre de Kodi
  continúa abierta; el propietario aceptó expresamente el riesgo únicamente
  para la publicación 0.4.24.

## AcTweeteR 0.4.23 — estable

- Servicio 0.4.23 requiere XStream Pro 1.1.2.4 y mantiene Trakt opcional.
- XStream Pro propaga metadatos de películas y episodios al ListItem final,
  incluidos los identificadores soportados y `script.trakt.ids`; no añade un
  cliente OAuth ni un scrobbler paralelo.
- Skin 1.2.18 y repositorio 1.0.3 no cambian. No hay migración de datos ni
  alteraciones de credenciales, favoritos, historial o progreso.
- 553 pruebas automatizadas PASS; la reproducción real y el scrobbling de
  script.trakt permanecen NOT_TESTED.
- La incidencia crítica de cierre de Kodi sigue abierta. El propietario acepta
  expresamente este riesgo conocido únicamente para la publicación 0.4.23.

## AcTweeteR 0.4.22 — estable

- Servicio 0.4.22 y XStream Pro 1.1.2.3 corrigen el `IndentationError` causado
  por inserciones de parche basadas en offsets de línea.
- El empaquetador ancla las modificaciones a contexto fuente único y valida
  sintácticamente los Python antes y después de crear el ZIP.
- Skin 1.2.18 y repositorio 1.0.3 no cambian. Sin migraciones de credenciales,
  progreso o perfiles.
- 545 tests automatizados PASS; corrección todavía NOT_TESTED en Kodi runtime.
- La incidencia crítica de cierre de Kodi/plugin:// sigue abierta. El
  propietario aceptó expresamente el riesgo para esta publicación 0.4.22.

## AcTweeteR 0.4.21 — estable

- Skin 1.2.18 / servicio 0.4.21 / XStream Pro 1.1.2.2.
- Trakt opcional; sin tercera integración ni sincronización duplicada.
- Filas nativas de recomendaciones en Películas y Series con filtrado estricto
  por coincidencia TMDb exacta disponible en XStream.
- Migración de widgets v7, versionada, idempotente, con backup y cuidado de
  personalizaciones.
- 542 pruebas automatizadas PASS. Recomendaciones/OAuth, IPTV y reproducción
  runtime en esta versión siguen NOT_TESTED.
- La incidencia crítica de cierre Kodi/plugin:// permanece abierta; el
  propietario acepta explícitamente el riesgo únicamente para 0.4.21.

# Changelog AcTweeteR

## AcTweeteR 0.4.18 — estable

- Skin 1.2.16 / servicio 0.4.18: Continuar viendo incorpora invalidación de
  caché al terminar reproducción y un token de refresco en los DATA portables.
- Migración de interfaz v4 para perfiles existentes: respalda y actualiza solo
  los DATA gestionados de Continuar viendo; conserva datos y preferencias.
- 523 pruebas automatizadas PASS. La fila corregida todavía requiere
  verificación visual en Apple TV; clean install/update runtime de esta versión
  quedan sin probar en las plataformas objetivo.
- La incidencia crítica de cierre de Kodi en trabajos `plugin://` sigue
  abierta. El propietario aceptó explícitamente ese riesgo para 0.4.18 solo.

## AcTweeteR 0.4.17 — estable

- Skin 1.2.15 y servicio 0.4.17: configurador inicial reanudable con
  autorización oficial de Trakt por dispositivo o aplazamiento.
- XStream Pro 1.1.2.1 incorpora la revisión mantenida de refresco y callbacks;
  Kodi puede actualizarla como versión nueva sin reemplazar 1.1.2.
- Los errores al iniciar la actualización Xtream conservan las credenciales y
  permiten reintentar. Trakt solo recibe valores predeterminados seguros si se
  instala por primera vez; se conservan los ajustes existentes.
- 510 pruebas automatizadas PASS. La instalación limpia y la ejecución de esta
  versión en dispositivos todavía no están validadas.
- Sigue abierta la incidencia de cierre de Kodi durante trabajos de directorio
  `plugin://`; su causa aún no está identificada.

## skin.actweeter 1.2.11 — parada segura también en widgets

- Completa la protección de SlyGuy en las filas de widgets, además de Home y
  Spotlight. Las paradas de previews corresponden al coordinador de ownership.
- Conserva el diseño del proveedor confirmado visualmente en Apple TV y los
  valores de preview para nuevas instalaciones. Requiere servicio 0.4.10.
- 437 tests PASS; sin cambios en XStream Pro ni repository.actweeter.

## service.actweeter 0.4.10 — estado Unicode independiente de plataforma

- Lee explícitamente en UTF-8 el estado que contiene preferencias españolas.
- 437 tests PASS. En Apple TV el bridge 0.4.9 ya produjo preview automático,
  AVStarted y avance de 17 segundos en Home; se comprobó cleanup al volver al menú.
- Mantiene backups, consentimiento e integración local sin publicar SlyGuy ZIP.
- Tras reiniciar Kodi en Apple TV, el propietario confirmó sinopsis españolas y
  preview automático operativos.

## service.actweeter 0.4.9 — integración reproducible de previews

- Resuelve el hueco de despliegue: el SlyGuy oficial no carga el bridge de
  AcTweeteR. El configurador puede conectar localmente el bridge ya existente.
- Requiere consentimiento, SlyGuy 0.2.1 y hashes oficiales exactos. Copia
  verificada, idempotencia, restart nativo y rollback sin cambiar preferencias.
- No distribuye paquetes ni fuentes de SlyGuy; se obtiene del repositorio oficial.
- Refresca una vez la caché propia de metadatos si el idioma ya era español,
  evitando mantener sinopsis inglesas generadas antes de la preparación.
- 436 tests PASS; la instalación del hook no se confunde con reproducción validada.

## skin.actweeter 1.2.10 / service.actweeter 0.4.8

- El mismo tráiler SlyGuy terminaba al salir de Home y avanzaba desde otra
  ventana: se limita la orden Stop heredada al backend antiguo sin SlyGuy.
- La parada de previews SlyGuy continúa gestionada mediante ownership.
- Configura metadatos XStream españoles si conserva sus preferencias inglesas
  de fábrica. Respalda preferencias y únicamente caché de metadatos Premium;
  no altera progreso, favoritos ni credenciales.
- Conserva la interfaz confirmada visualmente por el propietario en Apple TV,
  las filas por año y su persistencia. 433 pruebas automatizadas PASS.
- Repositorio 1.0.3 y XStream Pro 1.1.2 permanecen sin cambios; las versiones
  anteriores se conservan. La validación de estos dos últimos ajustes se realiza
  tras actualizar el Apple TV afectado.

## service.actweeter 0.4.7 — retirada de captura de QA

- Retira la acción de captura introducida durante esta validación; su solicitud
  coincidió con la salida de Kodi al menú tvOS. No altera las funciones del producto.
- Conserva la corrección VFS, backups e interfaz del proveedor. 431 tests PASS.
- Apple TV: Inicio carga filas del proveedor; Películas carga 24 títulos de
  2026 y 24 de 2025. DATA y Spotlight persisten tras la reapertura de Kodi.
- Continuar viendo/Favoritos vacíos no se rellenan con datos inventados.

## skin.actweeter 1.2.9 — diseño del proveedor y años dinámicos

- Corrige el grupo de Inicio usado por Skin Shortcuts; seis filas del proveedor.
- Películas y Series incluyen nueve filas, con estrenos del año actual y anterior.
- Elimina etiquetas heredadas de IMDb/Trakt en las filas predeterminadas IPTV.
- Spotlight obtiene varios elementos reales, no una única portada fija.
- Entrega un menú inicial sin datos de perfil de desarrollo. El servicio 0.4.6
  prepara los DATA mediante Kodi VFS y solicita la generación nativa.
- Antes del despliegue se verificó en el Apple TV el backup de ajustes/includes.
  Las pruebas automatizadas pasan; la comprobación visual se realiza tras actualizar.

## service.actweeter 0.4.6 — compatibilidad del XML de perfil en tvOS

- Lee y escribe DATA y ajustes mediante Kodi VFS: en tvOS un XML puede existir
  en NSUserDefaults sin un archivo POSIX. Defecto observado en el Apple TV.
- Verifica backups por lectura posterior y conserva datos personalizados.
- Diagnóstico de includes nativos con referencias por perfil; preparación
  disponible sin reiniciar Kodi. 430 pruebas automatizadas PASS.
- La nueva interfaz permanece pendiente de comprobación visual hasta desplegar
  la skin 1.2.9; no se confunde XML generado con PASS_RUNTIME.

## service.actweeter 0.4.5 — backup por la entrada nativa del plugin

- Hace accesible el backup local desde el plugin del servicio: Kodi prioriza
  esta entrada cuando el complemento declara varios puntos de extensión.
- Conserva 0.4.4 y todos los paquetes previos sin sobrescribirlos.
- 428 pruebas automatizadas PASS; comprobación visual de skin 1.2.9 pendiente.

## service.actweeter 0.4.4 — preparación segura de la interfaz

- Copia verificada de DATA, ajustes de skin e includes en el dispositivo antes
  de aplicar el diseño del proveedor. No copia credenciales ni perfiles del Mac.
- Regeneración nativa de Skin Shortcuts con protección de personalizaciones,
  reintento y diagnóstico que distingue XML generado de interfaz comprobada.
- 427 pruebas automatizadas PASS. La validación visual de la nueva skin 1.2.9
  en el Apple TV afectado está pendiente; el servicio preserva la skin 1.2.8.
- No cambia el repositorio 1.0.3, XStream Pro ni los paquetes históricos.

## service.actweeter 0.4.3 — versión estable

- Asistente reanudable para preparar y comprobar los componentes declarados;
  configuración de proveedor preservada al reintentar.
- Validación del perfil activo para PVR, evitando aceptar canales de otra
  instancia como configuración de AcTweeteR.
- Ajustes booleanos de XStream escritos mediante su API tipada y verificados
  con rollback de los valores previos si falla la actualización.
- Manejo defensivo de `HTTPError` cuando no existe cuerpo de respuesta.
- 416 pruebas automatizadas PASS. Se conservan resultados runtime comunicados
  anteriormente para asistente, IPTV/VOD, episodios, PVR/EPG, persistencia y
  trailers manuales; la instalación limpia aislada sigue NOT_TESTED y no se
  afirma validación runtime nueva en tvOS/Android TV.

## service.actweeter 0.4.1 — verificación de sincronización PVR

- Espera el estado real de inicialización PVR después de solicitar la sincronización nativa de XStream, con timeout acotado y errores de consulta diferenciados.
- Solicita consentimiento antes de habilitar y comprobar la preferencia de sincronización PVR de XStream; no reescribe ajustes de IPTV Simple ni repite la solicitud de sincronización.
- No afirma que EPG esté disponible sin observar emisiones reales.
- Suite automatizada: 377 PASS. Validación runtime en Apple TV: pendiente; no se declara funcionamiento en dispositivo.

## Catálogo 2026-10-12 — sincronización de versiones actuales

- Publica `service.actweeter 0.3.8` y `repository.actweeter 1.0.3` junto a la skin 1.2.8 ya disponible.
- El índice incluye el paquete adaptado `plugin.video.xstream-pro 1.1.2` bajo CC BY-NC 4.0, con licencia, atribución y cambios indicados; uso no comercial únicamente.
- Repository 1.0.3 incorpora el feed oficial SlyGuy; helpers BINGIE siguen servidos por Matke y dependencias Kodi por el repositorio oficial.
- Suite privada: 363 tests PASS + 13 subtests PASS. Instalación limpia y validación runtime Apple TV/Android TV permanecen NOT_TESTED.

# Changelog AcTweeteR

## service.actweeter 0.2.7 — elegibilidad XStream en tvOS

- XStream Pro solo se ofrece en tvOS cuando IPTV Simple está instalado,
  habilitado y cumple la versión mínima requerida.
- La habilitación requiere consentimiento explícito; el asistente informa y
  permite continuar si la dependencia falta o no es compatible.
- No se incluye PVR IPTV Simple ni se cambia el flujo de configuración.
- Validación automatizada: 325 tests PASS. No se ha realizado QA runtime en tvOS.

## skin.actweeter 1.2.8 — reproducción directa desde Inicio

- Conserva la acción nativa de Kodi para elementos reproducibles de XStream en
  widgets y tarjetas de Inicio, evaluando `ListItem.Property(IsPlayable)`.
- Mantiene la acción Información para elementos no reproducibles.
- Suite automatizada: 321 PASS. La prueba runtime de 1.2.8 y la auditoría
  funcional integral siguen pendientes; no se afirma validación en dispositivos.

## skin.actweeter 1.2.2 + service.actweeter 0.2.2 — corrección de primer arranque

- Evita que Home pierda el foco cuando una instalación limpia no tiene filas de
  widgets y presenta una ruta visible hacia configuración.
- Reofrece un asistente aceptado pero interrumpido y migra estado incompleto
  ambiguo de 0.2.1.
- Establece propiedad de reproducción de la intro antes de abrir su diálogo.
- Automatización/estructura PASS; QA runtime en Apple TV/tvOS y Android TV/Google
  TV pendiente. Instalación limpia no probada.

## skin.actweeter 1.1.3 + service.actweeter 0.1.0 — Search AcTweeteR

- Rediseña Buscar con un campo visible y enfocado como entrada canónica.
- El teclado físico escribe y actualiza resultados provider-only en vivo.
- En mando, el campo abre el teclado modal nativo de Kodi y busca al confirmar.
- Retira el pseudo-teclado de pantalla y corrige su navegación/foco.
- Añade el servicio Kodi para mantenimiento en segundo plano del índice y
  configuración estructural. Los perfiles Consumer siguen experimentales y no
  se consideran productizados.
- Kodi 21.3 es la baseline; la actualización física de Apple TV a 1.1.3 queda
  pendiente. XStream, credenciales y su patch privado no se incluyen.

## skin.actweeter 1.1.2 — Kodi Omega dependency compatibility

- Mantiene todas las dependencias obligatorias y la UI de 1.1.1.
- Ajusta únicamente los mínimos de AutoCompletion a 2.1.2 y Studio Icons a
  0.0.24, versiones disponibles en Kodi official Omega. Esto evita depender de
  “Any repository” para resolver IDs duplicados.
- No cambia código, recursos, funcionalidad, repository.actweeter ni bootstrap.
- Apple TV requiere retest físico; no se declara instalación tvOS validada.

## repository.actweeter 1.0.1 — GitHub-only bootstrap

- Añade el punto de entrada HTTP navegable de GitHub Pages para Kodi.
- Agrega de forma nativa la metadata upstream Bingie requerida; los paquetes
  continúan descargándose desde el repositorio upstream y no se redistribuyen.
- No modifica `skin.actweeter 1.1.1` ni completa funciones V1.1.

## 1.1.1 — primera distribución pública (dev)

- Empaquetado instalable mediante repositorio nativo Kodi.
- Conserva funcionalmente la UI validada del skin 1.1.0 en Kodi 21.3.
- Sustituye en la distribución las fuentes Netflix Sans e Impact sin derecho de
  redistribución acreditado por Inter ya incluido y su licencia SIL OFL 1.1.
- Incluye avisos de procedencia y dependencias; no contiene provisioning ni datos
  personales.
- El changelog post-update de una sola presentación y su consulta manual quedan
  documentados como diseño futuro; no se implementa servicio ni popup en 1.1.1.
- V1.1 sigue incompleta; consultar README.

## 1.1.0 — baseline local (no distribuida por este canal)

- Estado de skin observado en Kodi 21.3: Home/Spotlight/fila de contenido y
  apertura de ficha de póster.
- Esta versión fue la baseline local antes de saneamiento de fuentes.
