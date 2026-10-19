# Kodi AcTweeteR — roadmap de control de actualizaciones

Estado: **planificado / pendiente de implementación integral**. **Requisito del propietario (19-10-2026): actualizaciones automáticas para releases propias publicadas y verificadas por AcTweeteR; actualizaciones externas no automáticas.** Rama de trabajo: `codex/master-integration-2026-10-18`. No confundir protección básica ya instalada con un gestor completo de compatibilidad.

## Política vigente y límites

- **Kodi Master, verificado el 19-10-2026:** `general.addonupdates=1` (notificar sin instalar), leído después de reiniciar Kodi. `general.addonnotifications=true`. No se han deshabilitado las actualizaciones manuales.
- **Protección integrada en el servicio:** `service.actweeter` ejecuta `ensure_notify_only()` en cada arranque, utiliza JSON-RPC de Kodi, comprueba el resultado y registra `ADDON_UPDATE_POLICY`; no interrumpe la reproducción si Kodi rechaza el ajuste. Pruebas automatizadas: cuatro casos de configuración, idempotencia y errores; la suite total alcanzó **207 PASS**.
- **Límite de instalación:** instalar solamente `repository.actweeter` **no ejecuta código** ni puede imponer ajustes globales de Kodi. La política se aplica una vez instalado y arrancado `service.actweeter`. Una persona puede cambiar manualmente el ajuste durante la sesión; el servicio lo recupera en el siguiente arranque. No afirmar protección inmediata ni bloqueo absoluto.
- **Alcance:** la preferencia de Kodi afecta a **todos** los addons, no solo a los desarrollados por AcTweeteR. Evitar modificar fuentes/repositorios o borrar actualizaciones existentes.
- **Despliegue:** protección instalada en Kodi Master con copia de seguridad previa; confirmación en el log `ADDON_UPDATE_POLICY status=ALREADY_PROTECTED`. Código fusionado solo en la rama de integración, **no distribuido todavía en una release nueva**.

## Modelo de actualización selectiva (requisito obligatorio)

**Comportamiento final requerido:** cuando se publique una versión propia de AcTweeteR que haya superado nuestras pruebas, los dispositivos instalados deben descubrirla, verificarla e instalarla automáticamente, sin pedir al usuario que actualice manualmente. Los complementos ajenos no deben actualizarse automáticamente. Una publicación en el canal de desarrollo o una compilación sin aprobación **no autoriza** el despliegue.

- **Fuente de confianza:** manifiesto de releases **propias** aprobado y publicado en nuestro canal estable, con ID de addon, versión, hash SHA-256, plataforma/arquitectura, dependencias y estado de validación. Nunca confiar solo en el nombre del repositorio o en una versión superior.
- **Lista de permisos estricta:** inicialmente `service.actweeter`, `skin.actweeter` y `repository.actweeter`; cualquier paquete XStream parcheado u otro componente se añade solo si es un artefacto **nuestro** fijado explícitamente en el manifiesto y ha superado QA. No permitir automáticamente `slyguy.trailers`, Skin Shortcuts, PVR IPTV Simple ni otros terceros.
- **Aislamiento de fuentes:** el XML de `repository.actweeter` incorpora feeds externos Matke y SlyGuy; por tanto, «viene de nuestro repo» **no demuestra** que el paquete sea nuestro. El actualizador debe usar un manifiesto propio firmado/verificado, no todos los addons que anuncie ese repositorio.
- **Configuración Kodi:** conservar por ahora `general.addonupdates=1` para impedir la actualización indiscriminada. Kodi no ofrece un ajuste nativo de «actualizar automáticamente solo este repositorio» mientras otros repositorios quedan en modo manual. Se necesita un **actualizador selectivo dentro del servicio** o un diseño alternativo validado de reglas individuales; no activar `general.addonupdates=0` globalmente como solución rápida.
- **Seguridad:** verificar autenticidad, hash y compatibilidad, realizar backup, instalar de forma controlada con API oficial si es viable, confirmar salud y restaurar si falla. No editar directamente `Addons33.db` ni descargar/ejecutar código de una fuente no aprobada. Evitar actualizar el servicio mientras está ejecutando la transacción; recuperación después de reinicio.
- **Experiencia:** automática para releases propias aprobadas, con notificación de versión instalada y de cualquier fallo; terceros siguen notificándose y requieren autorización manual. Permitir pausar actualizaciones propias durante una incidencia y desplegar por fases.
- **Primer arranque:** el servicio debe configurar la política segura e iniciar el control selectivo cuando esté instalado. La mera instalación del ZIP de repositorio no puede ejecutar el servicio; documentar este límite.

