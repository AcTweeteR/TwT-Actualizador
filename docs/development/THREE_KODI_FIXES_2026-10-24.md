# Auditoría y correcciones integrales — 2026-10-24

## Resultado

Estado: **PARTIAL — código y paquetes privados preparados; falta validación runtime en dispositivos**.

Trabajo realizado en `codex/fix-series-tags-xstream-compat-tmdb-onboarding-2026-10-23`, derivada del estado consolidado de Trakt `84677c6`. Los cambios existentes de Trakt se conservaron. No se modificaron instalaciones Kodi, Stable, Lenovo ni Apple TV; no se publicó ni se hizo push.

## 1. NUEVA SERIE / NUEVOS CAPÍTULOS

### Causa y límites

El historial de novedades era local por perfil, se inicializaba sin usar fechas del proveedor y recortaba el almacén a 50 eventos. Dos instalaciones con distinta fecha de primera importación podían, por tanto, mostrar etiquetas diferentes; además, muchas novedades simultáneas podían expulsar eventos aún vigentes.

Se comprobó el flujo de extremo a extremo: XStream escribe `ListItem.Property(XStream.ChangeStatus)` y la skin lo consume en las vistas Poster, Landscape y Square. Sus tres XML ya contenían los overlays; el defecto no era una condición visual faltante, sino la captura y persistencia del historial.

### Solución

`third_party/xstream/series_changes.py` es ahora la fuente reproducible y hash-lockeada que el constructor instala en el ZIP final. El estado es versionado, perfilado y separado por huella SHA-256 de proveedor; se guarda mediante temporal, `fsync` y `os.replace`. El almacén conserva eventos por ventana de 30 días, sin un tope arbitrario de cantidad; el límite de filas de la vista sigue siendo una decisión de presentación.

La primera importación no etiqueta todo el catálogo: solo etiqueta adiciones con `added` reciente y válido. Luego compara IDs de catálogos completos. Para episodios, compara inventarios completos y acepta fechas `added` recientes; si no existen fechas, usa la diferencia entre inventarios persistidos. Respuestas explícitamente parciales, vacías o malformadas no sustituyen una instantánea válida. Los IDs conocidos se conservan frente a desapariciones temporales y reconstrucciones. Un cambio de proveedor establece una línea base independiente.

### Límite de paridad entre dispositivos

Si Xtream proporciona un `added` fiable, una instalación nueva puede calcular la misma etiqueta dentro de la ventana de 30 días sin contactar otro dispositivo. Sin fecha fiable, una instalación que nunca vio la instantánea anterior no puede distinguir una adición reciente de contenido preexistente. La comparación local detecta cambios posteriores, pero no puede garantizar paridad histórica con otro dispositivo sin un ledger compartido. No se añadió un servidor central obligatorio. Además, un listado truncado pero sintácticamente válido y sin indicador de completitud no puede distinguirse de uno completo mediante la interfaz actual de XStream.

## 2. COMPATIBILIDAD DE VERSIONES XSTREAM

Se eliminó `SUPPORTED_XSTREAM_VERSIONS`. El bloqueo provenía de una allowlist que envejecía con cada Beta, aunque XStream mantuviera el contrato usado por AcTweeteR.

Ahora se aplica una versión mínima con comparación numérica y orden `alpha < beta < rc < estable`, y se inspecciona el complemento instalado: identidad y versión del manifiesto, dependencias mínimas (`xbmc.python`, `script.module.requests`, `pvr.iptvsimple`), tipos de ajustes Xtream y rutas/callbacks de actualización, catálogo, metadatos y cambios de series. El asistente comunica los códigos de capacidades que faltan. Una versión posterior se acepta solo si satisface el contrato; el canal y la dependencia del paquete continúan controlando qué versión se ofrece.

## 3. TMDb OPCIONAL Y ASISTENTE PRINCIPAL

El estado principal del asistente (`first_run.py`) y el marcador opcional de TMDb (`tmdb_onboarding.json`) permanecen separados. El flujo principal ya persiste pasos y reanudación; no se debe interpretar `prompted` aislado como prueba de instalación completa.

