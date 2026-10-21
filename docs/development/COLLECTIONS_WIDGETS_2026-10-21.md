# Mis Colecciones — candidata Testing

## Base e aislamiento

- Base oficial: `067df3770d79f4bb01d242fdefddd4d4fedafb8e` (origin/main).
- Rama: `codex/collections-widgets-2026-10-21`.
- Commit de implementación y paquetes: `39720dd`.
- Worktree dedicado: `TwT-Actualizador-collections`; ningún otro checkout modificado.
- Árbol Git de Stable `repo/`: `551a296452cf3412f673c390374e811c42c4a106`.
- No se han modificado instalaciones, perfiles, colecciones, credenciales, Trakt o PVR.

## Causas y correcciones

1. `premium_routes.py` consultaba `Favorites.get_all()` al listar Favoritos.
   Ese método reúne todas las carpetas, incluidas las internas de Pendientes.
   La consulta ahora usa `get_favorites(stype)`, limitada a las carpetas de
   favoritos de upstream (nombre inglés y nombre localizado actual).
2. `is_favorite()` y `remove()` sin carpeta recorrían todas las listas.
   La acción `toggle_profile_fav` no especificaba tipo ni carpeta.
   Ahora el ámbito predeterminado es Favoritos y las acciones pasan el tipo.
   `add()` distingue `(stype, provider_id)`, normalizando IDs numéricos a texto.
   Pendientes conserva sus dos carpetas y su adaptador existentes.
3. `_build_favorite_ctx()` incorpora Pendientes para películas y series.
   Se retiran las acciones duplicadas en los renderizadores premium y las
   carpetas internas de Pendientes dejan de ofrecerse como listas arbitrarias.
4. `Premium.CollectionsRefresh` invalida las rutas de widgets preparadas por
   AcTweeteR; `Container.Refresh` actualiza la vista nativa activa. No hay
   ReloadSkin, reinicios ni base de datos nueva. Los objetos favoritos en caché
   releen el archivo antes de construir el menú contextual.
5. `collections_root` devuelve siempre Favoritos y Pendientes, con icono de
   carpeta, tipo y perfil explícitos. Abre listados paginados del catálogo real;
   los elementos desaparecidos se omiten sin borrar su registro ni fabricar URL.
6. La plantilla de cada hub añade la fila terminal después de todos sus items,
   incluidos widgets personalizados. Suprime la representación antigua de esa
   misma ruta, sin borrar los DATA personalizados. Se reutilizan el contenido,
   la presentación cuadrada y la navegación comunes de la skin.
7. Se retiran los accesos independientes de los DATA predeterminados, no las
   rutas internas. La migración v14 conserva backups, hashes de propiedad,
   detección de conflictos y consentimiento del migrador existente. La prueba
   desde los paquetes Stable 1.2.31/0.4.52 comprueba backup, repetición y conflicto.

No se alteran las rutas de reproducción, EXPANDIR, Trakt ni PVR. No se migra ni
reescribe el almacenamiento existente de colecciones al leerlo.

## Pruebas ejecutadas

