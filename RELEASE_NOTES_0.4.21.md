# AcTweeteR 0.4.21 — estable

**Kodi 21.3 Omega · Skin 1.2.18 · Servicio 0.4.21 · Repositorio 1.0.3 · XStream Pro 1.1.2.2**

## Cambios

- Trakt es opcional. IPTV y las funciones principales no dependen de autorizar Trakt.
- Se conservan las integraciones nativas separadas de `script.trakt` y XStream Pro; AcTweeteR no añade un tercer cliente ni duplica scrobbling.
- Los hubs de Películas y Series incorporan recomendaciones nativas de XStream. La fila solo puede presentar elementos con coincidencia exacta de TMDb en el catálogo del proveedor; sin autorización, coincidencia o resultados queda vacía.
- La migración de widgets v7 es versionada e idempotente, crea copia de los datos gestionados y preserva personalizaciones detectadas, preferencias, credenciales, favoritos, historial y progreso.
- XStream Pro 1.1.2.2 es una revisión basada en upstream 1.1.2, con atribuciones, licencia CC BY-NC 4.0 y aviso de modificaciones conservados dentro del paquete. No está avalada por upstream.

## Instalación y actualización

Instalación limpia: instala Kodi 21.3, permite «Orígenes desconocidos» con el diálogo nativo de Kodi, añade `https://actweeter.github.io/TwT-Actualizador/bootstrap/`, instala `repository.actweeter-1.0.3.zip` desde el navegador de archivos de Kodi y después instala AcTweeteR desde el repositorio. Acepta las confirmaciones normales de dependencias de Kodi. Configura el proveedor Xtream en el asistente. Trakt puede autorizarse ahora o más tarde.

Actualización: usa «Buscar actualizaciones» del repositorio AcTweeteR. No reinstales Kodi ni borres el perfil. Los ZIP anteriores permanecen publicados para recuperación.

## Verificación y limitaciones conocidas

- Suite automatizada: **542 PASS**. Integridad ZIP/CRC, XML, índice, MD5 y hashes: **PASS_AUTOMATED / PASS_STATIC**.
- Instalación limpia y actualización por Kodi para 0.4.21: **NOT_TESTED**.
- IPTV, PVR/EPG, reproducción, Trakt OAuth/scrobbling y renderizado de recomendaciones en Kodi runtime para esta versión: **NOT_TESTED**.
- macOS, Windows, Linux, Android, Android TV, Google TV y tvOS runtime para esta versión: **NOT_TESTED**. La metadata multiplataforma no equivale a validación en dispositivo.
- Sigue abierta la incidencia crítica de cierre normal de Kodi mientras espera trabajos de directorio `plugin://`; el componente causante no se ha identificado. El propietario autorizó expresamente aceptar este riesgo para 0.4.21; no se considera corregido y no levanta el gate para versiones futuras.

XStream Pro se distribuye bajo **CC BY-NC 4.0**: atribución, enlace a la licencia, aviso de cambios y uso no comercial. Consulte [THIRD_PARTY_NOTICES.md](https://github.com/AcTweeteR/TwT-Actualizador/blob/main/THIRD_PARTY_NOTICES.md). No se incluyen credenciales ni perfiles personales.
