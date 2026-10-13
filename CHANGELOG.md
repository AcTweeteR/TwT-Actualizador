# Changelog AcTweeteR

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
