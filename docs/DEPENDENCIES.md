# Dependencias y límites de la primera instalación

## Skin

`skin.actweeter 1.1.1` declara estas dependencias directas en `addon.xml`:

| Add-on | Versión mínima | Fuente esperada |
|---|---:|---|
| `xbmc.gui` | 5.17.0 | Kodi/Core |
| `script.bingie.helper` | 1.1.2 | Bingie upstream, agregado por `repository.actweeter` |
| `script.bingie.toolbox` | 1.0.0 | Bingie upstream, agregado por `repository.actweeter` |
| `script.bingie.widgets` | 1.0.1 | Bingie upstream, agregado por `repository.actweeter` |
| `script.skinshortcuts` | 2.0.3 | Kodi official repository o Bingie Repository |
| `resource.images.studios.coloured` | 1.0.0 | Bingie upstream, agregado por `repository.actweeter` |
| `plugin.video.tmdb.bingie.helper` | 1.0.1 | Bingie upstream, agregado por `repository.actweeter` |
| `plugin.program.autocompletion` | 2.1.3 | Bingie upstream, agregado por `repository.actweeter` |
| `script.module.bingie` | transitiva 1.0.1 | Bingie upstream, agregado por `repository.actweeter` |

Kodi Omega procesa múltiples `<dir>` dentro de una definición de repositorio,
combina las entradas de sus índices y conserva la ruta de descarga asociada a
cada entrada. `repository.actweeter 1.0.1` usa esa capacidad. El índice Bingie
publicado aquí contiene solo metadata de los seis add-ons requeridos, derivada del
índice upstream; los ZIP se descargan directamente del datadir upstream Bingie.
No se incluyen ni copian código/binarios helper. La instantánea de metadata se
actualiza únicamente en publicaciones manuales posteriores. Kodi oficial se
incluye con Kodi y proporciona `script.skinshortcuts`.

La versión instalada en el Mac no es una plantilla para copiar: algunos helpers
y `script.skinshortcuts` tienen versiones distintas a sus mínimos y el runtime
incluye una modificación local de Skin Shortcuts que no forma parte de este ZIP.
La instalación desde repositorio localiza las dependencias en el índice agregado;
el test físico de instalación completa en Apple TV/tvOS sigue pendiente y no se
promete compatibilidad tvOS hasta esa prueba.

## No incluidos

- XStream Pro (`plugin.video.xstream-pro`) ni credenciales/profiles.
- IPTV Simple, M3U, EPG ni canales.
- TMDb/Trakt cuentas, API keys, OAuth, caches o tokens.
- configuración personal BINGIE/Skin Shortcuts, favoritos, historial, progreso,
  bases de datos o widgets del Mac.
- provisioning iCloud.

Estos elementos no son dependencias del skin y deben instalarse/configurarse
privadamente en cada dispositivo. No se distribuyen aquí.

## Portabilidad

El paquete declara `<platform>all</platform>` y sus dependencias Kodi, pero solo
se ha validado en Kodi 21.3. La disponibilidad de Kodi/tvOS y la capacidad de
resolver dependencias upstream deben probarse en cada dispositivo objetivo.
