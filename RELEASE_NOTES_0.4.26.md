# AcTweeteR 0.4.26 — versión de pruebas de interacción

Esta release oficial de pruebas permite comparar, en las fichas, los controles
push `button` de Play, Resume y Trailer con los controles anteriores. Conserva
sus IDs, acciones y condiciones; el cambio es una hipótesis experimental, no
una solución táctil confirmada.

El servicio añade instrumentación optativa, desactivada por defecto. No registra
identidad del contenido, rutas, URLs, datos IPTV, contraseñas ni tokens.

No se modifican scroll ni foco del ratón. No se ha validado runtime en Android,
tvOS u otras plataformas. El propietario debe probar la release en su Android:

1. En una ficha, pulsar Play y Resume con tacto.
2. En otra ficha, pulsar Trailer con tacto.
3. Repetir con mando y comprobar que la navegación no regresa.
4. Informar por separado del scroll y del foco del ratón; no son cambios de
   esta versión.

La actualización Kodi es in situ desde 0.4.25; no requiere limpiar el perfil.
Los ZIP 0.4.25 permanecen disponibles para rollback. Kodi Master, Android y
Apple TV no fueron modificados por esta publicación.

Verificación: 590 pruebas automatizadas PASS, contando las cuatro pruebas de
servidor local ejecutadas por separado tras conceder loopback. No equivale a
validación runtime de tacto, mando, teclado o reproducción en dispositivos.

La incidencia de cierre se clasifica `CLOSED_NOT_REPRODUCIBLE`; no se conoce ni
se afirma una corrección técnica. Reabrir si vuelve a aparecer.
