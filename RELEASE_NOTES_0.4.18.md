# AcTweeteR 0.4.18 — estable

**Paquetes:** skin 1.2.16 · servicio 0.4.18 · repositorio 1.0.3 · XStream Pro 1.1.2.1 (sin cambios). Baseline: Kodi 21.3 Omega.

## Continuar viendo

- Las rutas de Continuar viendo en Home y Películas usan la fuente existente de
  XStream y reciben un token de refresco cuando Kodi termina una reproducción
  no-preview.
- Los DATA portables incluyen el parámetro de recarga para instalaciones
  limpias. La migración de interfaz v4 actualiza los DATA gestionados en
  perfiles existentes después de crear un backup local verificado.
- No se modifica el almacenamiento de progreso de XStream ni la integración de
  Trakt. La fila solo debe mostrar elementos realmente reanudables.
- 523 pruebas automatizadas PASS cubren las rutas, visibilidad, refresco y
  migración. **La aparición visual y reanudación de la fila en Apple TV aún
  requieren validación del propietario; no se declaran PASS_RUNTIME.**

## Instalación y actualización

Instalación limpia: instala Kodi 21.3, habilita «Orígenes desconocidos», añade
`https://actweeter.github.io/TwT-Actualizador/bootstrap/`, instala
`repository.actweeter-1.0.3.zip` desde Kodi y, después, instala AcTweeteR desde
el repositorio. Kodi conserva el proceso nativo para resolver dependencias.

Actualización: actualiza AcTweeteR desde el mismo repositorio oficial. No borres
el perfil ni reinstales Kodi. Las versiones anteriores permanecen en el
repositorio para rollback. La migración v4 guarda copia antes de cambiar los
DATA de Skin Shortcuts. Si detecta personalizaciones no gestionadas, solicita
consentimiento en vez de sobrescribirlas.

## Pruebas y compatibilidad

- Suite: `PASS_AUTOMATED` — 523 tests.
- ZIP, CRC, XML, índice y checksums: `PASS_AUTOMATED`/`PASS_STATIC`.
- Instalación limpia y actualización mediante Kodi: `NOT_TESTED` para esta
  versión.
- macOS, Windows, Linux, Android, Android TV, Google TV y tvOS runtime:
  `NOT_TESTED` para esta versión. No se infiere compatibilidad runtime entre
  plataformas.
- Trakt autenticación/sincronización runtime: `NOT_TESTED`.

## Limitación conocida

Sigue abierta la incidencia crítica en la que el cierre normal de Kodi puede
quedarse esperando trabajos de directorio `plugin://`. El origen no está
identificado ni corregido. El propietario aceptó este riesgo para publicar
0.4.18 únicamente; esto no cierra ni levanta el gate de releases futuros.

XStream Pro 1.1.2.1 se conserva sin cambios, con atribuciones y condiciones
CC BY-NC 4.0; uso no comercial. Consulte [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
