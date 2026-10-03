# Dependencias de instalación de AcTweeteR

`skin.actweeter 1.1.2` conserva todas las dependencias obligatorias de 1.1.1.
Solo ajusta los mínimos de dos dependencias para que la selección predeterminada
de Kodi Omega pueda resolverlas desde su repositorio oficial.

## Causa de los dos nodos no disponibles

Kodi Omega, por defecto, prefiere la versión del repositorio oficial cuando un ID
existe también en uno privado. Solo elige la versión privada más alta si la
preferencia global “Update official add-ons from” está en “Any repository”. El
código de Omega realiza esa selección en `CAddonRepos::FindDependency` y después
comprueba el mínimo en `AddonInstaller`; si la versión seleccionada no lo cumple,
la dependencia se informa como no disponible.

Así, 1.1.1 pedía `plugin.program.autocompletion >=2.1.3` aunque Kodi oficial ofrece
2.1.2, y `resource.images.studios.coloured >=1.0.0` aunque Kodi oficial ofrece
0.0.24. Los índices Bingie sí ofrecían versiones privadas superiores, pero no
podían imponerse a la política predeterminada. La interfaz AcTweeteR consume la
ruta normal de plugin del AutoCompletion oficial, y el recurso oficial conserva
el punto de extensión `kodi.resource.images` de tipo `studios`. El paquete de
Studio Icons oficial puede tener menor cobertura de logos que el fork modificado;
la API y el fallback visual del skin siguen siendo los mismos.

La skin 1.1.2 mantiene las dos dependencias obligatorias, con mínimos `2.1.2` y
`0.0.24`. No se modifica la preferencia global de seguridad ni se elimina una
dependencia. Kodi oficial ofrece asimismo `script.module.autocompletion 2.1.1`,
que satisface el mínimo `2.0.5` requerido por el addon de teclado.

## Cierre transitivo calculado

Resolución calculada con la metadata de skin 1.1.2, el índice Kodi Omega, los
índices upstream Bingie filtrados publicados y el manifest de sistema de Kodi
21.3. Los imports `xbmc.*`/`kodi.*` son dependencias de core/sistema.

| Nodo | Versión requerida | Versión elegida | Origen |
|---|---:|---:|---|
| `skin.actweeter` | — | 1.1.2 | AcTweeteR |
| `xbmc.gui` | 5.17.0 | 5.17.0 | Kodi core |
| `script.bingie.helper` | 1.1.2 | 1.1.2 | AcTweeteR metadata → Bingie upstream ZIP |
| `script.bingie.toolbox` | 1.0.0 | 1.0.0 | AcTweeteR metadata → Bingie upstream ZIP |
| `script.bingie.widgets` | 1.0.1 | 1.0.1 | AcTweeteR metadata → Bingie upstream ZIP |
| `script.skinshortcuts` | 2.0.3 | 2.0.3 | Kodi official |
| `resource.images.studios.coloured` | 0.0.24 | 0.0.24 | Kodi official |
| `plugin.video.tmdb.bingie.helper` | 1.0.1 | 1.0.3 | AcTweeteR metadata → Bingie upstream ZIP |
| `plugin.program.autocompletion` | 2.1.2 | 2.1.2 | Kodi official |
| `script.module.bingie` | 1.0.1 | 1.0.1 | AcTweeteR metadata → Bingie upstream ZIP |
| `script.module.autocompletion` | 2.0.5 | 2.1.1 | Kodi official |
| `script.module.simplejson` | 3.3.0 | 3.19.1+matrix.1 | Kodi official |
| `script.module.simplecache` | 2.0.2 | 2.0.2 | Kodi official |
| `script.module.requests` | 2.9.1 | 2.31.0 | Kodi official |
| `script.module.infotagger` | 0.0.4/0.0.5 | 0.0.8 | Kodi official |
| `script.module.addon.signals` | 0.0.6 | 0.0.6+matrix.1 | Kodi official |
| `script.module.beautifulsoup4` | 4.9.3 | 4.12.2 | Kodi official |
| `script.module.qrcode` | 6.1.0 | 6.1.0+matrix.3 | Kodi official |
| `script.module.soupsieve` | 2.4.1 | 2.4.1 | Kodi official |
| `script.module.six` | 1.14.0+matrix.1 | 1.16.0+matrix.1 | Kodi official |
| `script.module.certifi` | 2023.5.7 | 2023.5.7 | Kodi official |
| `script.module.chardet` | 5.1.0 | 5.1.0 | Kodi official |
| `script.module.idna` | 3.4.0 | 3.10.0 | Kodi official |
| `script.module.urllib3` | 1.26.16+matrix.1 | 2.2.3 | Kodi official |
| `script.module.unidecode` | 1.1.1+matrix.2 | 1.3.6 | Kodi official |
| `script.module.simpleeval` | 0.9.10 | 0.9.13 | Kodi official |
| `script.module.pil` | 1.1.7 | 5.1.0 | Kodi system/bundled |
| `xbmc.python`, `xbmc.addon`, `kodi.resource` | varies | Kodi 21.3 core API | Kodi core/system |

No hay nodos obligatorios `MISSING` en este cierre. No se copian paquetes helper
al repositorio público: los ZIP Bingie se sirven desde el upstream y los ZIP
oficiales desde el repositorio Kodi incluido en Kodi.

## Dependencias directas y portabilidad

La skin también requiere Kodi GUI 5.17.0, Bingie Helper 1.1.2, Bingie Toolbox
1.0.0, Bingie Widgets 1.0.1, Skin Shortcuts 2.0.3, TMDb Bingie Helper 1.0.1,
Studio Icons 0.0.24 y AutoCompletion 2.1.2. XStream Pro, PVR, credenciales,
userdata, historial y caches personales no son dependencias del paquete y no se
distribuyen.

El cierre anterior es validación estática de índices/metadata y no sustituye la
reinstalación física en Apple TV. tvOS continúa pendiente de retest.
