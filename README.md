# TwT-Actualizador — distribución Kodi de AcTweeteR

Repositorio público de artefactos Kodi. El desarrollo canónico continúa en
[`AcTweeteR/TweeteR-Kodi`](https://github.com/AcTweeteR/TweeteR-Kodi) (privado).
El provisioning personal vive únicamente en iCloud Drive/`actweeter kodi`.

## Distribución actual: AcTweeteR 1.1.3 (canal dev)

- `skin.actweeter 1.1.3`
- `service.actweeter 0.1.0`
- `repository.actweeter 1.0.1` (sin cambios)

La skin incluye el Search AcTweeteR: el teclado físico escribe directamente y
actualiza resultados en vivo; seleccionar el campo desde un mando abre el
teclado virtual nativo de Kodi y busca al confirmar. El servicio programa
actualizaciones del índice local cuando existe el runtime XStream compatible.

Kodi 21.3 Omega es la baseline de API validada. El propietario confirmó en
Apple TV la instalación anterior de la skin 1.1.2 y sus dependencias; la
actualización automática a 1.1.3 todavía requiere su prueba física. Kodi 22/23,
tvOS runtime y Android no se declaran validados.

Esta distribución no incluye perfiles personales, userdata, provisioning,
XStream, PVR/EPG, credenciales, historial, índices, caches ni datos personales.
No productiza perfiles Consumer. El patch privado de XStream no se redistribuye:
el upstream identificado declara CC BY-NC 4.0. Por ello, Search provider-only
requiere que la instalación disponga de un runtime XStream compatible; instalar
esta skin no instala ni configura el proveedor.

## Instalación y actualización Kodi

La fuente estable de bootstrap es
**https://actweeter.github.io/TwT-Actualizador/bootstrap/**. La primera
instalación utiliza `repository.actweeter-1.0.2.zip` desde esa fuente y luego
AcTweeteR Repository. Para instalar la beta, deja que Kodi consulte su
repositorio normal de add-ons y selecciona las versiones beta disponibles en el
catálogo.

El índice AcTweeteR contiene los ZIP de skin y service. Un segundo directorio
agrega metadata upstream Bingie; Kodi descarga esos helpers directamente de su
origen. Dependencias oficiales Kodi Omega se resuelven desde el repositorio
incluido en Kodi. El cierre versionado está en
[`docs/DEPENDENCIES.md`](docs/DEPENDENCIES.md).

## Versiones, cambios y verificaciones

- Manifest de esta distribución: [`manifests/1.1.3.json`](manifests/1.1.3.json).
- SHA-256: [`checksums/SHA256SUMS`](checksums/SHA256SUMS).
- Cambios: [`CHANGELOG.md`](CHANGELOG.md), más changelogs por add-on en `repo/`.
- `service.actweeter` incluye su licencia GPL-2.0-or-later. No incluye el
  patch XStream ni provisioning.
- La publicación es manual y requiere autorización expresa; no hay publicación
  automática por commit. No se ha modificado Apple TV.

## Rollback

Se conservan los ZIP públicos 1.1.1 y 1.1.2 y el repositorio 1.0.1. Kodi no
suele ofrecer un downgrade automático desde 1.1.3 a una versión inferior. Si
aparece una regresión, la recuperación preferida es publicar una versión
correctiva con número superior basada en el artefacto previo; conservar todos
los ZIP y checksums existentes. No eliminar userdata para recuperar una versión.

El histórico [`tools/build_repository.py`](tools/build_repository.py) construía
la distribución 1.1.2 y no debe usarse para regenerar la 1.1.3. La metadata de
esta release se ensambló con el builder privado versionado en TweeteR-Kodi,
usando los ZIP reproducibles generados desde ese source.
