# AcTweeteR Stable — 5 de noviembre de 2026

## Versiones

- Skin **1.2.41** (promovida de Testing 1.2.41~beta4).
- XStream **1.1.2.41** (promovido de Testing 1.1.2.40~beta2).
- Service **0.4.98**: sin cambios.
- No se modifican Trakt, PVR IPTV Simple, Rivulet, IAGL ni los perfiles de Kodi.

## Mejoras incorporadas

1. La EPG visualiza las etiquetas de programas que Kodi sí conoce: las cuatro etiquetas tenían anchura cero y se corrige también el tamaño de sus fondos.
2. Al confirmar el marcado/desmarcado de películas o capítulos se invalidan las rutas de widgets y se programa una actualización del contenedor después del cierre del menú contextual. Se incluyen los estados de serie completa y el progreso de episodios.
3. Un cambio real en el inventario completo de episodios invalida los widgets para mostrar el distintivo de nuevos capítulos, sin bucles de refresco si nada cambió.
4. La primera carga de las filas estándar del proveedor reutiliza la información local y la caché, sin esperar búsquedas de TMDb ni logos adicionales; se mantiene el enriquecimiento en navegación completa.
5. Se mantiene el modo Táctil/Mando introducido en Beta y la navegación por mando no se modifica.

## Alcance y limitaciones

Esta promoción se publica a petición explícita del propietario. Las pruebas de código pasan, pero la nueva versión **no ha sido validada visualmente en la Lenovo ni en el Apple TV**.

La comprobación en Mac mostró un problema adicional, independiente del dibujo: para 554 de 1.291 entradas M3U no hay un ID con programación exacta en el XMLTV analizado. Los canales sin programación en la fuente seguirán mostrando la guía vacía; la promoción no crea emisiones ni datos EPG inexistentes.

No se garantiza una carga literalmente instantánea en dispositivos modestos. Los tiempos reales dependen del procesador, la caché de imágenes y la conectividad y no se han medido en Lenovo.

## Origen y seguridad

La promoción fue reconstruida dos veces byte a byte desde los ZIP publicados en Testing, con inventario cerrado de paquetes cambiados, comprobación de hashes de origen, CRC y XML, conservación de la Stable anterior, comprobación de dependencias y verificación del índice. Service, repositorios externos y configuraciones personales no se tocaron.

Para volver a una versión anterior sin modificar perfiles, se conservan los ZIP Stable 1.2.40 (skin) y 1.1.2.40 (XStream). Una reversión exige instalar esas versiones expresamente y desactivar temporalmente la actualización que volvería a subir a la versión actual.
