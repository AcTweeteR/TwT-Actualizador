# TwT-Actualizador — distribución Kodi de AcTweeteR

Repositorio público de artefactos instalables. El desarrollo canónico continúa en
[`AcTweeteR/TweeteR-Kodi`](https://github.com/AcTweeteR/TweeteR-Kodi) (privado).
El provisioning personal vive únicamente en iCloud Drive/`actweeter kodi`.

## Primera distribución: skin 1.1.1 (canal dev)

La versión pública `skin.actweeter 1.1.1` conserva funcionalmente el runtime
validado `1.1.0` de Kodi 21.3. El único ajuste del paquete es sustituir fuentes
Netflix Sans/Impact sin permiso de redistribución acreditado por los archivos
Inter ya incluidos, con su licencia OFL. No representa que V1.1 esté completa.

Probado: Kodi 21.3.0 en macOS. Apple TV/tvOS y Kodi 22/23 no están validados.
El paquete no incluye perfiles personales, userdata, provisioning, XStream Pro,
credenciales, configuración PVR, historial, índices ni caches. La instalación
del skin no configura proveedores. Consulta [dependencias y prerequisitos](docs/DEPENDENCIES.md)
y [notices de terceros](THIRD_PARTY_NOTICES.md).

## Instalación Kodi

1. Descarga a una ubicación que Kodi pueda leer estos dos ZIP públicos y
   transfiérelos al Apple TV (por ejemplo, un recurso SMB accesible desde Kodi):
   [repository.bingie-1.0.0.zip](https://raw.githubusercontent.com/matke-84/repository.bingie/main/repository.bingie-1.0.0.zip)
   y [repository.actweeter-1.0.0.zip](repository.actweeter/repository.actweeter-1.0.0.zip).
   AcTweeteR no redistribuye los helpers upstream Bingie.
2. En Kodi habilita **Fuentes desconocidas**. En **Add-ons → Instalar desde archivo ZIP**,
   instala primero `repository.bingie-1.0.0.zip` y después
   `repository.actweeter-1.0.0.zip` desde la ubicación compartida.
3. Ve a **Instalar desde repositorio → AcTweeteR Repository → Aspecto → Skins → AcTweeteR → Instalar**.
   Kodi resolverá las dependencias declaradas desde los repositorios habilitados.
4. Tras instalar, selecciona la skin AcTweeteR y comprueba **Información del add-on**
   muestra `1.1.1`. La procedencia del canal se comprueba instalando desde la ficha
   abierta bajo **AcTweeteR Repository**. XStream, TV/PVR y la configuración personal
   deben instalarse/restaurarse por separado; no se importan desde el Mac.

El origen del repositorio Kodi es
`https://raw.githubusercontent.com/AcTweeteR/TwT-Actualizador/main/repo/`.
El repositorio está versionado manualmente. Las actualizaciones futuras solo se
publicarán cuando el propietario las solicite expresamente.

## Versiones y artefactos

- Skin: `skin.actweeter 1.1.1` (versión Kodi del paquete).
- Add-on del repositorio Kodi: `repository.actweeter 1.0.0`.
- Release global AcTweeteR: no se crea un tercer contador que duplique la versión
  del skin; manifest de distribución `1.1.1`, canal `dev`.
- SHA-256 públicos: [`checksums/SHA256SUMS`](checksums/SHA256SUMS).
- Changelog: [`CHANGELOG.md`](CHANGELOG.md) y `repo/skin.actweeter/changelog-1.1.1.txt`.
- Changelog post-update automático: **no implementado**; el texto está disponible
  para consulta manual. No existe `service.actweeter` en esta versión y no se
  mostrará ningún diálogo repetidamente.
- Rollback: es la primera versión pública; no hay versión AcTweeteR pública
  anterior. Si hubiera un problema, cambia a la skin Kodi predeterminada Estuary
  y desinstala AcTweeteR sin borrar userdata. El ZIP 1.1.0 queda solo como
  referencia local porque incluía fuentes no publicables.

## Publicación manual

No existe workflow de publicación automática. Commits/desarrollo en el repo
privado no generan publicaciones. Una futura publicación requiere petición
expresa del propietario. El script `tools/build_repository.py` solo construye y
valida los metadatos localmente; no publica ni realiza uploads.

## Seguridad y provisioning

Este repo público contiene **cero secretos**. Nunca copiar aquí usuarios,
contraseñas, URL privadas, M3U/EPG, tokens, API keys, cookies, userdata, perfiles,
bases personales, historiales, caches o contenidos de iCloud. No se implementa
provisioning en esta primera versión.

## V1.1 pendiente

No se declara V1.1 completa. Siguen pendientes perfil consumer, sync
Master/consumer, bloqueo administrativo y actualización incremental/background
del índice de Search. `profiles.xml` de referencia solo tenía Master.
