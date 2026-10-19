# Kodi AcTweeteR — roadmap de control de actualizaciones

Estado: **planificado / pendiente de implementación integral**. Rama de trabajo: `codex/master-integration-2026-10-18`. No confundir protección básica ya instalada con un gestor completo de compatibilidad.

## Política vigente y límites

- **Kodi Master, verificado el 19-10-2026:** `general.addonupdates=1` (notificar sin instalar), leído después de reiniciar Kodi. `general.addonnotifications=true`. No se han deshabilitado las actualizaciones manuales.
- **Protección integrada en el servicio:** `service.actweeter` ejecuta `ensure_notify_only()` en cada arranque, utiliza JSON-RPC de Kodi, comprueba el resultado y registra `ADDON_UPDATE_POLICY`; no interrumpe la reproducción si Kodi rechaza el ajuste. Pruebas automatizadas: cuatro casos de configuración, idempotencia y errores; la suite total alcanzó **207 PASS**.
- **Límite de instalación:** instalar solamente `repository.actweeter` **no ejecuta código** ni puede imponer ajustes globales de Kodi. La política se aplica una vez instalado y arrancado `service.actweeter`. Una persona puede cambiar manualmente el ajuste durante la sesión; el servicio lo recupera en el siguiente arranque. No afirmar protección inmediata ni bloqueo absoluto.
- **Alcance:** la preferencia de Kodi afecta a **todos** los addons, no solo a los desarrollados por AcTweeteR. Evitar modificar fuentes/repositorios o borrar actualizaciones existentes.
- **Despliegue:** protección instalada en Kodi Master con copia de seguridad previa; confirmación en el log `ADDON_UPDATE_POLICY status=ALREADY_PROTECTED`. Código fusionado solo en la rama de integración, **no distribuido todavía en una release nueva**.

## Hoja de ruta priorizada

| Prioridad | Entrega | Criterio de aceptación |
| --- | --- | --- |
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
