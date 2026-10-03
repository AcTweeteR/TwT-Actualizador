# Changelog AcTweeteR

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
