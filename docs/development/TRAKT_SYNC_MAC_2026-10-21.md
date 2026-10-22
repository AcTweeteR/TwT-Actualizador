# Trakt: arquitectura y ejecución Mac primero

## Alcance y base

- Base oficial `df96268` (main consultado el 21-10-2026).
- Rama aislada `codex/trakt-sync-mac-2026-10-21`.
- Master observado: `/Applications/Kodi.app`, perfil estándar; servicio 0.4.53,
  skin 1.2.32~beta1, XStream 1.1.2.19, script.trakt 3.9.0.
- Suite base: 310 pruebas correctas. No cambios en Lenovo, Apple TV o Stable.
- Las pruebas de escritura remota necesitan autorización específica y una
  exportación verificada previa. No se ejecutan por abrir una ficha o un widget.

## Funciones reutilizables y responsabilidades

| Componente | Código real | Reutilización / límite |
|---|---|---|
| script.trakt 3.9.0 | `resources/lib/script.py`, `service.py`, `scrobbler.py` | Responsable único del scrobbling actual. Exporta acciones de autorización y biblioteca, no una sesión OAuth pública para otros addons |
| XStream | `resources/lib/trakt.py` | Transporte OAuth propio, renovación, listas, playback y recomendaciones; no copiar tokens de script.trakt ni sus claves internas |
| Puente de reproducción | `trakt_playback_metadata.py`, `_monitor_playback` en addon.py | Ya identifica películas y episodios para script.trakt. No crear otro listener que envíe los mismos eventos |
| Estados XStream | `history.py`: WatchedMovies, WatchedEpisodes, ResumePoints | Se reutilizan en la proyección posterior. Hoy son IDs del proveedor, sin identidad universal ni fecha de modificación fiable para todos los campos |
| Recomendaciones | parche `actweeter-trakt-recommendations.patch`, tmdb_routes.py | Filtrado exacto por TMDb en catálogo disponible; no resolver por título ni simular recomendaciones cuando no hay autorización |
| Servicio | `trakt_integration.py`, setup.py:1795–1899 | Coordina acciones oficiales; su estado AUTHORIZATION_UNVERIFIED no demuestra cuenta conectada ni sincronización |

## Diseño seleccionado

1. Auditar sesión mediante rutas nativas; nunca leer tokens privados de
   script.trakt. La autorización de ese addon no implica autorización de XStream.
2. Añadir un núcleo puro y comprobable al servicio para identidad universal,
   lectura paginada y plan conservador de importación. No ejecuta red por su
   cuenta, no recibe credenciales y no realiza POST/DELETE.
3. Película: namespace movie + IDs validados. Episodio: namespace episode +
   identidad de serie + temporada/episodio; nunca tratar TMDb de serie como ID
   de película/episodio. Una coincidencia contradictoria o ambigua no se aplica.
4. Snapshot universal separado de la caché proveedor, con perfil/cuenta
   explícitos, eventos vistos y porcentajes/fechas remotos. No contiene URLs IPTV.
   Se conserva lo no disponible y se puede reconstruir el vínculo al proveedor.
5. Primera importación: plan previo, sin borrar estados locales. Conflictos de
   fecha, falta de duración y estado local sin fecha se difieren, no se decide
   por el porcentaje mayor. Solo duración conocida permite convertir a segundos.
6. La cola de escritura debe reconciliar estados inciertos antes de reintentar.
   Un UUID local NO es una garantía de idempotencia del servidor Trakt.
7. UI y proyección al almacenamiento existente se integran después de verificar
   la sesión autorizada, el responsable del scrobbling y la exportación. No
   habilitar periódicos que escriban en datos existentes durante la auditoría.

## Riesgos y límites oficiales

- El contrato oficial de `/sync/history` advierte que el cliente es responsable
  de evitar duplicados. Ante un timeout después de POST no reintentar a ciegas.
