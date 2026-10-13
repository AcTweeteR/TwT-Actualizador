# TwT-Actualizador — distribución de AcTweeteR

Canal oficial de distribución Kodi de AcTweeteR. Baseline: Kodi 21.3 Omega.

## Canal estable

- Skin: `skin.actweeter 1.2.11`
- Servicio: `service.actweeter 0.4.10`
- Repositorio: `repository.actweeter 1.0.3`
- Proveedor IPTV: `plugin.video.xstream-pro 1.1.2` (adaptación de terceros bajo CC BY-NC 4.0)

El catálogo conserva los paquetes históricos para recuperación manual. Kodi reconoce las nuevas versiones como actualizaciones superiores; no se eliminan datos de usuario durante una actualización.

Paquetes actuales: [skin 1.2.11](repo/skin.actweeter/skin.actweeter-1.2.11.zip) y [servicio 0.4.10](repo/service.actweeter/service.actweeter-0.4.10.zip). El instalador Kodi obtiene estos artefactos desde el catálogo del repositorio.

## Interfaz AcTweeteR, no configuración del Mac

Los paquetes contienen los DATA predeterminados del producto. El servicio los prepara en el perfil del dispositivo y pide a Skin Shortcuts que genere sus includes mediante el mecanismo nativo. Inicio incluye Continuar viendo, Añadidas recientemente, Tendencias, Películas, Series y Favoritos. Películas y Series incluyen el año actual y el anterior, calculados dinámicamente.

Todos los widgets IPTV utilizan registros del proveedor configurado; no se sustituyen por listas externas IMDb/Trakt. Continuar viendo y Favoritos permanecen vacíos cuando no existen datos reales. Los metadatos se preparan en español cuando XStream mantiene valores de fábrica. Otros idiomas personalizados se conservan.

Antes de cambiar DATA o ajustes se guarda una copia verificada dentro del dispositivo. Las personalizaciones desconocidas no se sobrescriben: desde el configurador, «Reparar interfaz de AcTweeteR» solicita consentimiento. No se copian perfiles ni credenciales del Mac.

El preview automático necesita el bridge de AcTweeteR en el contexto de SlyGuy. El configurador solicita consentimiento para una integración local y reversible de SlyGuy 0.2.1, comprobando hashes originales exactos y conservando sus preferencias. No se redistribuyen ZIP de SlyGuy. Una versión o modificación desconocida no se parchea; las actualizaciones siguen procediendo de su repositorio oficial. El servicio dispone de rollback que respeta cambios posteriores del usuario.

## Instalar o actualizar

Si AcTweeteR Repository ya está instalado, actualiza los complementos desde Kodi tras refrescar el repositorio.

Para una instalación nueva, descarga el ZIP bootstrap desde [AcTweeteR Bootstrap](https://actweeter.github.io/TwT-Actualizador/bootstrap/) e instálalo desde **Ajustes → Complementos → Instalar desde un archivo ZIP**. Después abre AcTweeteR Repository e instala AcTweeteR. El procedimiento exacto de navegación varía por versión/plataforma y aún requiere validación limpia en tvOS.

Kodi resuelve dependencias oficiales desde su repositorio. El repositorio AcTweeteR añade los feeds de Matke BINGIE Omega y SlyGuy para sus complementos respectivos. PVR IPTV Simple puede venir integrado en algunos paquetes Kodi; que esté incluido no significa que esté habilitado o configurado.

## XStream Pro y condiciones

El ZIP 1.1.2 contiene una adaptación identificada de XStream Pro upstream commit `1aa3e67da7c03c6acc3ec7e1ca579a7f645220f4`, con su licencia y aviso de modificaciones dentro del paquete y en [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Se distribuye únicamente bajo los términos **CC BY-NC 4.0**: atribución, enlace a licencia, cambios indicados y uso no comercial. No está avalado por el autor upstream. Los iconos Tabler conservan su aviso MIT. XStream almacena la contraseña en sus propios ajustes; no reutilices credenciales del desarrollador.

## Validación y límites

Los paquetes e índices tienen SHA-256/MD5 publicados en [checksums/SHA256SUMS](checksums/SHA256SUMS). La suite privada pasó 437 pruebas. En el Apple TV afectado se verificaron filas cargadas del proveedor, años 2026/2025, sinopsis españolas, preview automático con avance y cleanup, y persistencia de DATA tras reapertura. Después de reiniciar Kodi, el propietario confirmó que las sinopsis españolas y el preview automático siguen funcionando. Se conservan las evidencias anteriores de asistente/IPTV/PVR, sin convertirlas en pruebas nuevas de esta actualización.

La instalación limpia con las versiones actuales sigue `NOT_TESTED`; estas pruebas corresponden a una actualización del perfil existente. No se declara validación universal ni QA nuevo de Android TV/macOS.

No contiene perfiles personales, credenciales, bases Kodi ni provisioning del Mac. No se distribuye PVR binario multiplataforma: usa el componente compatible de Kodi y su repositorio oficial.
