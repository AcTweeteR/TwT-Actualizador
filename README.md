# TwT-Actualizador — distribución de AcTweeteR

Canal oficial de distribución Kodi de AcTweeteR. Baseline: Kodi 21.3 Omega.

## Versiones disponibles

- Skin: `skin.actweeter 1.2.8`
- Servicio: `service.actweeter 0.3.8`
- Repositorio: `repository.actweeter 1.0.3`
- Proveedor IPTV: `plugin.video.xstream-pro 1.1.2` (adaptación de terceros bajo CC BY-NC 4.0)

El catálogo conserva versiones anteriores. La skin 1.2.8 ya estaba publicada; esta sincronización añade el servicio 0.3.8, el repositorio 1.0.3 y el paquete XStream indicado.

## Instalar o actualizar

Si AcTweeteR Repository ya está instalado, actualiza los complementos desde Kodi tras refrescar el repositorio.

Para una instalación nueva, descarga el ZIP bootstrap desde [AcTweeteR Bootstrap](https://actweeter.github.io/TwT-Actualizador/bootstrap/) e instálalo desde **Ajustes → Complementos → Instalar desde un archivo ZIP**. Después abre AcTweeteR Repository e instala AcTweeteR. El procedimiento exacto de navegación varía por versión/plataforma y aún requiere validación limpia en tvOS.

Kodi resuelve dependencias oficiales desde su repositorio. El repositorio AcTweeteR añade los feeds de Matke BINGIE Omega y SlyGuy para sus complementos respectivos. PVR IPTV Simple puede venir integrado en algunos paquetes Kodi; que esté incluido no significa que esté habilitado o configurado.

## XStream Pro y condiciones

El ZIP 1.1.2 contiene una adaptación identificada de XStream Pro upstream commit `1aa3e67da7c03c6acc3ec7e1ca579a7f645220f4`, con su licencia y aviso de modificaciones dentro del paquete y en [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Se distribuye únicamente bajo los términos **CC BY-NC 4.0**: atribución, enlace a licencia, cambios indicados y uso no comercial. No está avalado por el autor upstream. Los iconos Tabler conservan su aviso MIT. XStream almacena la contraseña en sus propios ajustes; no reutilices credenciales del desarrollador.

## Validación y límites

Los paquetes e índices tienen SHA-256/MD5 publicados en [checksums/SHA256SUMS](checksums/SHA256SUMS). La suite automatizada privada pasó 363 pruebas y 13 subtests para el candidato. Esto no es una instalación limpia ni una prueba de reproducción en todos los dispositivos. La instalación runtime de esta publicación en Apple TV/tvOS y Android TV/Google TV queda pendiente; no se afirma que esos dispositivos estén actualizados.

No contiene perfiles personales, credenciales, bases Kodi ni provisioning del Mac. No se distribuye PVR binario multiplataforma: usa el componente compatible de Kodi y su repositorio oficial.
