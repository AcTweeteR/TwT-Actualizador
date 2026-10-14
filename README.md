# TwT-Actualizador — distribución de AcTweeteR

Canal oficial de distribución Kodi de AcTweeteR. Baseline: Kodi 21.3 Omega.

## Canal estable — AcTweeteR 0.4.17

- Skin: `skin.actweeter 1.2.15`
- Servicio: `service.actweeter 0.4.17`
- Repositorio: `repository.actweeter 1.0.3`
- Proveedor IPTV: `plugin.video.xstream-pro 1.1.2.1` (adaptación de terceros bajo CC BY-NC 4.0)

Kodi obtiene las versiones actuales desde el índice oficial. Se conservan las versiones anteriores para rollback; las migraciones no eliminan credenciales, favoritos, historial ni progreso.

Paquetes: [repositorio 1.0.3](docs/bootstrap/repository.actweeter-1.0.3.zip), [skin 1.2.15](repo/skin.actweeter/skin.actweeter-1.2.15.zip), [servicio 0.4.17](repo/service.actweeter/service.actweeter-0.4.17.zip) y [XStream Pro 1.1.2.1](repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.1.zip). También están adjuntos al [release v0.4.17](https://github.com/AcTweeteR/TwT-Actualizador/releases/tag/v0.4.17).

## Interfaz AcTweeteR, no configuración del Mac

Los paquetes contienen los DATA predeterminados del producto. El servicio los prepara en el perfil del dispositivo y pide a Skin Shortcuts que genere sus includes mediante el mecanismo nativo. Inicio incluye Continuar viendo, Añadidas recientemente, Tendencias, Películas, Series y Favoritos. Películas y Series incluyen el año actual y el anterior, calculados dinámicamente.

Todos los widgets IPTV utilizan registros del proveedor configurado; no se sustituyen por listas externas IMDb/Trakt. Continuar viendo y Favoritos permanecen vacíos cuando no existen datos reales. Los metadatos se preparan en español cuando XStream mantiene valores de fábrica. Otros idiomas personalizados se conservan.

Antes de cambiar DATA o ajustes se guarda una copia verificada dentro del dispositivo. Las personalizaciones desconocidas no se sobrescriben: desde el configurador, «Reparar interfaz de AcTweeteR» solicita consentimiento. No se copian perfiles ni credenciales del Mac.

El preview automático necesita el bridge de AcTweeteR en el contexto de SlyGuy. El configurador solicita consentimiento para una integración local y reversible de SlyGuy 0.2.1, comprobando hashes originales exactos y conservando sus preferencias. No se redistribuyen ZIP de SlyGuy. Una versión o modificación desconocida no se parchea; las actualizaciones siguen procediendo de su repositorio oficial. El servicio dispone de rollback que respeta cambios posteriores del usuario.

## Instalar o actualizar

Para empezar desde cero, instala Kodi 21.3, activa **Orígenes desconocidos** en Kodi y sigue los pasos de [Instalación](https://actweeter.github.io/TwT-Actualizador/INSTALLATION_ALL_IN_ONE_ES.html). El bootstrap instala AcTweeteR Repository; luego instala AcTweeteR desde el repositorio y acepta las confirmaciones normales de Kodi.

El asistente solicita servidor, usuario y contraseña IPTV, y ofrece autorizar Trakt mediante su flujo oficial o continuar más tarde. Kodi puede mostrar confirmaciones de instalación de dependencias. No se ha validado todavía una instalación limpia de esta versión en Apple TV.

Kodi resuelve dependencias oficiales desde su repositorio. El repositorio AcTweeteR añade los feeds de Matke BINGIE Omega y SlyGuy para sus complementos respectivos. PVR IPTV Simple puede venir integrado en algunos paquetes Kodi; que esté incluido no significa que esté habilitado o configurado.

## XStream Pro y condiciones

El ZIP 1.1.2.1 adapta XStream Pro upstream commit `1aa3e67da7c03c6acc3ec7e1ca579a7f645220f4`. Conserva licencia, atribución, enlace, aviso de modificaciones y condiciones **CC BY-NC 4.0** en el paquete y en [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Uso no comercial; no existe aval del autor upstream. Los iconos Tabler conservan su aviso MIT. XStream guarda la contraseña en sus propios ajustes.

## Validación y límites

Los paquetes e índices tienen SHA-256/MD5 publicados en [checksums/SHA256SUMS](checksums/SHA256SUMS). La suite de esta candidata pasó 510 pruebas automatizadas. Los resultados runtime históricos pertenecen a versiones/perfiles anteriores; no son pruebas de 0.4.17.

**Pendiente de runtime:** instalación limpia y actualización de 0.4.17, autorización y sincronización Trakt, IPTV/PVR/EPG, reproducción VOD y tráilers con este candidato; no se afirma compatibilidad runtime en Apple TV, Android TV, macOS, Windows o Linux. Sigue abierta una incidencia de cierre normal de Kodi tras consultas de directorios `plugin://`; el origen no está identificado ni corregido. Las vistas/listas remotas Trakt no están integradas en AcTweeteR. El preview automático SlyGuy necesita consentimiento para instalar el bridge local reversible; SlyGuy no se redistribuye.

No contiene perfiles personales, credenciales, bases Kodi ni provisioning del Mac. No se distribuye PVR binario multiplataforma: usa el componente compatible de Kodi y su repositorio oficial.