La ruta principal llamaba a `offer_once()` directamente, por lo que errores de interfaz o de persistencia del marcador opcional podían escapar antes de preparar componentes obligatorios. La decisión normal «Omitir» ya devolvía `SKIPPED`; el registro `FIRST_RUN_WIZARD ... reason=prompted`, por sí solo, no demuestra que omitir TMDb fuera la única causa del cierre observado. Se añadió una frontera recuperable: el marcador `OFFERED` es previo al diálogo, los fallos se guardan como `FAILED_RECOVERABLE`, un proceso nuevo puede reanudar una oferta interrumpida y el llamador registra el resultado y continúa el onboarding obligatorio. Omitir no cambia ni completa el estado principal; TMDb puede configurarse después desde Ajustes.

## Pruebas y comprobaciones

- Suite completa: **583 tests, 0 fallos, 0 omitidos**. Se proporcionaron los ZIP exactos mediante `ACTWEETER_XSTREAM_LIVE_ZIP`, `ACTWEETER_XSTREAM_TEST_ZIP` y `ACTWEETER_XSTREAM_UPSTREAM_ZIP`.
- Las pruebas que fallaban anteriormente quedan cubiertas: hashes del parche XStream fijados; `test_native_snapshot_transport_never_refreshes_or_posts` ejecutado contra el ZIP candidato y confirma solo `GET`, sin refresh ni `POST`.
- El contrato del instalador también se ejecutó contra el ZIP XStream exacto; versión candidata y capacidades pasaron.
- Se ejecutaron clases reales de almacenamiento XStream desde el ZIP: instancias simultáneas, merge/persistencia, progreso y reproducción del lost update upstream. No es una prueba dentro del proceso de Kodi.
- Novedades: primera importación, fechas, dos perfiles-dispositivo sintéticos, >50 eventos, inventario episódico incompleto, reconstrucción, cambio de proveedor, migración legacy, corrupción, reinicio de módulo, deduplicación y 5.000 series; el camino throttled no vuelve a materializar el listado.
- TMDb: omisión y estado core inalterado, marcador legacy, interrupción/reanudación por proceso, credencial existente y aislamiento de errores.
- Validación estática: AST de **160** archivos Python y parseo XML de **199** archivos correctos; `git diff --check` correcto.
- El constructor Beta privado verificó ZIP/CRC y produjo un índice de prueba bajo `/private/tmp`; Stable no se alteró.

## Candidatos privados reproducibles

El XStream upstream fijado tuvo SHA-256 `915f45708670d07e789bb73b7390a7b5cf30175f818ef5da8ea18c9f13f537fe`.

| Artefacto | Versión | SHA-256 |
|---|---:|---|
| service.actweeter | 0.4.69 | `9f09bc879b460c78e38ab576b275fc629c83c5c8b3efc7c063afd9efaa6a8adc` |
| plugin.video.xstream-pro | 1.1.2.28~beta9 | `c1723e99ef136e1d7f4017b8936a2aa4eea6a87099702088994ee3460377ed89` |
| skin.actweeter (sin cambios funcionales en esta misión) | 1.2.32~beta1 | `3e7cf74ad59cd7d9b3ee8be9b399f4974816890a2f2dd31ed9cfea3e9121d08b` |
| índice Testing local de prueba | — | `7fd65db26ffd533921f55307bf5b46314389f39f74194356ae7eec5d021b31f6` |

Los ZIP Service y XStream se reconstruyeron dos veces con los mismos hashes. El índice local declara repository.testing 1.0.2, Service 0.4.69, skin 1.2.32~beta1 y XStream 1.1.2.28~beta9; MD5 y CRC se verificaron. Artefactos finales: `/private/tmp/actweeter-candidates-final-v2/` (Service), `/private/tmp/actweeter-candidates-final-v3/` (XStream) y `/private/tmp/actweeter-beta-private-20261024-final-v3/` (índice/feed privado). Estos no son paquetes publicados.

## Git y despliegue

- Rama: `codex/fix-series-tags-xstream-compat-tmdb-onboarding-2026-10-23`.
- Base: `84677c6` (incluye el historial consolidado de Trakt).
- No se modificaron tokens, credenciales, estado Trakt, perfiles ni complementos instalados.
- No se publicaron paquetes ni se cambió el feed Testing/Stable.
- La prueba real en interfaz/arranque Kodi Mac y en Lenovo/Apple TV no se hizo; instalar o cambiar instalaciones estaba expresamente prohibido.
- XStream conserva licencia upstream CC BY-NC 4.0; este trabajo no concede derechos adicionales de redistribución.

Conclusión: el candidato es reproducible y está listo para revisión/QA Beta, pero no puede certificarse como corrección runtime ni como paridad total entre dispositivos hasta validarlo en Mac/Lenovo y decidir si la falta de fechas fiables requiere un ledger compartido.
