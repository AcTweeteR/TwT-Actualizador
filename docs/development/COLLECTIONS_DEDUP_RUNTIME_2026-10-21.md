# Colecciones: duplicados de catálogo (Lenovo, 2026-10-21)

La validación real sobre Kodi 21.3 Lenovo con XStream 1.1.2.18 confirmó grabación independiente en Favoritos y Pendientes y persistencia exacta tras un reinicio completo: película (ID 868039) y serie VisionQuest (ID 7449), una pertenencia por carpeta y tipo. Sin embargo, el catálogo IPTV contiene **dos filas con series_id=7449** y la vista `browse=1` representaba dos carátulas en cada colección, pese a una sola pertenencia.

XStream 1.1.2.19 elimina filas de proveedor duplicadas por ID **solamente** en `view=favorites` y `view=pending`, antes de paginar. Preserva la primera entrada existente y no altera el catálogo general, las diferentes ediciones con IDs diferentes ni los datos persistidos. Añade regresión con ID idéntico para película y serie, catalog entries duplicadas y ambos tipos de colección.

Validación pendiente: nueva Beta instalada en Lenovo y cuatro vistas con una sola carátula cada una; posterior retirada de los títulos de prueba mediante menú de Kodi y comprobación del estado inicial. La pulsación larga inyectada con ADB no abre el menú; un toque sostenido físico sigue sin poder certificarse a distancia.
