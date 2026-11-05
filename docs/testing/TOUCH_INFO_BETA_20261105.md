# AcTweeteR Testing — Touch refinement Beta 1.2.41~beta2 (5 noviembre 2026)

## Objetivo y alcance

La anterior Beta1 dejaba fuera del alcance táctil gran parte de los botones
de las fichas de películas/series, cuyas acciones viven dentro de controles
de grouplist optimizados para mando. Solo se modifica **skin.actweeter**.

## Cambios

1. Fichas de películas y series en ambos diseños (BingieInfo / BingieAltInfo):
   barra inferior con Reproducir, Continuar, Episodios, Tráiler, Todas las acciones
   y Cerrar, según disponibilidad de cada elemento.
2. Panel Todas las acciones: acceso con botones grandes a 32 acciones originales,
   incluyendo reproducir desde el principio, otras opciones de tráilers,
   reparto, similares, información ampliada, listas, Trakt, arte y actualizar.
   Los eventos se envían a sus botones originales mediante SendClick(id);
   **no se sustituyen sus rutas, plugins ni condiciones**.
3. Panel táctil desplazable con barra lateral y acciones subir/bajar; al pulsar
   una acción se cierra el panel. No bloquea el modo mando.
4. MyVideoNav: botones táctiles Volver, Ficha, Opciones y paginación para las
   vistas originales de biblioteca, temporadas y episodios.
5. DialogTextViewer: botones de cerrar, subir y bajar la sinopsis extensa.
6. Inicio: subir/bajar widgets a través de su scrollbar nativo (control 317).
7. Estado táctil persistente y voluntario, desactivado por defecto; retorno a
   modo mando disponible desde menú lateral y ajustes.

## Garantías automatizadas

- Los controles *originales* de DialogVideoInfo, DialogTextViewer y MyVideoNav
  coinciden estructuralmente con la Beta1 al retirar únicamente el añadido táctil.
- La fuente original de acciones de ficha IncludesDialogVideoInfo.xml es
  byte por byte idéntica a la de Beta1.
- El paquete Beta1 antiguo sigue siendo reconstruible byte a byte desde su
  commit inmutable 9e79068.
- La Beta2 se construye desde Beta1 con lista blanca explícita de solo skin;
  la compilación da el mismo ZIP en ejecuciones repetidas.
- Todos los XML de skin son válidos, cadenas españolas e inglesas sin duplicados.
- Suite general: 852 pruebas correctas, 110 subpruebas, 0 fallos,
  3 omitidas, 4 comprobaciones históricas Stable excluidas deliberadamente.
- Stable, Service, XStream, Rivulet y otros complementos permanecen idénticos.

## Limitaciones y prueba funcional pendiente

La tablet Lenovo no aparece conectada mediante ADB desde el Mac.
La validación estática no garantiza que Kodi Android procese todos los clics
táctiles de las mismas maneras que Kodi macOS; debe probarse en pantalla.
Si alguna acción no responde, recoger nombre, pantalla y posición del botón
para validar la ruta SendClick en la instalación.

## Prueba manual recomendada

1. Actualizar solo la skin desde AcTweeteR Testing; verificar version 1.2.41~beta2.
2. En modo mando, comprobar que la pantalla anterior funciona igual.
3. Activar modo táctil. Abrir ficha desde catálogo/biblioteca fuera de widgets.
4. Probar Reproducir, Tráiler, Episodios, panel Todas las acciones,
   desplazamiento, Reparto, Similares, Mi lista, cerrar.
5. Abrir una sinopsis larga y desplazarse mediante flechas; probar temporadas,
   episodios, opciones contextuales y retorno a Inicio.
6. Cambiar a Mando y confirmar que se ocultan todos los controles táctiles.

Instalador:
https://actweeter.github.io/TwT-Actualizador/testing/bootstrap/repository.actweeter.testing-1.0.2.zip
