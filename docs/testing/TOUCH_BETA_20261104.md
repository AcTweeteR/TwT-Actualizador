# Kodi AcTweeteR — Beta táctil 1.2.41~beta1 (4 de noviembre de 2026)

## Qué se publica

Solo la skin pasa de 1.2.40~beta1 a 1.2.41~beta1 en AcTweeteR Testing. Service, XStream, Rivulet, Trakt, IPTV Simple y las fuentes EPG no reciben cambios. El canal Stable permanece intacto.

## Cómo se cambia entre táctil y mando

* Menú lateral de AcTweeteR: abrir el menú y pulsar Modo táctil / Modo mando. El selector es accesible en ambos modos y no depende de editar atajos de Skin Shortcuts.
* Ajustes de la skin → General → Modo de interacción: elegir explícitamente el modo. Mando es predeterminado (el ajuste táctil está desactivado).
* El valor se guarda en la configuración propia de la skin, no en controles globales de Kodi.

## Cambios táctiles

* Botones de tamaño táctil para Menú, Buscar e Inicio (en hubs), sin cubrir la zona de gestos de los widgets.
* Desplazamiento vertical explícito arriba/abajo de filas y anterior/siguiente en Spotlight, además del desplazamiento nativo de Kodi por gestos.
* Las carátulas de película y serie abren la ficha de información con un toque cuando el modo táctil está activado; el comportamiento del modo mando no cambia.
* Botón cerrar grande en la ficha de películas/series.
* Conserva el teclado y la búsqueda actuales, sin modificar scripts externos ni pantallas ajenas.

## Compilación y verificaciones

* Se genera un único ZIP skin desde la Stable 1.2.40 verificada con una lista explícita de archivos de interfaz y traducciones.
* El ZIP es byte-a-byte reproducible; los 174 XML de ventanas de la skin son correctos.
* Suite general: 841 correctas; 110 subpruebas correctas; 3 omitidas y 4 comprobaciones históricas excluidas.
* Reconstrucción del canal Testing: modifica solo el índice, su MD5 y la skin; paquetes de terceros bit-a-bit intactos.
* Beta anterior 1.2.40~beta1, Service y XStream continúan reconstruyéndose byte-a-byte a partir de sus fuentes fijadas.

## Límites de verificación

* No se ha podido probar sobre la Lenovo mediante ADB: no hay dispositivo conectado.
* No se ha probado la interacción real con tvOS ni la traducción de los gestos Android al evento de Kodi; la automatización solo confirma integridad, enlaces y lógica declarada.
* No se ha instalado nada en el Mac Master ni en la tablet. No se ha cambiado Stable.

## Pruebas manuales prioritarias

1. En Lenovo, instalar la skin Beta desde AcTweeteR Testing.
2. Con Modo mando, verificar que todo está como antes.
3. Activar Modo táctil desde el menú lateral. Desplazarse por Inicio, Películas y Series, abrir fichas, cerrar con × y cambiar de Spotlight con los controles › y ‹.
4. Probar scroll vertical de las filas con deslizamiento y botones arriba/abajo; comprobar que no se pierde la selección ni se activan vídeos accidentalmente.
5. Volver a Modo mando con el botón lateral o en Ajustes y comprobar que desaparece la interfaz táctil.

Instalador Testing:
https://actweeter.github.io/TwT-Actualizador/testing/bootstrap/repository.actweeter.testing-1.0.2.zip
