# AcTweeteR 1.2.2 — beta experimental

Requiere Kodi 21 Omega. La instalación limpia no está validada. La corrección
de primer arranque aún necesita QA real en Android TV/Google TV y tvOS.

## Instalar o actualizar

Si ya tienes AcTweeteR Repository, abre **Complementos → Instalar desde
repositorio → AcTweeteR Repository → Aspecto → Skin → AcTweeteR** y aplica las
actualizaciones ofrecidas por Kodi. No borres los datos de Kodi.

Para una instalación nueva, instala primero
[repository.actweeter-1.0.2.zip](https://raw.githubusercontent.com/AcTweeteR/TwT-Actualizador/main/repo/repository.actweeter/repository.actweeter-1.0.2.zip)
desde Kodi mediante **Ajustes → Complementos → Instalar desde un archivo ZIP**.
Después abre el repositorio AcTweeteR e instala la skin. En algunas instalaciones
Kodi necesita que se añada y habilite previamente el repositorio externo Matke
BINGIE Omega para resolver helpers heredados; AcTweeteR no empaqueta addons de
terceros. Acepta la dependencia `service.actweeter` cuando Kodi la solicite.

La skin muestra un estado de bienvenida incluso cuando no hay IPTV, biblioteca
ni widgets configurados. Usa las flechas para abrir el menú, y desde él ve al
botón de configuración. Configurar IPTV, PVR, YouTube y Trakt es opcional según
las funciones que quieras usar. No introduzcas contraseñas en archivos de la
skin.

SlyGuy Trailers es un complemento externo opcional; debe instalarse desde el
repositorio original de su desarrollador. No forma parte de los ZIP de
AcTweeteR.

## Límites conocidos

- La corrección está probada estáticamente y mediante la suite automatizada; no
  se ha probado en tvOS/Apple TV ni Android TV/Google TV.
- La instalación limpia aún no se ha validado en un dispositivo nuevo.
- Al reportar errores, incluye Kodi, plataforma, skin/servicio y pasos de
  reproducción. Redacta secretos y URLs privadas de los logs.
