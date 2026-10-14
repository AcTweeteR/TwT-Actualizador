# AcTweeteR 0.4.25 — estable

**Kodi 21.3 Omega · Skin 1.2.22 · Servicio 0.4.25 · Repositorio 1.0.3 · XStream Pro 1.1.2.5**

## Cambios

- La skin conserva las correcciones de `SetFocus()` y BingieInfo, Spotlight
  abre la ficha y evita autoplay al mover el foco, y mantiene las mejoras de
  objetivos táctiles y lectura de sinopsis.
- El servicio reduce comprobaciones ociosas de XStream y trabajo repetido al
  validar los DATA generados por Skin Shortcuts. Las métricas opcionales siguen
  apagadas por defecto.
- XStream Pro reduce la reconciliación de SQLite de una consulta por contenido
  a una lectura agrupada de filas anteriores por tipo. No cambia el esquema,
  las credenciales ni el almacenamiento de progreso.

## Verificación

- 581 pruebas automatizadas: **PASS**.
- AST Python, XML, índice Kodi/MD5, ZIP/CRC y SHA-256: **PASS_AUTOMATED**.
- El benchmark sintético de SQLite conserva exactamente filas y deltas; con
  1.000 elementos de cada tipo baja de 2.003 a 5 SELECTs. No es medición de un
  dispositivo Kodi.
- Instalación limpia, actualización runtime desde 0.4.24, reproducción, PVR y
  Trakt en dispositivos: **NOT_TESTED**.
- Android táctil y tráilers Android: **PENDING**. No se afirma que estén
  corregidos o validados.
- La incidencia crítica de cierre `CApplication::Stop → CJobManager::CancelJobs`
  sigue abierta, no se considera resuelta y su excepción de riesgo se limita a
  esta versión 0.4.25.

## Instalar o actualizar

Instalación nueva: añade
`https://actweeter.github.io/TwT-Actualizador/bootstrap/`, instala
`repository.actweeter-1.0.3.zip` desde Kodi y luego instala AcTweeteR desde el
repositorio. Actualización: refresca el repositorio y actualiza por el mecanismo
nativo de Kodi; no borres el perfil ni reinstales complementos manualmente.

XStream Pro retiene `LICENCE.txt`, atribución, enlace a CC BY-NC 4.0 y la
declaración de modificaciones. Distribución no comercial; detalles en
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