| Comprobación | Resultado | Evidencia y alcance |
|---|---|---|
| Suite de partida | PASS_AUTOMATED | 292 tests |
| Suite candidata | PASS_AUTOMATED | 308 tests; 16 casos nuevos de colecciones |
| Stores reales de XStream con datos sintéticos | PASS_AUTOMATED | Persistencia, perfiles, colisiones movie/series, independencia de listas, formatos antiguos y estado desconocido |
| Rutas reales con proveedor simulado | PASS_AUTOMATED | Dos carpetas vacías, tipado, pendiente que no es favorito, ID retirado que permanece almacenado |
| Contratos de widget y migración | PASS_AUTOMATED | Solo dos hubs, última fila, DATA sin accesos duplicados, backup v13→v14, idempotencia, personalizaciones no sobrescritas |
| Menú contextual | PASS_AUTOMATED | Acciones independientes, sin duplicados y etiquetas recalculadas tras mutar datos sintéticos |
| Resolver de propiedades instalado de Skin Shortcuts | PASS_AUTOMATED | 12 casos; fuente pública SHA-256 `3a1112821f52ea7eec8e1c506f63541674a4755884de1c230bcc1e6732b7276c`; no se ejecuta su entrypoint ni se lee perfil |
| AST/XML del código propio | PASS_STATIC | 39 Python y 199 XML válidos |
| CRC, AST/XML y patrones de secretos en paquetes | PASS_STATIC | 619 miembros, sin userdata, DB, bytecode ni patrones de tokens/clave privada detectados; no equivale a una auditoría universal de secretos |
| Reproducibilidad | PASS_AUTOMATED | Reconstrucciones independientes de los ZIP y del índice Testing; hashes idénticos |
| Stable | PASS_STATIC | `git diff origin/main -- repo/` vacío; históricos intactos |
| Lenovo | NOT_TESTED | Conectada por ADB, TB330FU Android 15. Solo lectura de manifiestos; no se ha instalado esta candidata |
| Mac | NOT_TESTED | Solo lectura de versiones y código público de Skin Shortcuts; sin instalación de la candidata |
| Long press, menú del mando, clic derecho, Back y foco | NOT_TESTED | Requieren candidata instalada; ninguna prueba XML demuestra interacción real |

## Versiones y artefactos candidatos

| Componente | Candidata | SHA-256 |
|---|---|---|
| Servicio | 0.4.53 | `55455ea23da04124f4e52f66c24fcb7fa3df366844c9859fcdf38ace8e72c958` |
| Skin | 1.2.32~beta1 | `3e7cf74ad59cd7d9b3ee8be9b399f4974816890a2f2dd31ed9cfea3e9121d08b` |
| XStream | 1.1.2.16 | `1161eedf5e1b5aa49570753781f99c286130c70f56a760a32802b7a271a74a0f` |

Los ZIP están en `docs/testing/repo/<addon-id>/`. No sustituyen versiones previas.
XStream se reconstruye desde el upstream 1.1.2 fijado por SHA-256, con un parche
adicional independiente; mantiene licencia CC BY-NC 4.0 y atribución a PesicP.

Inventario observado, sin asumir equivalencia por versión:

- Lenovo: skin 1.2.30~beta10, servicio 0.4.52, XStream 1.1.2.15, Testing 1.0.2.
- Mac: skin 1.2.30~beta5, servicio 0.4.49, XStream 1.1.2.14.

## Gate runtime y recuperación

La preparación automatizada no certifica la aceptación funcional final.
Se ha solicitado autorización concreta para actualizar Lenovo exclusivamente
desde Testing sin escribir en sus colecciones personales. No se han usado ZIP
locales, copias al perfil ni instalaciones por ADB.

Después de instalar desde Testing:

1. Esperar carga completa y comprobar al final de ambos hubs las dos carpetas.
2. Abrir cada carpeta, volver con Back y verificar foco/contexto.
3. Verificar clic derecho, menú de mando y pulsación larga sin ejecutar acciones
   sobre títulos personales. Las escrituras se prueban únicamente con fixtures
   sintéticas; si se requiere una prueba Kodi que modifique una lista personal,
   obtener autorización específica antes de realizarla.
4. Comprobar que Inicio, Buscar, EXPANDIR, reproducción, perfiles y PVR mantienen
   su comportamiento; no iniciar Trakt ni cambiar preferencias IPTV.
5. Ante regresión, no borrar datos: los ZIP históricos se conservan y la
   migración produce backups verificables en el perfil de servicio. La vuelta
   de versión y cualquier restauración deben realizarse por vías nativas y con
   comprobación del backup, nunca copiando a ciegas carpetas al dispositivo.

PUBLICATION_STATUS=PENDING_CHECKS
FUNCTIONAL_ACCEPTANCE=PARTIAL
STABLE_UNCHANGED=YES
PERSONAL_INSTALLATIONS_MODIFIED=NO
