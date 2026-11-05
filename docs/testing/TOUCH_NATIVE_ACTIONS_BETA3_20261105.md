# AcTweeteR Testing — Beta 1.2.41~beta3 (5 noviembre 2026)

## Diagnóstico y solución

Se localizaron dos errores concretos en Beta2:

1. Los botones de las fichas usaban SendClick(ID). En Kodi esta función
   envía un mensaje GUI a una ventana; eso no equivale a ejecutar los
   onclick de un botón nativo anidado en un diálogo modal. Los 32
   accesos del panel táctil y sus seis accesos directos ahora ejecutan
   las acciones condicionales originales en cada diseño BingieInfo y
   BingieAltInfo, sin cambiar esos controles originales.
2. La barra de navegación de la biblioteca usaba SetFocus(5000).
   ID 5000 es un grupo contenedor sin selección de películas. Ficha,
   Opciones y la navegación ahora recuperan el foco del control visible
   de la vista nativa (IDs 50/51/52/525/527/etc.).

El panel Todas las acciones ahora utiliza una propiedad explícita de
Home para evitar fallos al cambiar entre el diálogo modal y su ventana
principal. Sus 32 opciones conservan la visibilidad/condiciones
originales y ofrecen paginación.

## Política de compatibilidad

* Solo cambia la skin, como Beta3 en el canal Testing.
* El modo mando conserva el mismo árbol de controles originales.
* No se cambia el servicio, XStream, Trakt, Rivulet, IPTV Simple, EPG
  ni ventanas de terceros.
* Los ZIP Beta1/Beta2 se mantienen reconstruibles bit a bit.
* El repositorio Stable no cambia.

## Pruebas

* 860 pruebas automatizadas correctas, 0 fallidas, 3 omitidas,
  4 pruebas históricas Stable excluidas, 110 subpruebas correctas.
* Incluidas 8 nuevas pruebas específicas que cotejan cada onclick
  original y su condición con la implementación táctil en ambos diseños.
* Integridad ZIP, XML y checksum del índice Testing correctos.
* Pendiente: validación visual y de toques reales en Android Lenovo,
  que no está conectada a ADB. La prueba automatizada no sustituye una
  pulsación real sobre la pantalla.

## Prueba funcional

En Lenovo actualizar solo la skin a 1.2.41~beta3 desde AcTweeteR Testing,
activar modo táctil, entrar en película y serie desde un catálogo fuera
de widgets y comprobar Reproducir, Continuar, Episodios, Tráiler,
Todas las acciones, Más información/Similares, y cerrar. Comprobar
también Ficha, Opciones y scroll en biblioteca/temporadas/episodios.

Instalador Testing:
https://actweeter.github.io/TwT-Actualizador/testing/bootstrap/repository.actweeter.testing-1.0.2.zip
