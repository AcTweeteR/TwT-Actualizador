# Trakt 2.0 — trabajo en curso

Base: Stable Beta37, commit 852f282. Rama local: codex/trakt-2-beta. No se ha publicado ni instalado una nueva Beta.

## Hallazgos comprobados

* El acceso lateral actual invoca `xstream_tmdb_trakt_menu`, que ofrece contenido, tendencias, listas y recomendaciones. La interfaz de Service `trakt_restore` contenía snapshot, sincronización puntual, consentimiento y vista previa, pero no tenía enlace desde ese menú.
* El ciclo automático existente importa mediante lecturas autenticadas, cola local y aplicación por XStream. El intervalo anterior era 300 segundos; ahora es 60, sujeto a consentimiento, pausa por reproducción y backoff. El cambio está probado localmente, no en Kodi.
* XStream contiene acciones directas de marcar/desmarcar y modificar watchlist, colección y favoritos mediante POST. `script.trakt` es responsable del scrobbling según los contratos existentes. La cola `trakt_outbox` y `trakt_explicit_actions` existen, pero no se ha demostrado que las acciones directas de XStream pasen por ella: no se declara idempotencia ni reconciliación bidireccional completa.
* La restauración expuesta actualmente prepara una vista previa; no equivale a aplicar la restauración. La ausencia de conexión no debe presentarse como un historial vacío.

## Cambios locales

* El menú empaquetado de XStream mantiene contenido Trakt y enlaza a la pantalla de sincronización incluso cuando las listas directas están deshabilitadas.
* La pantalla existente presenta datos persistidos disponibles del planificador y cuenta de lotes de importación globales, sin inferir éxito. Una cola global no se presenta como un recuento del perfil activo.
* El planificador tiene un intervalo mínimo de 60 segundos.
* Se añadieron pruebas del menú real empaquetado, errores del estado y separación de perfiles; los tests del intervalo comprueban el nuevo plazo.

## Comprobaciones

Pruebas específicas: 19 aprobadas y 6 subpruebas. Suite completa con ZIP locales de validación exactos: 758 aprobadas, 102 subpruebas, una omitida porque requiere canal Stable. Las construcciones locales de XStream y Service fueron reproducibles. Los ZIP son solo de prueba y conservan las versiones Beta37; no deben publicarse bajo esas versiones con contenido diferente. Stable local pasó el verificador y no hay cambios en los índices Stable ni Testing.

## Pendiente antes de publicar

Conectar y comprobar la propagación de acciones locales mediante una única cola segura, cubriendo desmarcados, avances y listas sin duplicar scrobbling; establecer una política verificable de conflictos e idempotencia; comprobar restauración y sincronización entre dispositivos; verificar autenticación y comportamiento visual real en Kodi Mac; versionar los paquetes antes de publicar, volver a ejecutar la suite y validar Testing. No se han probado escrituras reales de Trakt ni Android/tvOS.

## Continuación: integridad de la cola

Se corrigió una condición de carrera en `trakt_outbox.send`: si una lectura autenticada confirma una operación mientras el envío sigue en curso, una respuesta tardía no puede degradar su estado a incierto o pendiente. Dos procesos Python independientes compiten en una prueba real y solo uno ejecuta el POST simulado. La pantalla de operaciones explícitas ahora distingue una cola dañada de una cola vacía; se puede abrir desde el menú de restauración y se indica que abarca todos los perfiles.

Pruebas agrupadas de cola, reconciliación y menús: 31 aprobadas y 2 subpruebas. Suite completa contra ZIP locales de validación: 761 aprobadas, una omitida por requerir el canal Stable, 102 subpruebas. No hay escritura real en Trakt ni prueba runtime del cambio. La aplicación de restauración sigue limitada por el contrato existente de transacción con Kodi detenido; no se ha eludido esta protección. La captura de cambios locales y las escrituras directas de XStream todavía no están coordinadas con la cola. No se puede declarar la sincronización bidireccional completa ni publicar esta versión.

## Continuación: plan de restauración persistente

Se ha añadido un módulo de preparación y aplicación aislada de un plan de tres almacenes. Exige confirmación explícita del llamador, vincula cuenta y perfil, conserva huellas de los datos previsualizados y rechaza cambios durante la preparación o antes de la aplicación. Para aplicar reutiliza la transacción existente con copia recuperable y exige que el llamador acredite que Kodi está detenido. La preparación y la aplicación se han probado con datos sintéticos; el módulo aún no está conectado a la interfaz ni a un ejecutor capaz de verificar de forma independiente que Kodi está detenido. No se ha aplicado ninguna restauración real.

