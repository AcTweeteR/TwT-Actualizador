# Kodi AcTweeteR — Beta de correcciones prioritarias (4 de noviembre de 2026)

## Canal de instalación

Repositorio **AcTweeteR Testing** (sin modificar Stable):
https://actweeter.github.io/TwT-Actualizador/testing/repo/addons.xml

Paquetes candidatos:
- Skin `1.2.40~beta1`
- Service `0.4.98~beta1`
- XStream `1.1.2.40~beta1`

### Cambios

1. **Tráilers:** captura homogénea de IDs de vídeo YouTube de 11 caracteres, incluso al pasar de una carátula a otra dentro del mismo widget; el tráiler manual intenta la ruta disponible antes de una búsqueda de título. En equipos sin SlyGuy instalado, Spotlight y widgets aprovechan el tráiler directo cuando está disponible. No se distribuyen archivos modificados de SlyGuy.
2. **Series:** temporadas con tipo nativo `seasons`, nombre de serie y arte habitual; episodios con temporada/número, imagen de episodio o, en su defecto, imagen de la serie y sinopsis específica cuando el proveedor la facilita. Los metadatos se entregan también en perfiles antiguos con el interruptor general desactivado, manteniendo los interruptores individuales.
3. **Progreso acumulativo:** nuevo menú de contexto «Establecer progreso hasta aquí (AcTweeteR)». Marca positivamente todos los episodios de temporadas anteriores y hasta el episodio seleccionado. Requiere un inventario completo y reciente (≤14 días), identidad inequívoca y perfil coincidente; conserva capítulos posteriores ya vistos y excluye especiales S0. Usa los almacenes nativos que ya coordinan Trakt.
4. **EXPANDIR:** en listas de proveedor se aplican 19 carátulas como máximo más la entrada final EXPANDIR cuando hay catálogo adicional. Incluye rutas predeterminadas de Inicio, películas y series, además de una vía hacia catálogo completo cuando una lista de tendencias/populares solo contiene unos pocos títulos.
5. **EPG:** la actualización deja de depender únicamente de abrir una sincronización manual. Un chequeo en reposo verifica la antigüedad del XMLTV y exporta de nuevo el archivo mediante el bloqueo PVR preexistente. No sustituye un archivo por datos históricos sin programación actual suficiente; el servicio solo recarga IPTV Simple cuando no hay vídeo y el sistema está inactivo. Conserva los archivos e instancias ajenos y no borra la base de datos EPG de Kodi.
6. **Menús:** se evita la inserción duplicada de acciones de favoritos de episodios.

### Seguridad y límites

- La distribución se genera a partir de tres ZIP Stable cuyos SHA-256 originales se verifican antes de aplicar las modificaciones.
- Los tres ZIP Beta superan compilación Python, validación XML, integridad ZIP y verificación del índice `addons.xml.md5`.
- Se conservan los paquetes Beta anteriores en el repositorio Testing.
- No se modifica Stable ni se sobrescriben perfiles Kodi.
- **Sin validación runtime en tvOS**: el usuario probará primero Mac y Lenovo; la prueba en Apple TV deberá verificar disponibilidad real de SlyGuy, resolución de tráilers, imágenes y datos frescos del proveedor. Si el XMLTV remoto solo contiene programas históricos, el software no puede inventar programación y mostrará el estado de falta de cobertura.
- Las acciones de marcar progreso no se ejecutan automáticamente; requieren selección explícita del usuario.

### Prueba manual solicitada

En **Kodi Mac y Lenovo** actualizar los tres complementos desde AcTweeteR Testing y comprobar: tráilers automáticos y manuales (Inicio, Películas y Series), carátulas y sinopsis de episodios, contexto de progreso T2E03 (se marcan T1 y T2E01–03 sin tocar posteriores), entrada EXPANDIR al final de filas con más contenido y guía EPG tras completar una sincronización en reposo.

### Regresión

Véase `source/0.4.32/tests/test_priority_beta_20261104.py` para las comprobaciones nuevas. Los tests antiguos de Trakt que requieren un paquete `ACTWEETER_XSTREAM_LIVE_ZIP` deben ejecutarse apuntando al ZIP de esta Beta para evitar errores por paquete ausente.