**Estado actual: NO IMPLEMENTADO.** La protección básica actual impide actualizaciones automáticas de todos los addons, incluidos los propios. No presentarla como el comportamiento final solicitado.

## Hoja de ruta priorizada

| Prioridad | Entrega | Criterio de aceptación |
| --- | --- | --- |
| P0 — autoactualización propia | Actualizador selectivo de releases AcTweeteR aprobadas y verificadas, sin actualizar terceros | Nueva release propia publicada: descarga y actualización automática; tercero con versión superior: solo aviso, nunca instalación automática |
| P0 — distribución | Incluir `addon_update_policy.py` y su importación en la siguiente versión publicada del servicio, con comprobación del ZIP y manifiesto | Instalación nueva de repositorio + servicio: `general.addonupdates=1` después del primer arranque, sin intervención del usuario; instalación solo del repositorio no se presenta como protegida |
| P0 — detección | Inventario local de addons críticos (XStream, skin, servicio, Skin Shortcuts, SlyGuy, PVR) con versión, origen y hashes de archivos propios modificados | Detectar reemplazos y cambios de versión sin leer ni exponer credenciales, historiales o contenido privado; falsos positivos documentados |
| P0 — alertas | Estado visible en AcTweeteR y aviso de integridad cuando una actualización manual o externa sobrescriba parches | Aviso preciso con addon, archivo/versión afectada y acción segura; nunca reinstalar ni sobrescribir automáticamente |
| P1 — compatibilidad | Matriz versionada de addons/dependencias y pruebas de contrato (búsqueda, series, IPTV, tráilers, widgets y Skin Shortcuts) | Una actualización incompatible queda marcada como pendiente de validación, sin prometer compatibilidad solo por número de versión |
| P1 — actualización supervisada | Comprobar versiones nuevas, changelog, fuente y procedencia; generar backup antes de proponer migración | Consentimiento explícito; hash, firma si existe, repositorio de origen y compatibilidad verificados antes de instalar |
| P1 — rollback | Copia de addons afectados y restauración atómica de código propio; preservar `userdata`, credenciales, ajustes y Skin Shortcuts generados | Prueba de actualización fallida y recuperación sin pérdida de datos, incluso si Kodi se interrumpe |
| P2 — multiplataforma | Adaptar la detección a macOS, Android y tvOS (permisos, firma y addons binarios) | Pruebas en cada dispositivo compatible, sin suponer que la instalación macOS se traslada a tvOS |
| P2 — interfaz | Pantalla de «Actualizaciones» con pendientes, riesgos, cambios, pruebas y acción manual | Distinguir claramente «disponible», «compatible», «bloqueada», «instalada» y «reversible» |

## Condiciones de seguridad y cierre

1. No habilitar actualizaciones automáticas por comodidad durante las pruebas ni cambiar el ajuste sin autorización explícita del propietario.
2. No aceptar automáticamente diálogos de consentimiento de personalización ni reescribir los atajos propios del usuario.
3. No instalar una versión upstream de XStream sobre nuestros parches sin un candidato reproducible y un plan de migración; la versión instalada en Master puede diferir del código de desarrollo.
4. Ejecutar pruebas aisladas y posteriormente validaciones de interfaz y reproducción en el dispositivo autorizado; no considerar PASS_RUNTIME una mera prueba unitaria.
5. Mantener inmutables los ZIP históricos y el canal estable; usar versión y manifiesto nuevos para cada publicación.
6. Una vez implementado, documentar cobertura, límites de protección y restauración real antes de marcar este proyecto como **COMPLETADO**.

## Referencias de implementación

- `source/0.4.32/addons/service.actweeter/resources/lib/addon_update_policy.py`
- `source/0.4.32/addons/service.actweeter/service.py`
- `source/0.4.32/tests/test_addon_update_policy.py`
- `docs/development/PHASE_1_5_EXECUTION.md`
