# TwT-Actualizador — distribución de AcTweeteR

Canal oficial de distribución Kodi de AcTweeteR. Baseline: Kodi 21.3 Omega.

## Canal estable — AcTweeteR 0.4.18

- Skin: `skin.actweeter 1.2.16`
- Servicio: `service.actweeter 0.4.18`
- Repositorio: `repository.actweeter 1.0.3`
- Proveedor IPTV: `plugin.video.xstream-pro 1.1.2.1` (adaptación de terceros bajo CC BY-NC 4.0)

Kodi obtiene las versiones actuales desde el índice oficial. Se conservan las versiones anteriores para rollback; las migraciones no eliminan credenciales, favoritos, historial ni progreso.

Paquetes: [repositorio 1.0.3](docs/bootstrap/repository.actweeter-1.0.3.zip), [skin 1.2.16](repo/skin.actweeter/skin.actweeter-1.2.16.zip), [servicio 0.4.18](repo/service.actweeter/service.actweeter-0.4.18.zip) y [XStream Pro 1.1.2.1](repo/plugin.video.xstream-pro/plugin.video.xstream-pro-1.1.2.1.zip). También están adjuntos al [release v0.4.18](https://github.com/AcTweeteR/TwT-Actualizador/releases/tag/v0.4.18).

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

Los paquetes e índices tienen SHA-256/MD5 publicados en [checksums/SHA256SUMS](checksums/SHA256SUMS). La suite de esta candidata pasó 523 pruebas automatizadas; no equivalen a instalación real de Kodi.

**Continuar viendo:** los DATA portables contienen la ruta actualizable para instalaciones limpias; la migración v4 añade el token de refresco a los perfiles gestionados existentes con backup verificado. El servicio invalida/refresca la fila al terminar una reproducción no-preview. Esta corrección aún requiere comprobación visual en Apple TV.

**Gates por plataforma para 0.4.18:** clean install y actualización nativa: `NOT_TESTED` en macOS, Windows, Linux, Android, Android TV, Google TV y tvOS. Integridad ZIP/índice y tests: `PASS_AUTOMATED`; estructura del paquete Kodi/Python/XML: `PASS_STATIC`. No se afirma compatibilidad runtime en ninguna plataforma para esta versión.

Sigue abierta una incidencia crítica de cierre normal de Kodi durante trabajos de directorio `plugin://`; el origen no está identificado ni corregido. El propietario autorizó 0.4.18 aceptando ese riesgo únicamente para este release. Las vistas/listas remotas Trakt no están integradas en AcTweeteR. El preview automático SlyGuy necesita consentimiento para instalar el bridge local reversible; SlyGuy no se redistribuye.

No contiene perfiles personales, credenciales, bases Kodi ni provisioning del Mac. No se distribuye PVR binario multiplataforma: usa el componente compatible de Kodi y su repositorio oficial.
