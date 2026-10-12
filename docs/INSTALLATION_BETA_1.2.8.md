# Instalar AcTweeteR desde cero (Kodi 21 Omega)

Esta guía se refiere al catálogo AcTweeteR 1.2.8 / 0.3.8 / 1.0.3. La instalación limpia aún no está validada en tvOS ni Android TV.

1. En Kodi, abre **Ajustes** (engranaje) → **Complementos**.
2. Abre **Instalar desde un archivo ZIP**. Si Kodi pide habilitar fuentes desconocidas para instalar el bootstrap, sigue el diálogo nativo de Kodi.
3. Añade como fuente la dirección que aparece en [AcTweeteR Bootstrap](https://actweeter.github.io/TwT-Actualizador/bootstrap/) y elige `repository.actweeter-1.0.3.zip`. Si tu versión de Kodi no muestra el ZIP dentro de esa fuente, detente y usa el enlace directo del bootstrap en un dispositivo navegador; no cambies la seguridad de Kodi.
4. Vuelve a **Complementos → Instalar desde repositorio → AcTweeteR Repository** y elige la skin AcTweeteR. Acepta los avisos de dependencias de Kodi.
5. Al abrir la skin, sigue el asistente. Las credenciales IPTV solo se introducen en los ajustes oficiales de XStream Pro. XStream Pro 1.1.2 almacena su contraseña en sus propios ajustes; no compartas capturas ni logs con esos datos.
6. Espera a que Kodi refresque los catálogos de complementos. Los paquetes oficiales, Matke y SlyGuy se obtienen de sus fuentes respectivas; si un feed no está disponible, el asistente debe dejar el estado incompleto y permitir reparación.

La presencia de XStream, PVR, YouTube o SlyGuy instalado no demuestra autenticación, catálogo, EPG o reproducción. No configures PVR con una URL que contenga credenciales en una captura o informe.

En Apple TV/tvOS el procedimiento de red, foco y selección de ZIP está pendiente de Device QA. La publicación no actualiza por sí sola un Apple TV apagado/desconectado: el dispositivo debe refrescar el repositorio desde Kodi.
