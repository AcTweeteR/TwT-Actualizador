# AcTweeteR 0.4.29 — actualización oficial de feed

Esta candidata corrige el selector de contenido expandible de widgets. En
1.2.27 el skin comprobaba `String.Contains` sobre la ruta completa del widget,
que contenía una expresión dinámica de refresco. Kodi registró un error al
parsear esa condición. La skin 1.2.28 selecciona el include a partir de una
propiedad explícita propagada por la plantilla Skin Shortcuts.

El servicio 0.4.29 aplica una migración versionada e idempotente a los DATA
predeterminados que aún coinciden con la versión que AcTweeteR había
generado. Crea un backup antes de escribir. DATA personalizados que no
coinciden con el hash previo no se sobrescriben sin consentimiento.

En rutas admitidas, XStream entrega como máximo 20 títulos más la entrada
EXPANDIR; al activarla, la ruta de catálogo conserva tipo y filtros compatibles.
Las rutas de recomendaciones y categorías sin expansión verificada no se
marcan como expandibles.

## Verificación

- Pruebas automatizadas específicas: 9 PASS.
- Python AST/compilación y XML estático: PASS.
- ZIP CRC, índice y checksums: verificados para artefactos candidatos.
- Instalación/actualización por Kodi y renderizado/selección de EXPANDIR en
  Lenovo: NOT_TESTED en esta candidata.
- Tráilers manuales/automáticos, distintivos, colecciones, botones y scroll:
  NOT_TESTED después de esta candidata.
- No se declara soporte táctil, runtime ni instalación limpia como validado.

Esta actualización está disponible en el feed oficial de Kodi desde el commit
`76428bf51301d78dc61d91d083a5517ea2147e26`. El artefacto de 0.4.28 permanece
disponible para rollback. La instalación y validación runtime en Lenovo aún
no se han completado; la disponibilidad pública no equivale a PASS_RUNTIME.
