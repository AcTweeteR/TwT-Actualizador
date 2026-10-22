# Registro de cambios de prueba en Trakt — 22/10/2026

Comparación **solo lectura** de tres exportaciones privadas del perfil XStream del Mac.
Los tres `snapshot.json` verifican SHA-256 contra su `manifest.json`.
No publicar las exportaciones: contienen historial personal.

## Cambio remoto confirmado (reversible con autorización posterior)

- Cuenta: misma cuenta en las tres exportaciones; no registrar credenciales.
- Película: **TMDb 644**.
- Evento de historial Trakt **14559147842**.
- Fecha remota: **2026-10-21T20:47:00.000Z**.
- Estado anterior: existían los eventos **14349681805** y **14349473811** (29/08/2026).
- Estado posterior: los dos anteriores permanecen y se añade **14559147842**.
- Reversión futura: revisar estado actual y solicitar autorización para borrar **solo** el evento **14559147842**, nunca borrar por título o ID de película completo.

## Prueba sin cambio confirmado

- Serie: TMDb **250307**, temporada **2**, episodio **15**.
- Evento preexistente **14349964049**, fecha **2026-08-29T12:14:00.000Z**.
- Antes y después: mismo evento; **ningún ID nuevo** en las exportaciones.
- No revertir ni desmarcar el episodio: no hay cambio atribuible demostrado.

## Fuentes privadas (no versionar)

- `~/Library/Application Support/Kodi/userdata/addon_data/plugin.video.xstream-pro/trakt_exports/snapshot-0rvnkxml/`
- `~/Library/Application Support/Kodi/userdata/addon_data/plugin.video.xstream-pro/trakt_exports/snapshot-miieb58r/`
- `~/Library/Application Support/Kodi/userdata/addon_data/plugin.video.xstream-pro/trakt_exports/snapshot-s49j1_q6/`

No se efectuó POST, DELETE ni cambio de estado remoto durante esta auditoría.
La reversión requiere comprobar antes que el evento sigue existiendo y autorización explícita.
