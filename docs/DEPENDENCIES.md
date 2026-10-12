# Dependencias y procedencia — AcTweeteR 1.2.8 / service 0.3.8

Baseline de catálogo: Kodi 21.3 Omega. El índice declara los mínimos reales de cada add-on; Kodi resuelve los imports según sus repositorios habilitados. El catálogo no implica que un componente esté configurado o probado en runtime.

| Componente | Mínimo / versión | Fuente | Función y estado |
|---|---:|---|---|
| skin.actweeter | 1.2.8 | AcTweeteR | Interfaz; GPL-2.0, fuente incluida en ZIP |
| service.actweeter | 0.3.8 | AcTweeteR | Asistente/servicio; GPL-2.0-or-later |
| repository.actweeter | 1.0.3 | AcTweeteR | Catálogo propio más feeds Matke Omega y SlyGuy |
| plugin.video.xstream-pro | 1.1.2 | ZIP de este catálogo | Adaptación de tercero; CC BY-NC 4.0, solo uso no comercial |
| PVR IPTV Simple | >=21.4.0 | Repositorio Kodi oficial o binario incluido por la distribución Kodi | Requisito de XStream/PVR. El paquete tvOS Kodi 21.3 examinado contiene 21.11.0; disponibilidad y habilitación se deben comprobar en el dispositivo |
| plugin.video.youtube | versión que resuelva Kodi | Repositorio Kodi oficial | Integración de tráilers; no se distribuyen sus credenciales |
| slyguy.trailers | >=0.2.1 | Feed oficial SlyGuy añadido por repository.actweeter 1.0.3 | Backend adicional de tráilers |
| Helpers script.bingie.* y plugin.video.tmdb.bingie.helper | mínimos en addon.xml | Feed Matke BINGIE Omega | Helpers de interfaz/metadatos; los ZIP se sirven desde upstream |
| Skin Shortcuts, AutoCompletion, Studio Icons y módulos | mínimos en addon.xml | Repositorio Kodi oficial | Dependencias de interfaz y módulos |

## Resolución y actualizaciones

`repository.actweeter 1.0.3` declara el feed AcTweeteR, el feed Omega de Matke y el feed SlyGuy. YouTube, PVR IPTV Simple y módulos oficiales no se copian en nuestros ZIP. XStream Pro 1.1.2 sí se publica aquí como adaptación CC BY-NC con avisos completos; Kodi lo considera servido por AcTweeteR Repository, por lo que los cambios de versión deben publicarse en este catálogo. XStream incluye su propio updater upstream; la convivencia y la persistencia de la integración parcheada requieren seguimiento, no se afirma un test de actualización aquí.

No se incluyen binarios PVR de otra plataforma. En tvOS, Kodi puede traer PVR IPTV Simple en su propio paquete; esa disponibilidad no equivale a configuración PVR/EPG funcional. Los feeds externos y el repositorio oficial deben poder alcanzarse desde la red del dispositivo.

## Estado de compatibilidad

- Kodi 21.3 Omega: versión objetivo y compatibilidad declarada por metadata.
- macOS: existen validaciones previas de partes del asistente en Master; la instalación limpia de este conjunto no está demostrada.
- Android TV / Google TV y tvOS / Apple TV: dependencias evaluadas estáticamente, pruebas runtime de esta publicación pendientes.
- Instalación limpia, autenticación IPTV, PVR/EPG y reproducción real no se deducen de la validez XML/ZIP.
