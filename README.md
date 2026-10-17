# TwT-Actualizador — distribución de AcTweeteR

Canal oficial para Kodi 21.3 Omega.

## Canal oficial — AcTweeteR 0.4.28

- Skin: `skin.actweeter 1.2.27`
- Servicio: `service.actweeter 0.4.28`
- XStream Pro: `plugin.video.xstream-pro 1.1.2.7` (CC BY-NC 4.0)
- Repositorio Kodi: `repository.actweeter 1.0.3` (sin cambios)

Los widgets compatibles presentan como máximo 20 contenidos del proveedor y
un `EXPANDIR` rojo adicional solo cuando existe una ruta de expansión
verificada. Favoritos y Pendientes se mantienen en Mis colecciones para
Películas y Series, con aislamiento por perfil/tipo y distintivos rojos de
novedades. La skin integra cambios estructurales de hit testing derivados de
touch10; no se afirma que tacto, scroll, botones de fichas ni navegación hayan
sido validados en runtime Android o tvOS. Instalación limpia y actualización
runtime tampoco se probaron.

Paquetes: [skin 1.2.27](repo/skin.actweeter/skin.actweeter-1.2.27.zip),
[servicio 0.4.28](repo/service.actweeter/service.actweeter-0.4.28.zip),
[XStream Pro 1.1.2.7](repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.7.zip).
El bootstrap usa el repositorio 1.0.3. Suite automatizada: 606 PASS y 285 subtests.
Consulta
[notas 0.4.28](RELEASE_NOTES_0.4.28.md), [manifiesto](manifests/0.4.28.json)
y [avisos de terceros](THIRD_PARTY_NOTICES.md). XStream solo se redistribuye
bajo CC BY-NC 4.0 para uso no comercial, con licencia, atribución y avisos
preservados. Las fuentes y los comandos para reconstruir exactamente estos
paquetes están en [source/0.4.28](source/0.4.28/README.md); la automatización
compara sus hashes con los artefactos publicados. La versión 0.4.27 permanece
disponible para rollback.

## Canal estable — AcTweeteR 0.4.27 (hotfix)

- Skin: `skin.actweeter 1.2.24`
- Servicio: `service.actweeter 0.4.26` (sin cambios)
- Repositorio: `repository.actweeter 1.0.3` (sin cambios)
- XStream Pro: `plugin.video.xstream-pro 1.1.2.5` (sin cambios; CC BY-NC 4.0)

Hotfix para la regresión de acciones en las fichas introducida por el
prototipo 0.4.26: se restauran los controles nativos `radiobutton` de Play,
Resume y Trailer en los dos diseños de información, con sus IDs, acciones,
condiciones y navegación. La verificación estática y automatizada pasa; la
recuperación de botones requiere confirmación runtime del usuario. Esto no
declara resueltos el tacto general, el scroll ni el foco del ratón en Android.

Paquetes: [skin 1.2.24](repo/skin.actweeter/skin.actweeter-1.2.24.zip),
[service 0.4.26](repo/service.actweeter/service.actweeter-0.4.26.zip),
[XStream Pro 1.1.2.5](repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.5.zip).
[Notas 0.4.27](RELEASE_NOTES_0.4.27.md). La suite automatizada tiene 590 PASS;
la instalación y las acciones en dispositivos siguen pendientes de runtime.
Conserva 0.4.25 para rollback. El tag 0.4.26 se mantiene intacto y esa
versión no se recomienda por la regresión confirmada.

## Canal estable — AcTweeteR 0.4.25

- Skin: `skin.actweeter 1.2.22`
- Servicio: `service.actweeter 0.4.25`
- Repositorio: `repository.actweeter 1.0.3`
- XStream Pro: `plugin.video.xstream-pro 1.1.2.5` (CC BY-NC 4.0, no comercial)

El servicio reduce verificaciones ociosas y evita trabajo redundante al
validar los DATA de Skin Shortcuts. XStream agrupa la lectura SQLite previa
por tipo de contenido durante la reconciliación del índice, manteniendo IDs y
actualizaciones incrementales. La skin conserva las correcciones de foco y
Spotlight, y las mejoras táctiles/sinopsis. Las mejoras táctiles y los tráilers
Android **no están validados en runtime**.

Paquetes: [bootstrap repository 1.0.3](docs/bootstrap/repository.actweeter-1.0.3.zip),
[skin 1.2.22](repo/skin.actweeter/skin.actweeter-1.2.22.zip),
[service 0.4.25](repo/service.actweeter/service.actweeter-0.4.25.zip),
[XStream Pro 1.1.2.5](repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.5.zip).
Notas: [0.4.25 estable](RELEASE_NOTES_0.4.25.md). 581 pruebas automatizadas
PASS; runtime de instalación y dispositivos no probado. La incidencia de
cierre de Kodi continúa abierta; la excepción aceptada por el propietario se
aplica solo a 0.4.25.

## Canal estable — AcTweeteR 0.4.24

- Skin: `skin.actweeter 1.2.20`
- Servicio: `service.actweeter 0.4.23` (sin cambios)
- Repositorio: `repository.actweeter 1.0.3` (sin cambios)
- IPTV: `plugin.video.xstream-pro 1.1.2.4` (revisión no comercial CC BY-NC 4.0)

