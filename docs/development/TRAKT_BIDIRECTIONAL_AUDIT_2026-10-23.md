# Auditoría de integración Trakt ↔ XStream — 2026-10-23

## Resultado

**PARTIAL — código y artefactos privados reproducibles; sincronización runtime en Kodi no certificada.** No se instaló, publicó, activó consentimiento ni modificó datos de Trakt o del perfil.

## Estado verificado

- Rama: `codex/trakt-unified-beta-2026-10-22`; HEAD al iniciar: `badc390`; árbol limpio.
- Kodi Mac instalado (lectura de manifiestos): Service `0.4.58`, XStream `1.1.2.27~beta1`, Skin `1.2.32~beta1`.
- El reporte de auditoría proporcionado por el usuario registra GET autenticados HTTP 200 en `/users/settings`, `/sync/watched/movies`, `/sync/watched/shows` y endpoints de playback. No se repitieron ni se renovaron tokens en esta continuación.

## Recorrido de código encontrado

1. `service.py::_run_coordinator` comprueba el consentimiento durable, evita despachar durante reproducción y ejecuta el ciclo XStream a intervalos de cinco minutos.
2. El router incluido en XStream vuelve a verificar cuenta, perfil y fingerprint del proveedor; obtiene actividad y snapshot por GET mediante el transporte nativo de XStream.
3. `trakt_auto_cycle` evita solapamientos, reutiliza exportes/checkpoints compatibles y prepara lotes limitados. Los candidatos sin identidad exacta quedan diferidos.
4. XStream consume la cola por sus stores coordinados, verifica la escritura antes del acuse durable y el servicio avanza el checkpoint después de confirmar.
5. El ciclo solicita una invalidación selectiva de Continue Watching tras aplicar cambios.
6. La salida Kodi → Trakt sigue delegada al `script.trakt` instalado; el puente de metadatos de XStream suministra IDs a Kodi/script.trakt. No se añadió otro scrobbler ni se verificó aquí el POST/scrobbling real.
7. Las recomendaciones existen en el parche XStream y se filtran por IDs exactos disponibles del proveedor. No se validó su presentación runtime ni hay cobertura garantizada para títulos sin identidad externa corroborada.

Este recorrido está conectado en el código candidato; no equivale a haberlo ejecutado en Kodi. La sincronización automática continúa opt-in y no se concedió consentimiento.

## Defecto reproducible del constructor y corrección

El commit `badc390` añadió `apply_trakt_pkce.py` y `trakt_pkce.py`, pero el constructor `build_xstream_package.py` no los invocaba. El ZIP Beta 2 existente incluía PKCE, mientras que una reconstrucción desde el upstream fijado no lo incluía. Además, su payload difería en siete módulos de sincronización respecto a las fuentes actuales, pese a tener la misma versión Beta 2. Reutilizar esa versión habría permitido que Kodi tratara dos contenidos distintos como el mismo release.

Se integró el helper existente en el constructor después de validar los hashes de base y de las fuentes, y se añadieron validaciones obligatorias al ZIP final para la ruta de autorización, el intercambio y el módulo PKCE. Se fijaron hashes del integrador y del módulo. La metadata del manifiesto también se actualizó para el nuevo versionado.

Para no reutilizar el número con payload distinto, los candidatos pasan a Service `0.4.62` y XStream `1.1.2.28~beta3`; Service depende exactamente de Beta 3. Beta 2 permanece reconocida solo para compatibilidad anterior.

## Previsualización actual de solo lectura

Se ejecutó `tools/preview_trakt_mac.py` contra el snapshot existente `snapshot-7xusy3gk` y el perfil Mac. El programa comprobó fingerprints antes y después.

| Métrica | Resultado |
|---|---:|
| Registros Trakt únicos considerados | 1.830 |
| Películas vistas remotas | 1.028 |
| Episodios vistos remotos | 796 |
| Reproducciones remotas | 6 |
| IDs de proveedor verificados | 170 películas, 0 series |
| Matches XStream cacheados nuevos | 0 películas, 2 series |
| Matches con Trakt | 8 películas, 35 episodios (43 total) |
| Películas que se añadirían como vistas | 2 |
| Episodios que se añadirían como vistos | 0 |
| Vistos que ya constan localmente | 38 |
| Avances por actualizar / preservar / diferir | 2 / 8 / 1 |
| Identidades sin resolver / conflictos | 1.787 / 1 |

Las 35 correspondencias episódicas se compararon con el algoritmo histórico: los 35 pares serie-temporada-episodio-ID coinciden exactamente; no hubo correspondencias antiguas exclusivas ni nuevas exclusivas. Cinco episodios quedan pendientes por inventario incompleto. No se infiere que elementos no resueltos estén ausentes del proveedor.

No se aplicó ninguna operación: cero escrituras a Kodi y cero escrituras remotas. Los almacenes activos mantuvieron sus hashes.

Tres muestras de preparación: pared p50 `930.677 ms`, CPU p50 `929.210 ms`, pico Python `158,673,118 bytes`; consulta de generación p50 `2.376 ms`. Son medidas de proceso local, no de latencia visual ni de Kodi runtime.

## Pruebas y candidatos privados

- Suite completa `unittest`: **524 PASS, 0 FAIL, 0 omitidas**, con upstream fijado y el ZIP XStream Beta 3 reconstruido en las pruebas de integración.
- Pruebas nuevas: constructor reproduce PKCE dos veces, hashes de fuente, rechazo del ZIP sin rutas PKCE y contrato Service/XStream.
- XStream Beta 3: ZIP CRC correcto, 115 miembros, contiene el módulo y las rutas PKCE; reconstrucciones idénticas.
- Service `0.4.62`: ZIP CRC correcto, 158 miembros; dos construcciones idénticas.
- Skin `1.2.32~beta1`: ZIP CRC correcto, 392 miembros.
- Índice Testing privado: versiones exactas `repository 1.0.2`, `skin 1.2.32~beta1`, `service 0.4.62`, `XStream 1.1.2.28~beta3`; MD5 del índice comprobado. Todos los artefactos están únicamente bajo `/private/tmp/actweeter-trakt-final-1023`.

SHA-256:

- Service: `d8f8a0dbdab3d39654a4ab9774cf3a18e6cefc0a392d18da5e7405f1cee10fa9`
- XStream: `2726e7330abedb3c485210aba3d952311bc3374e86d133431628b8dfa22af9f3`
- Skin: `3e7cf74ad59cd7d9b3ee8be9b399f4974816890a2f2dd31ed9cfea3e9121d08b`
- `addons.xml`: `415c247b03598288fcfc93e8efd1be6620e93bf1cffdf72edaeae42dec740021`

## No verificado / límites

- El candidato no está instalado en Kodi Master; por tanto, scheduler, consentimiento, GET en proceso Kodi, acuses/checkpoints, refresco de widgets, Continue Watching, recomendaciones y reproducción siguen **NOT_TESTED_RUNTIME**.
- No se realizaron escrituras ni importación real desde Trakt, ni POST hacia Trakt.
- La conectividad Xtream no se reprobó en esta fase; el último diagnóstico disponible registraba timeout TCP, así que los 227 elementos de caché que no dieron match nuevo siguen pendientes, no fallidos.
- No se hizo prueba entre dispositivos.
- La licencia observada de XStream es CC BY-NC 4.0; la distribución pública sigue sujeta a revisión legal independiente. No se publicó ni se hizo push.
- Stable, Lenovo y Apple TV permanecieron intactos.
