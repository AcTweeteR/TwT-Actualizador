# Instalar AcTweeteR 0.4.17 en Kodi

## 1. Instala Kodi

Instala Kodi 21.3 Omega desde la fuente oficial para el dispositivo. No copies
el perfil de otra instalación.

## 2. Permite instalar el repositorio

En Kodi abre **Ajustes → Sistema → Complementos → Orígenes desconocidos**,
activa la opción y acepta el aviso de Kodi. AcTweeteR no cambia este permiso.

## 3. Añade el repositorio AcTweeteR

Abre **Ajustes → Gestor de archivos → Añadir fuente** e introduce:

`https://actweeter.github.io/TwT-Actualizador/bootstrap/`

Nombra la fuente **AcTweeteR**. Después abre **Complementos → Instalar desde
un archivo ZIP → AcTweeteR** y selecciona `repository.actweeter-1.0.3.zip`.
Añadir la fuente no instala el repositorio: Kodi debe mostrar que el ZIP se
instaló correctamente.

## 4. Instala la skin desde Kodi

Abre **Complementos → Instalar desde repositorio → AcTweeteR Repository →
Apariencia → Skin → AcTweeteR**. Selecciona **Instalar**, confirma las
dependencias que Kodi presente y acepta activar AcTweeteR cuando pregunte.
Deja que Kodi complete la instalación; no descargues dependencias por separado.

## 5. Configura IPTV y Trakt

Cuando aparezca el configurador, introduce servidor, usuario y contraseña
Xtream. El servicio conserva las credenciales en los ajustes del complemento
oficial correspondiente y no debe incluirlas en sus registros. Trakt puede
autorizarse con el procedimiento del propio complemento o posponerse para más
tarde. Kodi puede presentar confirmaciones legítimas al instalar componentes.

No escribas rutas M3U/EPG ni edites archivos. Si el catálogo, una dependencia o
la autenticación falla, usa **Reintentar** o **Reparar** y conserva el mensaje
de error sin compartir datos privados.

## Estado de validación

AcTweeteR 0.4.17 es una publicación estable, pero todavía no se ha ejecutado
una instalación limpia de esta versión en Apple TV. Tampoco se ha validado el
flujo real de Trakt. Existe una incidencia abierta de cierre de Kodi asociada a
trabajos pendientes `plugin://`; la causa sigue sin determinarse. Consulta las
[notas de la versión](RELEASE_NOTES_0.4.17.html) antes de instalar.