La skin 1.2.20 añade una barra de desplazamiento vertical nativa de Kodi para
Home, amplía los objetivos táctiles de acciones y ofrece un visor desplazable
de sinopsis completa. Mantiene gestos nativos en carruseles y navegación con
mando/teclado. **El uso táctil todavía no está validado en runtime Android.**
El servicio, XStream y repository no cambian; el scrobbling de XStream/script.trakt
sigue sin validación runtime. Los paquetes anteriores se conservan.

Paquetes: [bootstrap repository 1.0.3](docs/bootstrap/repository.actweeter-1.0.3.zip), [skin 1.2.20](repo/skin.actweeter/skin.actweeter-1.2.20.zip), [service 0.4.23](repo/service.actweeter/service.actweeter-0.4.23.zip), [XStream Pro 1.1.2.4](repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.4.zip). [Release estable v0.4.24](https://github.com/AcTweeteR/TwT-Actualizador/releases/tag/v0.4.24).

Suite automatizada: **563 PASS**. Integridad ZIP/CRC, XML, índice, MD5 y
SHA-256: **PASS_AUTOMATED / PASS_STATIC**. Táctil Android y runtime en Android,
tvOS, macOS, Windows y Linux: **NOT_TESTED** para 0.4.24. Continúa abierta la
incidencia crítica de cierre de Kodi en trabajos `plugin://`; el propietario
aceptó expresamente ese riesgo solo para esta publicación 0.4.24.

## Canal estable — AcTweeteR 0.4.21

- Skin: `skin.actweeter 1.2.18`
- Servicio: `service.actweeter 0.4.21`
- Repositorio: `repository.actweeter 1.0.3`
- IPTV: `plugin.video.xstream-pro 1.1.2.2` (adaptación de terceros CC BY-NC 4.0; no comercial)

Kodi instala y actualiza los paquetes desde el índice oficial. Los artefactos anteriores se conservan para recuperación. La migración de widgets v7 es idempotente y protege los datos gestionados con backups.

Paquetes: [bootstrap repository 1.0.3](docs/bootstrap/repository.actweeter-1.0.3.zip`), [skin 1.2.18](repo/skin.actweeter/skin.actweeter-1.2.18.zip), [service 0.4.21](repo/service.actweeter/service.actweeter-0.4.21.zip), [XStream Pro 1.1.2.2](repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.2.zip). [Release estable v0.4.21](https://github.com/AcTweeteR/TwT-Actualizador/releases/tag/v0.4.21).

## Interfaz e IPTV

La skin prepara sus menús y widgets mediante mecanismos de Kodi y los DATA empaquetados; no copia perfiles de desarrollo. Los hubs de Películas y Series conservan las filas existentes y añaden recomendaciones nativas de XStream. Solo se aceptan coincidencias exactas de TMDb disponibles en el catálogo del proveedor. Sin autenticación o resultados válidos, no se muestra contenido recomendado.

La instalación necesita los datos Xtream del usuario. No se deben guardar credenciales en el repositorio ni en capturas/logs. PVR IPTV Simple y otros complementos binarios dependen de la build de Kodi y su plataforma; AcTweeteR no redistribuye un binario de una plataforma para otra.

## Trakt

Trakt es opcional. `script.trakt` conserva la propiedad del scrobbling/biblioteca Kodi y XStream mantiene su integración de cuenta/recomendaciones. AcTweeteR no comparte tokens entre complementos ni implementa un tercer cliente. Autorización y sincronización Trakt de esta versión: `NOT_TESTED` en Kodi runtime.

## Instalar o actualizar

Sigue [la guía de instalación](INSTALLATION_ALL_IN_ONE_ES.md). En breve: instala Kodi 21.3, activa «Orígenes desconocidos» mediante la confirmación de Kodi, añade `https://actweeter.github.io/TwT-Actualizador/bootstrap/`, instala `repository.actweeter-1.0.3.zip` y luego AcTweeteR desde el repositorio. Para actualizar, utiliza el actualizador nativo; no elimines datos ni el perfil.

## Licencias y artefactos

XStream Pro 1.1.2.4 está basado en upstream 1.1.2, commit `1aa3e67da7c03c6acc3ec7e1ca579a7f645220f4`. Retiene atribución, enlace CC BY-NC 4.0 y `ACTWEETER_MODIFICATIONS.txt`; no es un build avalado por el autor upstream y no puede usarse comercialmente. Consulte [avisos de terceros](THIRD_PARTY_NOTICES.md) y [SHA256SUMS](checksums/SHA256SUMS).

## Validación

Para 0.4.24, la suite es **563 PASS** y los paquetes/índice/checksums están verificados automáticamente. El comportamiento táctil en Android y el runtime de esta versión en macOS, Windows, Linux, Android, Android TV, Google TV y tvOS permanecen **NOT_TESTED**. Las autorizaciones y la sincronización Trakt tampoco se presentan como runtime validadas.

Permanece abierta una incidencia crítica de cierre de Kodi al esperar trabajos de directorio `plugin://`; su origen no se ha identificado. El propietario aceptó expresamente el riesgo para 0.4.21. No está corregido, y la excepción no se extiende a versiones futuras.

No se incluyen credenciales personales, perfiles Kodi ni datos privados. Las dependencias externas mantienen sus fuentes y licencias propias.
