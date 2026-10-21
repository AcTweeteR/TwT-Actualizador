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

ESTADO=EN_CURSO
REMOTE_WRITES=NONE
MAC_SYNC_RUNTIME=NOT_TESTED
LENOVO=NOT_TOUCHED
BETA_PUBLICATION=NOT_STARTED
STABLE_UNCHANGED=YES
