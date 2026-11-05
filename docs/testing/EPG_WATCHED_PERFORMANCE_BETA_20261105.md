# AcTweeteR Testing — EPG, vistos y rapidez (5 noviembre 2026)

## Paquetes

- Skin **1.2.41~beta4** (sobre Beta3): corrige la anchura de las etiquetas de programas de la guía y sus fondos. La cuadrícula de TV permanece nativa de Kodi.
- XStream Pro **1.1.2.40~beta2** (sobre Beta1): mejora la actualización de estados y la primera carga de los widgets.
- Service sigue en **0.4.98~beta1**, sin cambios. Trakt, Rivulet, IPTV Simple y Stable tampoco cambian.

## EPG

La auditoría de Kodi Master mostró PVR disponible, 1.151 canales visibles y 487 con programa actual asociado. En el XMLTV de origen hay 203.145 programas para 1.072 IDs; la lista M3U tiene 1.291 canales, de los que 737 tienen un ID con programación exacta y 554 no tienen un programa vinculable por ID.

Se corrigen **cuatro etiquetas con anchura 0** en los diseños de programa enfocado y no enfocado, y el ancho de sus fondos. La skin puede visualizar programas conocidos por Kodi; **esto no genera EPG para canales ausentes del XMLTV**. Los 554 canales sin correspondencia requieren mejorar la fuente XMLTV/M3U, no adivinar emisiones.

## Vistos y estados dinámicos

- Después de confirmar un marcado o desmarcado de película o episodio, XStream actualiza las propiedades de refresco de widgets existentes y programa un único refresco de contenedor dos segundos después, tras cerrarse el menú contextual.
- El progreso exacto de temporada también invalida vistas después de confirmarse. No hace cambios si el inventario es incompleto.
- Cuando un inventario de episodios completo registra **capítulos nuevos**, cambia la generación del widget para que el distintivo no dependa de reiniciar Kodi. Evita repetir la notificación si los episodios son los mismos.
- Nunca interrumpe una reproducción ni escribe datos de Trakt.

## Rendimiento

Las filas del proveedor de 19 elementos (actweeter_expand=1) se construyen con metadatos disponibles del proveedor y caché, pero sin bloquear la primera presentación por búsquedas o imágenes adicionales de TMDb. Conservan cartel, título y datos existentes. Las clasificaciones vigentes en caché pueden reutilizarse brevemente al vencer su TTL, hasta 24 horas, evitando una petición externa al entrar a Inicio. En las vistas completas de navegación, se conservan las consultas de enriquecimiento anteriores.

**No se afirma carga instantánea**: el rendimiento visual también depende de la red, caché y decodificación de imágenes de cada dispositivo. La Lenovo no está disponible por ADB y no hay medición real de tiempo de aparición.

## Verificación

- Builder desde ZIPs Beta publicados e inmutables, con lista cerrada de archivos modificables, dos reconstrucciones byte a byte idénticas, validación Python, XML y CRC.
- Pruebas del refresco de visto/no visto, inventario nuevo y sin cambios, evitación de recargas durante reproducción, primera carga sin metadatos remotos, conservación de metadatos en caché y navegación completa.
- La suite global y GitHub Actions deben quedar correctos antes de promover a Stable.
- Sin instalación automática en Kodi Master ni tablet y sin cambios en los perfiles.

## Comprobaciones en Lenovo

1. Actualizar Skin y XStream desde AcTweeteR Testing.
2. En TV, abrir la guía: los canales que sí tienen programación deben mostrar títulos; observar si los demás siguen vacíos.
3. En Películas y Series, marcar y desmarcar un título; comprobar el cambio de contexto, ojo y COMPLETA al volver a la fila, sin reiniciar.
4. Abrir una serie con episodios nuevos ya detectados y verificar los distintivos en Inicio y sección Series.
5. Comparar el tiempo de primera presentación de Inicio, Películas y Series en caliente/frío, sin desactivar extras de la ficha.

Repositorio de Testing:
https://actweeter.github.io/TwT-Actualizador/testing/bootstrap/repository.actweeter.testing-1.0.2.zip
