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

La URL pública de bootstrap es **https://actweeter.github.io/TwT-Actualizador/bootstrap/**.
En Kodi: **Ajustes → Explorador de archivos → Añadir fuente**, introduce esa URL;
después **Add-ons → Instalar desde archivo ZIP → fuente AcTweeteR →
`repository.actweeter-1.0.1.zip`**. A continuación abre **Instalar desde repositorio
→ AcTweeteR Repository → Aspecto → Skins → AcTweeteR → Instalar** y selecciona la skin.

`repository.actweeter 1.0.1` publica el índice AcTweeteR y un índice filtrado de
metadata upstream Bingie para las dependencias declaradas. Kodi agrega ambos
directorios nativamente y descarga los ZIP upstream directamente de su repositorio;
no se copian ni redistribuyen esos helpers, y no hace falta instalar
`repository.bingie` por separado. Esta resolución está validada contra el código
de repositorios de Kodi Omega y sus índices/ZIP HTTP; la prueba física en Apple TV
sigue pendiente. Kodi oficial continúa siendo el origen de `script.skinshortcuts`.

Después de instalar, selecciona AcTweeteR y comprueba **Información del add-on**
indica `1.1.1`; su ficha debe aparecer bajo **AcTweeteR Repository**. XStream,
TV/PVR y la configuración personal deben instalarse/restaurarse por separado; no
se importan desde el Mac. Las futuras publicaciones seguirán siendo manuales y
solo se harán a petición expresa del propietario.

## Versiones y artefactos

- Skin: `skin.actweeter 1.1.1` (versión Kodi del paquete).
- Add-on del repositorio Kodi: `repository.actweeter 1.0.1` (bootstrap GitHub Pages
  y agregación nativa del índice de dependencias Bingie).
- Release global AcTweeteR: no se crea un tercer contador que duplique la versión
  del skin; manifest de distribución `1.1.1`, canal `dev`.
- SHA-256 públicos: [`checksums/SHA256SUMS`](checksums/SHA256SUMS).
- Changelog: [`CHANGELOG.md`](CHANGELOG.md) y `repo/skin.actweeter/changelog-1.1.1.txt`.
- Changelog post-update automático: **no implementado**; el texto está disponible
  para consulta manual. No existe `service.actweeter` en esta versión y no se
  mostrará ningún diálogo repetidamente.
- Rollback: conserva `repository.actweeter 1.0.0` y publica el ZIP `1.0.1` en
  paralelo. Si el nuevo bootstrap falla, instala el ZIP 1.0.0 desde el enlace
  histórico del repositorio y vuelve a usar Estuary; no borres userdata.
  El ZIP 1.1.0 queda solo como referencia local porque incluía fuentes no publicables.

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
