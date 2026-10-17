# AcTweeteR 0.4.28 — widgets, colecciones y candidata touch10

## Componentes

- skin.actweeter 1.2.27
- service.actweeter 0.4.28
- plugin.video.xstream-pro 1.1.2.7
- repository.actweeter 1.0.3 (sin cambios)

## Cambios

- Los widgets compatibles presentan como máximo 20 contenidos del catálogo;
  cuando existe una ruta de expansión verificada, añaden un elemento rojo
  `EXPANDIR` que abre la categoría completa conservando tipo, perfil, orden y
  filtros.
- Favoritos y Pendientes se muestran dentro de Mis colecciones en Películas y
  Series. Las colecciones se aíslan por tipo/perfil y conservan la migración
  existente.
- Las etiquetas NUEVA SERIE y NUEVOS CAPÍTULOS mantienen fondo rojo y texto
  blanco.
- Integra en el código distribuible los cambios estructurales de hit testing,
  origen de carátulas y movimiento de Spotlight derivados de touch10.
- XStream Pro se distribuye con licencia CC BY-NC 4.0, atribución y aviso de
  modificaciones intactos; únicamente para uso no comercial.

## Validación y límites

- 605 pruebas automatizadas PASS; ZIP, CRC, índice Kodi, MD5, SHA-256 y
  reconstrucción reproducible verificados.
- No se realizó instalación limpia ni actualización en Kodi runtime.
- No se validaron en runtime selección táctil, scroll, botones de fichas ni
  tvOS. Las incidencias táctiles conocidas siguen abiertas.
- La versión pública 0.4.27 permanece disponible para rollback.
