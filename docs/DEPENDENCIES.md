# Dependencias y límites de la primera instalación

## Skin

`skin.actweeter 1.1.1` declara estas dependencias directas en `addon.xml`:

| Add-on | Versión mínima | Fuente esperada |
|---|---:|---|
| `xbmc.gui` | 5.17.0 | Kodi/Core |
| `script.bingie.helper` | 1.1.2 | Bingie Repository |
| `script.bingie.toolbox` | 1.0.0 | Bingie Repository |
| `script.bingie.widgets` | 1.0.1 | Bingie Repository |
| `script.skinshortcuts` | 2.0.3 | Kodi official repository o Bingie Repository |
| `resource.images.studios.coloured` | 1.0.0 | Bingie Repository |
| `plugin.video.tmdb.bingie.helper` | 1.0.1 | Bingie Repository |
| `plugin.program.autocompletion` | 2.1.3 | Bingie Repository |

Kodi resuelve dependencias declaradas al instalar el skin cuando el repositorio
que ofrece cada add-on está instalado y habilitado. El paquete no incluye esos
add-ons upstream. Instala el repositorio Bingie upstream indicado en README;
Kodi oficial se incluye con la instalación Kodi.

La versión instalada en el Mac no es una plantilla para copiar: algunos helpers
y `script.skinshortcuts` tienen versiones distintas a sus mínimos y el runtime
incluye una modificación local de Skin Shortcuts que no forma parte de este ZIP.
La primera instalación en Apple TV debe validar la resolución real de
dependencias; no se promete compatibilidad tvOS todavía.

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
