# AcTweeteR 0.4.27 — hotfix de controles de ficha

Esta actualización corrige la regresión introducida por el prototipo de
interacción de 0.4.26. En las variantes `BingieAltInfo` y `BingieInfo`, los
controles Play (80), Resume (90) y Trailer (54) vuelven a ser los
`radiobutton` nativos anteriores. Se retiran los wrappers de grupo y botones
push experimentales, la capa de iconos auxiliar y la opción temporal de
trazado. Las acciones originales, condiciones, IDs y navegación se conservan.

La regresión de botones fue reportada por el usuario tanto en Apple TV como en
Android después del cambio radio→button. El hotfix revierte ese cambio. No se
ha instalado en dispositivos y la recuperación necesita validación runtime
del usuario. No se afirma que el tacto general de Android esté corregido.

Sin cambios en scroll, foco/hover del ratón, `input.enablemouse`, XStream,
Trakt, PVR, credenciales, favoritos, historial, progreso ni datos personales.
La versión 0.4.26 se conserva; no es la versión recomendada debido a la
regresión conocida. La 0.4.25 continúa disponible para rollback.

Validación automatizada: 590 tests PASS, incluidos los contratos de controles
y acciones restauradas. Instalación, mando, tacto, reproducción de tráilers y
actualización en dispositivos: pendientes de comprobación runtime.