- `/sync/playback` describe porcentaje y `paused_at`, no segundos. No es una
  garantía de que toda reproducción pausada de cualquier cliente esté presente.
- Una serie vista se importa como episodios explícitos; una fila de serie no
  autoriza marcar todas sus temporadas/episodios como vistos.
- La API cambia; paginación y payloads se validan. Un fallo o snapshot incompleto
  no debe interpretarse como colección vacía ni sustituir el último estado válido.
- Los stores de vistos de XStream no tienen timestamps de desmarcado: no hay una
  forma segura de inferir borrados remotos ni exportarlos automáticamente.
- OAuth XStream y script.trakt son independientes. El aislamiento por perfil
  necesita vinculación explícita de cuenta; no heredar una sesión global a otro.
- No se copia código GPL de script.trakt al parche CC BY-NC de XStream. El
  núcleo nuevo es implementación propia en el servicio GPL existente.

## Fuentes primarias consultadas

- [API Trakt](https://trakt.docs.apiary.io/).
- [OAuth oficial](https://github.com/trakt/api-help/blob/master/projects/developer/src/lib/guides/authentication-oauth.md).
- [Contratos sync](https://github.com/trakt/api-help/blob/master/projects/api/src/contracts/sync/index.ts).
- [Contratos recomendaciones](https://github.com/trakt/api-help/blob/master/projects/api/src/contracts/recommendations/index.ts).
- [Identidades script.trakt](https://github.com/razzeee/script.trakt/wiki/Providing-id%27s-to-facilitate-scrobbling).
- [Código script.trakt](https://github.com/razzeee/script.trakt).

## Plan de pruebas y gates

Identidades tipadas, especiales/temporada cero, IDs contradictorios, paginación
incompleta, cancelación y errores de red; importación conservadora sin borrados;
conflictos temporales; proveedor nuevo/ausente; recomendaciones exactas;
ausencia de secretos. Después: GET reales desde el contexto nativo autorizado,
exportación privada, consentimiento específico para escritura y prueba VOD
inequívoca. Lenovo y publicación Beta solo después de validación Mac.

## Resultado de este bloque

### Defecto nativo confirmado y corrección preparada

El Mac respondió por JSON-RPC TCP local (9090): Kodi 21.3, cero reproductores
activos antes de las pruebas. HTTP 8080 no está disponible; no se cambió ningún
servicio ni preferencia para habilitarlo.

`Files.GetDirectory` sobre `xstream_tmdb_trakt_menu` devolvió 11 entradas en
1,20–1,24 s. El resumen de las rutas muestra:

```
authorization_offered=false
account_configuration_offered=true
account_routes_present=false
```

La rama de `tmdb_routes.trakt_menu()` que produce ese resultado depende de
`trakt.auth_configured() == false`, no de un historial vacío. La función exige
client ID **y secreto**. El contrato oficial actual declara el secreto opcional
y desaconseja enviarlo desde aplicaciones de escritorio. Se preserva el OAuth
nativo de XStream: no se extraen ni copian tokens o claves de script.trakt.
El parche nuevo elimina ese requisito, deja de enviar el secreto y utiliza
`https://auth.trakt.tv` para Device Code, Device Token y renovación.
Esto confirma un bloqueo del acceso a funciones de cuenta, NO demuestra todavía
la sincronización ni que la aplicación OAuth acepte realmente la autorización.

Referencias adicionales verificadas:

- [Device OAuth y hostname oficial](https://github.com/trakt/api-help/blob/master/projects/api/src/contracts/oauth/index.ts).
- [Secreto opcional, no para escritorio](https://github.com/trakt/api-help/blob/master/projects/api/src/contracts/oauth/schema/request/clientSecretSchema.ts).
- [Kodi 21.3 JSON-RPC](https://github.com/xbmc/xbmc/blob/21.3-Omega/xbmc/interfaces/json-rpc/schema/methods.json).

### Código preparado, sin activar sincronización

- `resources/lib/trakt_sync.py` del servicio: identidades tipadas, índice de
  coincidencias verificadas por perfil, lectura paginada de vistos/historial/
  playback, vallado por actividad y cuenta, y plan conservador sin borrados.
  Conflictos o duración desconocida impiden sobrescribir progresos.
- `actweeter-trakt-device-auth.patch`: cambio localizado del cliente OAuth
  existente. El constructor verifica hash del parche y de los archivos finales.
- `tools/probe_trakt_mac.py`: diagnóstico por rutas nativas permitidas;
  imprime cantidades/estados, no títulos, URLs de reproducción ni tokens.
- Se diferencian las pruebas de paquetes **publicados** de la versión fuente
  **candidata**, sin modificar índices públicos ni reducir las comprobaciones
  de CRC, identidades, aislamiento o reproducibilidad.

El planificador NO está conectado a un temporizador ni a los stores personales.
No hay una importación aplicada, cola de envío funcional, UI de sincronización
completa ni sincronización bidireccional validada. Los widgets de recomendaciones
existentes se conservan; sus resultados de cuenta quedan NOT_TESTED.

### Pruebas y artefactos locales

| Comprobación | Resultado |
|---|---|
| Suite completa | PASS_AUTOMATED: 352 tests (310 de base + 31 de importación + 11 OAuth/diagnóstico) |
| Identidades/paginación/perfiles/progreso | PASS_AUTOMATED con API sintética, no cuenta personal |
| OAuth nativo parcheado | PASS_AUTOMATED: secreto no leído/enviado, host oficial, pending/errores, conservación ante rate limit |
| GET del menú XStream instalado en Mac | PASS_RUNTIME para diagnóstico; funciones de cuenta no expuestas |
| OAuth corregido en Mac | NOT_TESTED: modificación instalada rechazada por el control de permisos |
| Importación real / envío / reanudación / recomendaciones | NOT_TESTED; no confundir con las pruebas sintéticas |
| Reproducibilidad | PASS_AUTOMATED: dos reconstrucciones independientes idénticas por componente |
| Integridad de paquetes | CRC/AST/XML verificados; la comprobación inicial recorrió 225 miembros, 70 Python y 5 XML |
| Revisión de artefactos privados | Sin userdata, DB ni bytecode; sin claves privadas o tokens GitHub reconocibles por los patrones examinados. No equivale a detección universal de secretos |
| Stable/Testing públicos | Sin modificaciones en `repo/`, `docs/testing/` ni `testing/` |

Versiones propuestas, **no publicadas ni instaladas**:

| Paquete | SHA-256 |
|---|---|
| service.actweeter 0.4.54 | `86db4e571a9be54464146a669ac0e4615d63717ad81edbde4004483a1cabe5c7` |
| plugin.video.xstream-pro 1.1.2.20~beta1 | `650b46c5e58f1ea067f7f6de1f4bc7f701c5a062a9a52d7788341625e53729d6` |

Skin sin cambios. Servicio final local en
`/private/tmp/actweeter-trakt-final.KJwnUS/`; XStream en
`/private/tmp/actweeter-trakt-candidate.NwyZcq/`. Los primeros builds del servicio
son anteriores al refuerzo de aislamiento: NO son los artefactos finales de esta
tabla. Los constructores no permitieron sobrescribirlos; se usó otra carpeta.

### Protección de Master y bloqueo real

Se verificó que los dos módulos instalados coinciden con el ZIP oficial 1.1.2.19.
Antes del intento de cambio se respaldaron ambos y se verificaron con `cmp` y
SHA-256 en la carpeta privada de modo 0700:

`_local_recovery/trakt-mac-20261021.5Mj1Sz/` (fuera del worktree Git).

- Original `trakt.py`: `971103887851c84556a81e5776e84c995dbb29b4359a9f3aad33ff8e2d928403`.
- Original `tmdb_routes.py`: `5ed659bc75514908eaa6596dd979700021e9f06f4006c024a4bfbb92a487a478`.

El control de permisos rechazó aplicar el parche directamente a Master:
considera necesaria autorización explícita para modificar esos archivos de la
instalación activa. No se eludió el rechazo. Los SHA-256 posteriores siguen
siendo los originales. No hace falta restaurar: no se aplicó modificación.

Solo hubo navegación/consultas nativas, lectura de flags de scrobbling no
sensibles y backup de código. No se leyeron tokens privados de script.trakt,
ni se cambiaron ajustes, credenciales, perfiles, listas o historial.

### Continuación exacta

1. Obtener autorización explícita para aplicar a Master los dos módulos
   respaldados, sin cambiar settings ni tokens. No usar una vía alternativa
   para eludir la restricción del entorno.
2. Comprobar que el menú nativo ofrece autorización; realizar OAuth con el
   usuario. No confundir el diálogo cerrado con autorización correcta.
3. Verificar GET autenticados y preparar exportación remota privada íntegra.
4. Con el resultado real, integrar proyección aditiva, persistencia y UI;
   resolver propiedad única del scrobbling y reintentos de resultados inciertos.
5. Solicitar permiso específico antes de pruebas que escriban historial remoto.
6. Validar recomendaciones/progreso/vistos en Mac. Solo después preparar el
   despliegue Testing a Lenovo solicitado por el usuario.

Commits de base funcional: `128907e` (planificador), `6e58285` (cuenta/perfil).
Parche OAuth, constructor, metadatos, pruebas y probe: `cc4bb98`.
Los commits permanecen locales; no se ha abierto PR ni actualizado ningún feed.

ESTADO=PARTIAL
REMOTE_WRITES=NONE
MAC_SYNC_RUNTIME=NOT_TESTED
LENOVO=NOT_TOUCHED
BETA_PUBLICATION=NOT_STARTED
STABLE_UNCHANGED=YES

## Continuación: parche Mac autorizado y OAuth nativo abierto

El usuario autorizó expresamente modificar los dos módulos instalados, con copia
verificable previa. Se comprobó que no había reproductores activos. Nueva copia
privada (0700), fuera de Git:
`_local_recovery/trakt-mac-20261021.pj6vve/`.
Ambos originales coinciden mediante `cmp` y SHA-256 con los hashes anteriores.

El parche versionado se aplicó a Master sin modificar manifiestos, configuración
ni tokens. Los hashes instalados coinciden con los módulos del candidato:

- `trakt.py`: `529cc01399903c0ebbbd8fa265669ac4c1926740f9591a8e80730a1c90f7d664`.
- `tmdb_routes.py`: `e435f7cdd8d35658f60c20640e8a978427c8d57cdf062228b411052f34135376`.

Esto es un overlay de desarrollo de dos módulos sobre XStream 1.1.2.19, no una
instalación completa de 1.1.2.20~beta1. El parche y su constructor ya están
versionados en `cc4bb98`.

Verificación runtime mediante ruta nativa: 11 entradas, autorización ofrecida,
sin la antigua exigencia de client secret y sin rutas de cuenta todavía.
Desde la interfaz nativa XStream → Trakt → Autorizar Trakt se abrió el diálogo
de dispositivo y Trakt devolvió URL oficial de activación y código de usuario.
No se conserva ese código temporal en este informe. Se solicitó al usuario
completar personalmente el consentimiento. La autorización final y las consultas
autenticadas siguen pendientes; obtener un código no acredita una sesión válida.

Suite completa repetida: **352 tests, OK, 16.844 s**. No se copió ni leyó el token
de script.trakt. No se enviaron escrituras de historial/progreso, no se cambió
Stable ni se desplegó en Lenovo. Próximo paso: verificar el resultado OAuth y
ejecutar consultas autenticadas de lectura; después preparar exportación privada
verificada antes de solicitar autorización específica para cualquier escritura.
