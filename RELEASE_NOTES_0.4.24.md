# AcTweeteR 0.4.24 — estable

**Kodi 21.3 Omega · Skin 1.2.20 · Servicio 0.4.23 · Repositorio 1.0.3 · XStream Pro 1.1.2.4**

## Cambios

- La Home incorpora una barra de desplazamiento vertical nativa conectada a
  sus widgets, proporcionando un punto de inicio de gesto más predecible.
- Las acciones principales de las fichas tienen objetivos táctiles mayores.
- Las fichas de películas y series permiten abrir la sinopsis completa en el
  visor desplazable nativo de Kodi.
- Se conservan los gestos nativos horizontales y la navegación por mando,
  teclado y ratón.
- No cambian el servicio, XStream, las credenciales, el progreso ni la
  configuración del usuario. Se conserva la versión anterior para rollback.

## Verificación

- 563 pruebas automatizadas: **PASS**.
- XML, ZIP/CRC, versiones e índice Kodi/MD5: **PASS_AUTOMATED**.
- Validación del gesto táctil en una pantalla Android: **PENDING**. Estas
  mejoras no se presentan como runtime validadas.
- Runtime de esta versión en Android, Android TV, Google TV, tvOS, macOS,
  Windows y Linux: **NOT_TESTED**.
- La incidencia crítica conocida de cierre de Kodi mientras espera trabajos
  `plugin://` sigue abierta y sin causa identificada. El propietario aceptó
  expresamente este riesgo solo para la versión estable 0.4.24; no se considera
  resuelta ni se extiende la excepción a versiones posteriores.

## Instalar o actualizar

Para una instalación nueva, añade
`https://actweeter.github.io/TwT-Actualizador/bootstrap/`, instala
`repository.actweeter-1.0.3.zip` desde Kodi y después instala AcTweeteR desde el
repositorio. Para actualizar, refresca el mismo repositorio y actualiza la
skin mediante Kodi; no borres el perfil ni reinstales complementos manualmente.

XStream Pro conserva licencia, atribución y avisos CC BY-NC 4.0; distribución
no comercial. Consulta `THIRD_PARTY_NOTICES.md`.
