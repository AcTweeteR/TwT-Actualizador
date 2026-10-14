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
