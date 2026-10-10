# Changelog AcTweeteR

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
