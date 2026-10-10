# AcTweeteR 1.2.0 — instalación beta experimental

Esta es una beta experimental para Kodi 21 (Omega). La instalación limpia aún no se ha validado. No se afirma compatibilidad runtime con otras plataformas.

## Instalar el repositorio

1. Descarga [repository.actweeter-1.0.2.zip](https://raw.githubusercontent.com/AcTweeteR/TwT-Actualizador/main/repo/repository.actweeter/repository.actweeter-1.0.2.zip). No lo descomprimas.
2. En Kodi, abre **Ajustes** (engranaje) → **Complementos**.
3. Elige **Instalar desde un archivo ZIP** y selecciona el ZIP descargado. Si Kodi pregunta si permite fuentes desconocidas, habilítalas desde el aviso de Kodi y vuelve a instalar el archivo.
4. Abre **Instalar desde repositorio** → **AcTweeteR Repository** → **Aspecto** → **Skin** → **AcTweeteR** → **Instalar**.
5. Acepta las dependencias que Kodi pueda resolver desde los repositorios configurados. La skin necesita componentes externos; en una instalación nueva puede ser necesario añadir y habilitar antes el repositorio Matke BINGIE Omega. El repositorio AcTweeteR no redistribuye complementos de terceros.
6. Cuando Kodi ofrezca activar AcTweeteR, confirma el cambio de skin. Sigue el asistente inicial si aparece.

## Servicio

La skin declara `service.actweeter` como dependencia; Kodi debe instalar la versión 0.2.0 desde el catálogo AcTweeteR. Si no aparece, actualiza el catálogo del repositorio y vuelve a consultar sus complementos.

## Tráilers y servicios opcionales

SlyGuy Trailers es opcional y se instala desde el repositorio original de su desarrollador. No forma parte de los ZIP AcTweeteR. Sin él, las funciones de tráiler que dependen de SlyGuy no estarán disponibles. YouTube/OAuth e IPTV también se configuran por separado cuando el usuario decide utilizar esas funciones; no introduzcas credenciales en archivos de la skin.

## Alcance y soporte

- Versiones beta: skin 1.2.0, servicio 0.2.0 y repositorio 1.0.2.
- Kodi 21 Omega es la versión de referencia.
- La instalación limpia no se ha probado: pueden surgir dependencias que requieran pasos adicionales.
- Para informar de un problema, incluye la versión de Kodi, el sistema, las versiones de los tres complementos y los pasos para reproducirlo. Antes de adjuntar logs, elimina nombres de usuario, tokens, contraseñas, cookies y URL privadas.
