# AcTweeteR 0.4.30 — migración de interfaz al actualizar

Esta actualización corrige un hueco en perfiles existentes: la migración de
Skin Shortcuts dependía del asistente inicial, que no vuelve a ejecutarse tras
reclamar su sesión dentro del proceso Kodi. El servicio detecta una migración
de layout pendiente incluso en ese caso y solicita la regeneración nativa.

El servicio 0.4.30 incrementa la versión de layout a v10. La preparación crea
un backup antes de escribir y conserva DATA personalizados si no hay
consentimiento. El resultado se declara verificado solo tras revisar la salida
generada por Skin Shortcuts. Los intentos fallidos/aplazados no crean un bucle
en cada refresco de Home y pueden reintentarse con la acción de reparación.

## Verificación

- Las pruebas de migración cubren layout anterior verificado, generación
  pendiente y estado ausente/malformado. Son automatizadas, no Kodi runtime.
- No se modifica skin, XStream, preferencias IPTV, tokens, progreso, favoritos
  ni los controles radiobutton.
- La regeneración real en Lenovo debe validarse tras la actualización oficial;
  no se declara corregido el tacto ni la reproducción de tráilers.

La candidata está en una rama privada hasta finalizar empaquetado y
validación. 0.4.29 y 0.4.28 permanecen disponibles para rollback; no se afirma
que 0.4.30 esté publicada ni validada en runtime.
