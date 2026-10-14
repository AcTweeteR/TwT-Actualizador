# TwT-Actualizador — distribución de AcTweeteR

Canal oficial para Kodi 21.3 Omega.

## Canal estable — AcTweeteR 0.4.23

- Skin: `skin.actweeter 1.2.18` (sin cambios)
- Servicio: `service.actweeter 0.4.23`
- Repositorio: `repository.actweeter 1.0.3` (sin cambios)
- IPTV: `plugin.video.xstream-pro 1.1.2.4` (revisión no comercial CC BY-NC 4.0)

XStream Pro 1.1.2.4 añade a los ListItem reproducibles los metadatos de
películas/episodios y la propiedad `script.trakt.ids` esperada por script.trakt
3.9.0. El cambio no incorpora OAuth ni scrobbling propio y no modifica las URL
de reproducción ni el almacenamiento de progreso. El scrobbling real todavía
no se ha validado en Kodi runtime. Los paquetes anteriores se conservan.

Paquetes: [bootstrap repository 1.0.3](docs/bootstrap/repository.actweeter-1.0.3.zip), [skin 1.2.18](repo/skin.actweeter/skin.actweeter-1.2.18.zip), [service 0.4.23](repo/service.actweeter/service.actweeter-0.4.23.zip), [XStream Pro 1.1.2.4](repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.4.zip). [Release estable v0.4.23](https://github.com/AcTweeteR/TwT-Actualizador/releases/tag/v0.4.23).

Suite automatizada: **553 PASS**. Integridad ZIP/CRC, XML, índice, MD5 y
SHA-256: **PASS_AUTOMATED / PASS_STATIC**. Integración con script.trakt en
reproducción real y runtime en Android, tvOS, macOS, Windows y Linux:
**NOT_TESTED**. Continúa abierta la incidencia crítica de cierre de Kodi en
trabajos `plugin://`; el propietario acepta expresamente ese riesgo solo para
esta publicación 0.4.23.

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

Sigue [la guía de instalación](INSTALLATION_ALL_IN_ONE_ES.md). En breve: instala Kodi 21.3, activa «Orígenes desconocidos» mediante la confirmación de Kodi, añade `https://actweeter.github.io/TwT-Actualizador/bootstrap/`, instala `repository.actweeter-1.0.3.zip) y luego AcTweeteR desde el repositorio. Para actualizar, utiliza el actualizador nativo; no elimines datos ni el perfil.

## Licencias y artefactos

XStream Pro 1.1.2.4 está basado en upstream 1.1.2, commit `1aa3e67da7c03c6acc3ec7e1ca579a7f645220f4`. Retiene atribución, enlace CC BY-NC 4.0 y `ACTWEETER_MODIFICATIONS.txt`; no es un build avalado por el autor upstream y no puede usarse comercialmente. Consulte [avisos de terceros](THIRD_PARTY_NOTICES.md) y [SHA256SUMS](checksums/SHA256SUMS).

## Validación

Suite automatizada de esta candidata: **542 PASS**. ZIP, CRC, XML, índice y checksums: **PASS_AUTOMATED / PASS_STATIC**. Instalación limpia, actualización y funciones IPTV/PVR/EPG/Trakt/recomendaciones/reproducción en Kodi runtime para 0.4.21: **NOT_TESTED**. Tampoco se declara validación runtime en macOS, Windows, Linux, Android, Android TV, Google TV o tvOS.

Permanece abierta una incidencia crítica de cierre de Kodi al esperar trabajos de directorio `plugin://`; su origen no se ha identificado. El propietario aceptó expresamente el riesgo para 0.4.21. No está corregido, y la excepción no se extiende a versiones futuras.

No se incluyen credenciales personales, perfiles Kodi ni datos privados. Las dependencias externas mantienen sus fuentes y licencias propias.
