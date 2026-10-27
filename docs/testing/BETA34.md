# Beta34 — complementos obligatorios (2026-10-27)

## Resultado

La corrección solicitada está publicada en Testing. `script.trakt` y los demás complementos declarados por AcTweeteR son obligatorios en el catálogo de instalación y reparación. La autorización de la cuenta de Trakt sigue siendo una acción del usuario; la instalación de `script.trakt` no depende de autorizarla.

| Comprobación | Resultado | Evidencia |
| --- | --- | --- |
| Service Beta34 en Testing | PASS | `0.4.94~beta8`, ZIP e índice públicos idénticos a los artefactos locales. |
| Actualización nativa en Kodi Mac Master | PASS_RUNTIME | Kodi mostró «Add-on actualizado»; `addon.xml` instalado: `0.4.94~beta8`; `Addons33.db`: origen `repository.actweeter.testing`, habilitado. |
| Reinicio del Service tras actualizar | PASS_RUNTIME | `kodi.log` registra parada de la instancia anterior, instalación beta8 y `SERVICE_INSTANCE_START`/`COORDINATOR_START` de la nueva instancia a las 11:03:54. |
| `script.trakt` en Mac | PASS_RUNTIME | Versión 3.9.0 instalada y habilitada; origen `repository.xbmc.org`. |
| Instalación en teléfono/Lenovo | NO VERIFICADO | ADB no mostró el teléfono; la dirección antigua de Lenovo no respondió. No se alteró ese dispositivo. |
| Suite completa sobre ZIP publicados | PASS_TEST | 726 aprobadas, 4 omitidas y 100 subpruebas; sin fallos. |
| Stable | INTACTA | `repo/addons.xml` conserva SHA-256 `7ce09e4d820d8c52ec697d7a2bac5451a1076eec5d89e2234072be490efe54ee`. |

Las cuatro omisiones requieren, respectivamente, el ZIP upstream fijado para Device Code, la puerta de publicación Stable tras validar Mac y Lenovo, un ZIP candidato XStream específico de concurrencia y el ZIP upstream XStream fijado. No se han contado como pruebas superadas.

## Causa y corrección

El catálogo anterior clasificaba `script.trakt` como opcional y el manifiesto de Service no lo exigía. Por eso podía faltar en una instalación nueva, como la del teléfono. `module_catalog.py`, `first_run.py`, `setup.py` y `addon.xml` del Service ahora lo incluyen en la instalación y reparación obligatorias. También se exigieron SlyGuy Trailers y las demás dependencias declaradas que aún podían quedar fuera del contrato de Service. `CATALOG_VERSION=18` fuerza la reevaluación de instalaciones ya configuradas sin borrar perfiles ni ajustes.

El instalador sigue utilizando el gestor de Kodi y sus repositorios. No acepta términos de terceros ni autoriza cuentas automáticamente. Una fuente ausente o una incompatibilidad de plataforma se comunica como instalación pendiente; no se simula éxito.

## Versiones y artefactos

| Componente | Versión Testing | Estado en Mac |
| --- | --- | --- |
| Skin | `1.2.36~beta4` | Ya instalada; sin cambios en Beta34. |
| Service | `0.4.94~beta8` | Actualizada por Kodi desde Testing. |
| XStream Pro | `1.1.2.36~beta3` | Ya instalada; sin cambios en Beta34. |

Service ZIP SHA-256: `cdda5d0cb9345cb01c6febf503212b519ccbccaeceff895e0f59d61c6c049483`. Índice Testing SHA-256: `8951a551df7518f251db8fd7ab9e9a84d4e7fc26c4543b8f2d297e53833be039`. El ZIP reconstruido dos veces produjo el mismo hash; CRC, XML, Python, dependencias e índice se validaron. Manifiesto: [`manifests/actweeter-beta34-20261027.json`](../../manifests/actweeter-beta34-20261027.json).

Rama `codex/mandatory-addons-beta`; commits `0d07a5e` (catálogo e instalador), `cf4b51c` (dependencias del manifiesto) y `39a4568` (publicación Testing). CI de instalador Beta, verificación Stable y GitHub Pages terminó correctamente para `39a4568`. Los archivos públicos de Pages se compararon byte a byte con el ZIP e índice locales.

## Límites

No se ha demostrado todavía la instalación ni el flujo de reparación en el teléfono, porque no estuvo accesible. Su ausencia de `script.trakt` se explica por la política anterior, pero el estado actual de ese dispositivo sigue sin verificarse. Tampoco se ha probado una promoción Stable; Stable no se publicó ni modificó.