La inspección del ZIP XStream identifica llamadas explícitas desde `tmdb_routes.trakt_item_action_route` a `mark_watched`, `mark_unwatched`, `checkin_item` y `sync_item`; esta última cubre historial, watchlist, favoritos y colección. Siguen utilizando el transporte directo de XStream y no la cola persistente de Service. Las conciliaciones bidireccionales de avances, watchlist y listas personales también siguen incompletas. No se puede asegurar todavía que dos instalaciones no dupliquen eventos. No se ha publicado Beta ni alterado Stable.

### Límite de idempotencia entre dispositivos

La documentación oficial de Trakt indica que `/sync/history` no comprueba la unicidad por contenido y fecha: [Trakt API — Add to History](https://trakt.docs.apiary.io/reference/movies). La transacción SQLite local impide que dos procesos del mismo perfil reclamen simultáneamente un evento, pero no coordina dos instalaciones desconectadas. Una consulta GET previa tampoco es un bloqueo entre dispositivos: dos instalaciones pueden consultar antes de que cualquiera haga POST. La garantía solicitada requiere una autoridad de escritura compartida o un mecanismo remoto equivalente con exclusión/idempotencia verificable. Hasta disponer de ello no se debe declarar protegida la escritura multidispositivo ni publicar la integración como completa.

Suite final con los ZIP locales de validación: 765 pruebas aprobadas, 102 subpruebas y una omisión específica de Stable. Stable sigue verificada con SHA-256 de índice `3f0f219bad7736ada4c33386c1b7af00db2536d973b9e3d409a1f7550873c8cf`. No se instalaron paquetes en Kodi Master.

## Continuación: acciones coordinadas y planes confirmados

La ruta manual de XStream se ha conectado a la cola persistente de Service para vistos individuales, desmarcados, check-in, watchlist, colección y favoritos. Cada acción conserva cuenta, perfil y huella del proveedor; requiere identidad tipada, usa una única reclamación SQLite entre procesos y conserva como incierta una respuesta perdida. Los reintentos automáticos solo abarcan operaciones explícitas pendientes, dentro de la sincronización autorizada y con el ámbito verificado. Los check-ins no se reintentan automáticamente; se rechaza el check-in sin episodio específico o con reproducción activa. Las operaciones de visto se posponen durante la reproducción para reducir colisiones con el scrobbling de script.trakt. El desmarcado exige una confirmación que advierte que Trakt puede eliminar todo el historial del contenido.

La interfaz puede previsualizar, confirmar y guardar un plan persistente, listar planes y cancelarlos con confirmación. Se mantiene bloqueada la aplicación: aún no existe un ejecutor conectado que verifique realmente Kodi detenido y la cuenta activa. Esta limitación reemplaza cualquier impresión anterior de que el plan persistente ya estuviera conectado o de que fuera aplicable desde la interfaz.

Se ha recuperado el acceso a `Mis listas` mediante la ruta de lectura existente. La reconciliación completa de avances y listas, los eventos locales y la resolución de resultados inciertos de listas aún no están integrados; no se afirma que las acciones directas y el scrobbling estén coordinados entre dispositivos. Un reloj y un GET previo no constituyen exclusión distribuida, por lo que puede haber duplicados entre instalaciones.

Las construcciones locales de validación de XStream y Service fueron reproducibles; todavía llevan las versiones Beta existentes y no deben publicarse. Suite con ZIP locales: 784 pruebas aprobadas, 102 subpruebas, una omitida para canal Stable. Las pruebas usan datos simulados; no se escribieron datos de Trakt reales ni se instaló esta candidata en Kodi. Stable local conserva el índice SHA-256 `3f0f219bad7736ada4c33386c1b7af00db2536d973b9e3d409a1f7550873c8cf`. No se ha publicado una nueva Beta.

## Continuación: protección de importaciones

Las dos rutas conocidas que aplican lotes remotos utilizan ahora un bloqueo SQLite compartido con la creación de acciones explícitas. Mientras se aplica un lote, una acción de historial pendiente, incierta o un desmarcado confirmado sin reconciliar hace que el elemento coincidente se posponga. También se posponen identidades con un identificador coincidente y otro contradictorio. La prueba utiliza los almacenes reales de XStream con datos sintéticos y comprueba que un desmarcado confirmado no es revertido por una lectura anterior; otra prueba usa procesos independientes para comprobar que la creación de una acción espera al final de la importación.

El desmarcado confirmado permanece protegido hasta que exista un procedimiento que pruebe su reconciliación remota; no se presume que la ausencia en una lectura parcial sea una eliminación. La captura de todos los cambios locales de visto y listas, la reconciliación de progresos/listas entre instalaciones y la ejecución segura de planes de restauración siguen incompletas. No se ha publicado ni instalado una Beta.

Suite posterior a la protección de importaciones: 788 pruebas aprobadas, 102 subpruebas y una omisión que requiere canal Stable. Los ZIP son locales y mantienen versiones antiguas; no deben publicarse con esos números. La prueba de exclusión entre procesos y la prueba sobre los almacenes XStream utilizan datos sintéticos.

## Recuperación de desconexiones antes del envío

Cuando la validación de la cuenta falla por conexión antes de invocar el POST, la acción queda pendiente con espera para un reintento seguro. Las respuestas perdidas después de iniciar el POST siguen siendo inciertas y no se reenvían automáticamente. Pruebas con transporte simulado verifican que en el primer caso no hubo escritura remota.

La protección de importaciones todavía no captura todos los cambios locales ajenos a la cola; un desmarcado confirmado permanece retenido hasta que exista evidencia remota suficiente, por lo que no se afirma reconciliación completa. El plan confirmado no cuenta todavía con un ejecutor que demuestre la exclusión de Kodi y valide la cuenta activa. Por estas dos razones continúa bloqueada la publicación Beta.

Suite de continuación con los ZIP locales exactos: 789 pruebas aprobadas, 102 subpruebas y una omitida por requerir canal Stable. La prueba adicional del reintento programado ante desconexión anterior al POST también pasó. No se publicó ni instaló Beta; la migración de todos los cambios locales y el ejecutor de restauración con Kodi realmente detenido siguen sin implementar.

## Captura local: estado y límites

| Cambio y origen | Almacén y captura | Identidad y destino | Estado |
|---|---|---|---|
| Visto o no visto de película, XStream | `watched_movies_pN.json`, diario antes de guardar bajo el bloqueo del almacén | Identificador disponible y perfil; todavía sin cuenta ni proveedor verificados | Capturado; no conectado a la cola de envío |
| Visto o no visto de episodio, XStream | `watched_episodes_pN.json`, mismo diario | Serie, temporada y episodio disponibles; todavía sin vinculación verificada | Capturado; no conectado a la cola de envío |
| Avance de película o episodio, XStream | `resume_points_pN.json`, mismo diario | Huella de la clave y valores numéricos; no se guardan URL | Capturado; resolución y envío pendientes |
| Importación remota aplicada por XStream | Los mismos almacenes; origen `trakt_import` | Marcada por procedencia para impedir una futura reexportación como cambio local | Captura probada con datos sintéticos |
| Creación y cambio de nombre de listas de Service | SQLite de colecciones; registro en la misma transacción | ID local de lista | Capturado; asociación a cuenta y lista remota pendiente |
| Adición o eliminación en colecciones de Service | SQLite de colecciones; registro en la misma transacción | Tipo e ID TMDb; importaciones marcadas como observadas | Capturado; reconciliación y envío pendientes |
| Acciones explícitas Trakt de XStream | Cola persistente de Service | Cuenta, perfil, proveedor e identidad tipada | Enrutadas y probadas con transporte simulado |
| Favoritos y pendientes de XStream | `favorites_N.json` | Depende del contenido y perfil | Sin adaptador de captura general |
| Reproducción gestionada por Kodi y `script.trakt` | Almacenes y scrobbling de terceros | Depende del evento y de la identidad que expongan | Sin captura general verificada; no se atribuyen sus escrituras a AcTweeteR |

El diario XStream registra primero una intención `prepared` y la confirma después de guardar el almacén. Si se interrumpe entre ambos pasos, la intención permanece sin resolución: todavía no existe recuperación automática que pueda decidir si la escritura llegó a aplicarse. No hay un consumidor que envíe estos registros a Trakt; incorporar uno sin vincular cuenta y proveedor podría transmitir cambios a la identidad equivocada. Si el diario no puede persistirse, el guardado coordinado falla en lugar de perder silenciosamente el cambio. Esta consecuencia también necesita validación en Kodi antes de publicar.

La restauración confirmada sigue sin ejecutor seguro: el parámetro `kodi_stopped` de la transacción es una afirmación del llamador, no una comprobación independiente de que los almacenes estén cerrados o de que Kodi no vuelva a abrirlos. No se ha conectado ni aplicado a datos reales. La compatibilidad de ese ejecutor con macOS, Android y tvOS no está demostrada.

Suite contra los ZIP locales de esta continuación: **795 pruebas aprobadas, 102 subpruebas y una omitida** por requerir el canal Stable. Las pruebas nuevas cubren el registro de modificaciones e importaciones, ausencia de secretos en el diario, persistencia de intenciones interrumpidas y reversión atómica ante fallo del diario de colecciones. Son pruebas automatizadas con datos controlados; no verifican sincronización real ni una restauración real. Los ZIP locales mantienen versiones publicadas y no son publicables con esas versiones. No se ha modificado Testing ni Stable, ni se ha instalado esta candidata en Kodi. El verificador de Stable confirma el índice `3f0f219bad7736ada4c33386c1b7af00db2536d973b9e3d409a1f7550873c8cf`.

## Recuperación conservadora y bloqueo explícito de restauración

El diario registra ahora huellas de los estados anterior y posterior. Bajo el bloqueo del almacén, una intención interrumpida se contrasta con el estado presente: una importación cuyo resultado coincide se marca `observed`; las operaciones locales sin cuenta y proveedor acreditados y los resultados divergentes se mantienen `quarantined`, sin envío ni asignación retrospectiva de ámbito. Las intenciones antiguas sin nombre de almacén verificable permanecen pendientes. Esta clasificación no conecta el diario a la cola ni identifica el contenido de las claves de avance; no constituye reconciliación completa.

La función de aplicación de planes rechaza expresamente la operación después de validar el plan, incluso si el llamador afirma que Kodi está detenido. La previsualización, confirmación y preparación permanecen disponibles. Falta un ejecutor que impida la reapertura de los almacenes durante la transacción; no se ha demostrado en ninguna plataforma.

Validación de esta continuación: **796 pruebas aprobadas, 102 subpruebas y una omitida** por requerir Stable. XStream y Service se construyeron dos veces con resultados idénticos: SHA-256 `872db6026b46aa05674588a254633ee70e99ff51d8e1221138146dd4146815ab` y `78e48441a9a2c5e788e68eed05c8436e8cbaece6536f566507adeb0effec0940`, respectivamente. Son paquetes locales de prueba que todavía utilizan números publicados, no candidatos publicables. El verificador local de Stable sigue confirmando el índice `3f0f219bad7736ada4c33386c1b7af00db2536d973b9e3d409a1f7550873c8cf`. No se ha publicado ni instalado la modificación.

## Adaptador de entrega del diario a Service

`trakt_local_journal.verified_scope` permite adjuntar al evento nuevo cuenta, perfil, huella de proveedor, huella de perfil Kodi y generación. El ámbito solo se registra durante la modificación y no se asigna retrospectivamente. Este contexto todavía requiere conexión con un productor runtime que acredite la vinculación; su presencia como API no demuestra esa integración.

`deliver` entrega películas con identidad explícita `tmdb:movie:N` a `Outbox.enqueue_manual`, incluidos desmarcados. Conserva los IDs de salida en el evento de origen. Un fallo entre la inserción durable y la confirmación del diario vuelve a utilizar el mismo nonce y no duplica la operación. Las importaciones, los ámbitos distintos y los IDs IPTV ambiguos no se exportan. Las operaciones no cubiertas se mantienen en cuarentena. No hay exclusión distribuida entre instalaciones.

Dos pruebas nuevas recorren captura → diario → cola → POST simulado → confirmación, interrupción entre almacenes, aislamiento de cuenta, importación y ambigüedad. Las pruebas de diario y cola suman 31 aprobadas. No se ha conectado este adaptador al ciclo automático: faltan el productor de ámbito verificado en las rutas de escritura reales, autorización de exportación distinguible del consentimiento de importación, adaptadores de episodios/avances/listas y reconciliación completa. No hay publicación ni instalación runtime.

## Conexión al guardado real de XStream

El coordinador de `WatchedMovies`, `WatchedEpisodes` y `ResumePoints` consulta ahora el ámbito al guardar. La ruta autenticada existente persiste la cuenta y una huella de las credenciales verificadas, sin guardar tokens en el registro. Cada guardado contrasta credenciales, perfil activo, proveedor y perfil Kodi. Un cambio invalida la atribución hasta una nueva verificación. La entrega de películas con TMDb explícito se invoca tras guardar, utilizando `trakt_explicit_outbox.sqlite`, la cola existente de Service. No se ha implementado todavía entrega de episodios, avances ni listas.

Las operaciones capturadas entran en estado `held`, excluido de los reintentos automáticos: el consentimiento actual autoriza importación, no la exportación automática general. Una autorización explícita de la operación permite enviarla por el mecanismo existente. Los eventos retenidos también protegen la importación frente a snapshots contradictorios. Falta conectar una autorización de exportación específica y verificar el circuito de reproducción real. No se publicó ni instaló esta candidata; no hay cambios de Stable.

Validación: 799 pruebas aprobadas, 102 subpruebas y una omitida específica de Stable, utilizando los ZIP locales actualizados. Las siete pruebas del diario también pasan tras reforzar la aserción de que `held` no se reintenta automáticamente. No hay validación de reproducción real en Kodi.

## Episodios y autorización por operación

La captura de episodios intenta resolver la identidad en el momento del cambio mediante el catálogo del proveedor acreditado, `verified_show_records` y `verified_episode_records`. Exige correspondencia única del ID interno con temporada/número de episodio y guarda la identidad externa en el evento; los casos no resueltos siguen en cuarentena. La entrega utiliza el mismo nonce determinista y la misma cola que películas, con operaciones `history.add`/`history.remove` retenidas. La prueba de captura y entrega simula el resultado del resolvedor: no demuestra reproducción ni resolución real en Kodi.

La pantalla de operaciones muestra ahora `held` y permite abrir la ruta existente de autorización. Esta vuelve a verificar cuenta y proveedor, explica la operación y advierte del borrado de historial en `history.remove`; cancelar no envía nada. Es autorización individual independiente de la importación, no un consentimiento general de exportación automática. Operaciones confirmadas o inciertas no se reenvían.

Los adaptadores de avances, favoritos, pendientes y colecciones/listas siguen sin completar. La sincronización bidireccional no se declara terminada. No se publica Beta ni se modifica Kodi Master.

Suite con los ZIP locales actualizados: **801 aprobadas, 102 subpruebas y una omitida** específica de Stable. SHA-256 XStream `1918a0731125315cb30f5ba1c8b982286e32bf73a938bf3d6b68f36cfe8519cb`; Service `6e26e8b1f48f06db63fed3238fd77579d24d7a62da443a90acd06c34eda153ce`. Son ZIP de prueba con números antiguos y no deben publicarse. Stable local conserva su hash verificado.

## Consentimiento general de exportación separado

El menú incorpora autorización y revocación persistentes de exportación, distintas de la importación, con cuenta, perfil y proveedor. Service puede despachar el ciclo con exportación autorizada aunque la importación esté apagada; esa ruta no importa datos. La cola incluye operaciones retenidas solo con autorización vigente y la vuelve a comprobar antes del POST. Si se revoca antes del envío o hay una desconexión segura, conserva `held`, sin convertirlo en pendiente autorizado implícitamente. Prueba simulada: ausencia de permiso → ningún envío; revocación durante la validación → ningún envío; nueva autorización → una sola confirmación.

Límite deliberado: `history.add` capturado permanece retenido para evitar duplicar el scrobbling de script.trakt; requiere reconciliación de autoridad antes de habilitar automatización. El diálogo explica este límite. Avances, favoritos/pendientes y colecciones/listas todavía no tienen adaptadores completos. No se declara sincronización bidireccional completa ni se publica. La restauración sigue deshabilitada.

Suite: 802 aprobadas, 102 subpruebas y una omitida específica de Stable. El primer intento falló porque el generador rechazó la huella intermedia de `tmdb_routes.py`; se comprobó que la única diferencia era pasar `params` a la ruta de consentimiento, se actualizó la huella y se reconstruyó antes de repetir con éxito la suite. La etiqueta de estado de exportación añadida después pasó sus diez pruebas de interfaz, sin repetir la suite completa ni reconstruir el ZIP tras esa etiqueta. Stable local conserva su hash. Sin instalación en Kodi ni escrituras reales en Trakt.

## Consolidación local de avances y autoridad de reproducción

Se inspeccionó el `script.trakt` instalado en Mac, en `resources/lib/service.py`: su servicio conecta inicio, fin, pausa, reanudación y salto al `Scrobbler`. No se modificó el addon. Este componente continúa siendo la autoridad de scrobbling; el diario de AcTweeteR no envía avances ni vistos capturados automáticamente. La inspección de código no acredita que esos eventos se hayan enviado correctamente en runtime.

El diario añade porcentaje cuando posición y duración son finitas y válidas. Al confirmar un avance local con ámbito, consolida registros no enviados del mismo contenido y ámbito mediante una transacción SQLite: conserva los anteriores como `superseded`, con referencia al sucesor, y no permite que un timestamp anterior desplace al vigente. No consolida importaciones, eventos ya encolados ni registros de otro ámbito. Prueba sintética: timestamps 100 → 200 → 150 mantienen únicamente 200 vigente y conservan toda la evidencia.

Esto no completa los cuatro bloques: la entrega de avances a la cola, los adaptadores de favoritos/pendientes y las listas de Service siguen pendientes. La exclusión con script.trakt se consigue reteniendo exportaciones de reproducción, no mediante un bloqueo distribuido. Sin Beta publicada ni instalación en Mac.

Suite de esta continuación con ZIP locales: **803 aprobadas, 102 subpruebas y una omitida** específica de Stable. XStream SHA-256 `09e25f92d07765fdcc5a901f3fa84e0ccd938ba341ddf69ae6b8fb2b6ce785c9`; Service `dfa4cadee8f7748f8b8794b9ab561b705183ba877f344d29cc8c2de0c183e18b`. Sin publicación. Stable conserva su hash verificado.

## Conexión de capturas retenidas y favoritos reales

La cola existente admite referencias retenidas (`schema=3`, estado `retained`) a eventos cuya identidad, ámbito o autoridad de envío no está acreditada. Solo conservan tipo de fuente, identificador derivado y huella del evento; no contienen credenciales, URL ni títulos. No son operaciones exportables ni equivalen a sincronización remota. El menú las muestra sin enlace de envío. Los avances con ámbito llegan a esta retención desde el guardado real; el ciclo de sincronización entrega también las capturas de colecciones de Service, sin atribuirles la cuenta actual. La prueba verifica entrega repetida sin duplicados y exclusión del planificador incluso con exportación autorizada.

El generador conecta `Favorites._save` con el coordinador existente. La escritura se bloquea entre procesos y fusiona los cambios por carpeta, tipo e ID, evitando que una instancia antigua elimine altas independientes. Se capturan altas/bajas de Favorites y PendingAdapter; los pendientes tienen semántica propia y las demás carpetas conservan una huella sin asumir destinos Trakt. Los eventos ambiguos permanecen en cuarentena o retención, no se envían. La prueba ejecuta Favorites y PendingAdapter reales del ZIP con un perfil sintético y comprueba altas, bajas, identidad por tipo, dos instancias y ausencia de URL en el diario. No es una prueba en Kodi Master.

Pendiente: resolución y mapeo exportable de listas, reconciliación bidireccional de listas y avances, y verificación real. Las referencias retenidas no completan estas funciones. Sin publicación ni instalación Beta; restauración deshabilitada.

Suite final de esta continuación: **805 aprobadas, 102 subpruebas y una omitida** específica de Stable. La comprobación histórica de Favorites usa ahora la huella de su base histórica; el generador verifica por separado el archivo nuevo. XStream local SHA-256 `78fd3725e4e989254f40e1e632f302c05b06d65309b34abb2354f6f7d5dd3443`. Las pruebas empaquetadas no sustituyen una validación de Kodi Master. No se ha publicado ni instalado Beta. El verificador confirma Stable intacta.

## Mapeos de pertenencia a listas en la cola existente

`manual_event` admite operaciones tipadas `list.<ID numérico>.add/remove`, construye exclusivamente `/users/me/lists/<ID>/items[/remove]` y conserva la validación de cuenta, perfil, proveedor e identidad. Reutiliza los mismos estados, confirmación y protección de resultados inciertos. No permite rutas arbitrarias ni slugs ambiguos. Se probaron juntas watchlist, colección y listas personales: altas, bajas, payload exacto, cambio de cuenta y repetición de una operación confirmada (un solo POST simulado).

La selección/configuración de destinos remotos para las colecciones locales y la importación/reconciliación de pertenencia todavía no están integradas. Este mapeo de transporte no completa la sincronización bidireccional. Los avances siguen retenidos para no duplicar el scrobbling de script.trakt. La documentación oficial de Trakt relaciona los avances con los eventos de scrobbling; no se ha añadido un supuesto endpoint genérico de escritura de posiciones. Referencia: https://trakt.docs.apiary.io/reference/movies

Sin escrituras reales, publicación ni instalación. Stable no se modifica.

Suite con paquetes locales: 806 aprobadas, 108 subpruebas, una omitida específica de Stable. Service SHA-256 `85dfb8d5344f132e5a54a6d27a78ea6a6f43b4fe89a2c890534b207763849838`. No equivale a una validación runtime en Kodi.


## Continuación 2026-10-29 — Destinos explícitos y reconciliación de colecciones Service

Implementado y comprobado con transporte simulado, no validado en Kodi:

- `collection_catalog.py`: configuración persistente por cuenta/perfil/proveedor/generación para watchlist, colección, favoritos Trakt y listas personales numéricas. Cada cambio futuro captura la revisión del destino en la misma transacción; cambiar la configuración no redirige eventos anteriores ni migra elementos.
- `trakt_auto_routes.py` y `trakt_restore_ui.py`: configuración explícita desde el menú y lectura de los destinos configurados en el ciclo manual/automático. Las listas personales se verifican por ID; el consentimiento de exportación sigue siendo independiente.
- Importación atómica por colección: respuestas completas, comprobación de actividad y ámbito antes/después, filtros por tipo, protección de cambios locales, rechazo de snapshots antiguos y registro de origen remoto sin reexportación. Las eliminaciones solo afectan a miembros previamente importados/confirmados; más de 20 eliminaciones requieren revisión.
- Confirmación en dos pasos: una operación local deja de bloquear la reconciliación únicamente cuando la cola la confirma y un snapshot posterior refleja su resultado. Conserva referencia al recibo. Un POST confirmado sin una lectura compatible mantiene la protección.
- La colección Trakt utiliza su respuesta completa no paginada; watchlist/favoritos/listas exigen evidencia de paginación completa. Documentación contrastada: https://trakt.docs.apiary.io/reference/movies .
- Los errores de importación se incorporan a la ruta existente de fallo del ciclo y no quedan como éxito de sincronización.

Pruebas: **810 passed, 1 skipped, 108 subtests passed** (41,64 s), sobre ZIP locales exactos. Omisión: contrato exclusivo de canal Stable. Incluye ruta real con transporte simulado, respuesta truncada, protección del desmarcado local, importación sin exportación, confirmación seguida de eliminación remota, rollback de escritura interrumpida, snapshot antiguo y cambio de mapeo.

Paquetes de comprobación, **no publicados ni instalados**, aún con las versiones de desarrollo existentes (no reutilizables para publicación):

- XStream `/private/tmp/trakt20-mapped-xstream-final.zip`: `977470e641c13b322aa9d81051cff76e10ed67f2763af0495596b568d44a5aee`.
- Service `/private/tmp/trakt20-mapped-service-final.zip`: `7a93fbdf783aeb229ec96e493246fcb466f1a6265d058827cb222bd683122259`.
- Dos construcciones idénticas de cada paquete; CRC correcto; AST de 117 archivos Python y 5 XML válidos.
- Stable verificada sin cambios: `3f0f219bad7736ada4c33386c1b7af00db2536d973b9e3d409a1f7550873c8cf`.

Pendiente de implementación, no impedimento externo: conectar los mapeos explícitos de las carpetas nativas de favoritos/pendientes XStream y su reconciliación al almacén real. Sus eventos siguen retenidos; la implementación de Service no debe presentarse como cobertura de XStream. La exportación complementaria de avances sigue retenida para no duplicar script.trakt; su código instalado contiene manejadores de inicio/pausa/reanudación/finalización, pero esta sesión no valida envíos runtime. La restauración de escritura continúa deshabilitada. No se hicieron escrituras reales a Trakt, publicación, instalación ni validación visual en Kodi.


Continuación: la importación de colecciones rechaza elementos remotos malformados o de tipo desconocido antes de aplicar el snapshot, para evitar que se interpreten como ausencias. Pruebas específicas: 17 aprobadas. El adaptador bidireccional de favoritos y pendientes XStream sigue pendiente; no se ha publicado.


Entrega de eventos Favorites con destino capturado: `trakt_local_journal.deliver` convierte altas/bajas de películas y series con `destination_capture` y `external_identity` en operaciones idempotentes de la cola existente. Exige ámbito coincidente y tipo movie/show correcto; quedan held para consentimiento, nunca se envían directamente. Prueba sintética de ocho combinaciones, cambio de cuenta y doble entrega: 12 tests del diario aprobados. Esta prueba NO demuestra captura runtime: `prepare` aún no produce esos campos desde una configuración nativa, falta configurar las cuatro fuentes en `consent_route` y aplicar la importación a Favorites. No publicado ni instalado; suite completa no repetida en esta continuación.


## Configuración y proyección nativa — continuación

Cambios efectivos: consent_route ofrece las cuatro fuentes nativas y persiste la carpeta/tipo junto al destino y ámbito; prepare consume ese mapeo por hash de carpeta y tipo. sync_configured_collections invoca sync_native_collection tras un snapshot completo: resuelve IDs contra inventarios verificados y aplica mediante Favorites.apply_trakt bajo el bloqueo del almacén. Las importaciones quedan observed; solo elimina elementos con su marca de origen, máximo 20 por aplicación. Verifica que no haya un snapshot posterior antes de escribir. El guardado nativo conserva el diario y sustitución atómica existentes.

Pruebas: 812 aprobadas, 1 omitida exclusiva de Stable, 108 subpruebas. Prueba del Favorites empaquetado cubre altas/bajas de películas/series, carpetas de favoritos/pendientes, protección local y ausencia de reexportación. Dos ZIP idénticos: SHA-256 46980054d9155737a4197eb3dfdce4962637e228186f4798beddac8aa5db68e1; CRC, Python y XML válidos. Es paquete local de comprobación con versión existente, NO publicable bajo ese número.

Limitación pendiente de programación: protected() mantiene protegidos todos los eventos nativos locales incluso después de confirmar su exportación. Falta liberar esa protección con confirmación de cola anterior a una lectura remota compatible, conservar la transición y probarla de extremo a extremo. También faltan pruebas integradas del menú de configuración y del circuito completo frente a cambios concurrentes de configuración. No se declara PASS runtime ni Beta terminada. No publicado, no instalado en Kodi. Stable verificada: 3f0f219bad7736ada4c33386c1b7af00db2536d973b9e3d409a1f7550873c8cf.


Validación continuada: las cuatro combinaciones usan Favorites empaquetado, diario, cola, POST simulado y reconciliación nativa para verificar alta local, confirmación y baja remota sin reexportación. La prueba sustituye el resolvedor de identidad y el ámbito por datos controlados y llama directamente a sync_native_collection; no cubre aún el scheduler ni sync_configured_collections de extremo a extremo. Suite: 812 aprobadas, 1 omitida exclusiva Stable y 108 subpruebas. ZIP XStream local 1bf15533aa6e31512dc9b3d6922c91f03270f4a81564fdbdcea6a7f2c89e965a; reproducible, Python/XML/CRC válidos. No publicado: queda verificar la ruta real completa y actualizaciones concurrentes; no instalado en Mac.


## Candidata experimental para Testing

XStream 1.1.2.39~beta1 (`88dc63547f981c16c84faced4f1c437b83de5f0baa73c1ef1fdde7fe1547d3e8`) y Service 0.4.97~beta1 (`a6a79fda37e88e7d594a6fcba87d2b4b5eef3c5a6b85b5f4afd9847e5027b9f4`). Suite exacta del índice candidato: 815 aprobadas, una omitida exclusiva Stable y 108 subpruebas. Las exportaciones automáticas de bajas quedan retenidas para autorización individual; restauración de escritura y avances duplicables siguen deshabilitados/retenidos. El usuario debe autorizar cualquier envío. La sincronización bidireccional real, el planificador completo con las cuatro colecciones y la concurrencia entre dispositivos no están validados.
