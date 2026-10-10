# Incidente de primer arranque — AcTweeteR 1.2.2

La revisión de fuente encontró que Home mandaba el foco inicial y la navegación
lateral al contenedor de widgets incluso si este tenía cero filas. En una
instalación sin widgets configurados, ese destino no contiene un elemento al
que Kodi pueda asignar foco; el fondo base es negro y la superficie podía quedar
sin contenido funcional. La corrección conserva el menú accesible y añade un
estado vacío con arte local, instrucciones y un botón direccional para abrir la
configuración inicial.

El asistente también persistía el estado “ya preguntado” antes de completar
una ejecución aceptada. Ahora una respuesta explícita «Ahora no» difiere el
asistente, mientras que una ejecución iniciada e incompleta se vuelve a ofrecer;
los estados incompletos ambiguos de la versión anterior se migran una vez.
La propiedad de reproducción de la intro se establece antes de activar su
diálogo para impedir que el foco de Home retire prematuramente la máscara.

La causa es coherente y demostrada en el código fuente; los reportes de Apple TV
y Google TV no incluían logs del dispositivo. Por ello esta publicación no
declara reproducido ni validado el fallo en tvOS/Android TV. Las pruebas
automatizadas cubren las condiciones estructurales y de persistencia, no la
composición visual real de esos dispositivos.

Para diagnosticar un caso persistente, adjuntar un extracto de `kodi.log` que
incluya `FIRST_RUN_FLOW`, `FIRST_RUN_WIZARD`, `INTRO_SESSION_GUARD`,
`INTRO_PLAYBACK_STARTED`, `INTRO_PLAYBACK_TERMINAL` y errores de carga de Home.
Redactar antes nombres de usuario, tokens, cookies, contraseñas y URLs privadas.
