# AcTweeteR 0.4.22 — estable

**Kodi 21.3 Omega · Skin 1.2.18 · Servicio 0.4.22 · Repositorio 1.0.3 · XStream Pro 1.1.2.3**

## Corrección

XStream Pro 1.1.2.3 corrige un `IndentationError` de Python en el parche de
recomendaciones Trakt: las inserciones ahora se anclan a contexto fuente único,
no a offsets de línea que cambian al aplicar otros parches. El constructor
rechaza contextos ausentes o ambiguos y valida todos los Python antes y después
del empaquetado.

El servicio 0.4.22 eleva el mínimo requerido de XStream a 1.1.2.3 para que Kodi
resuelva la actualización por el mecanismo normal del repositorio. No se cambia
la skin ni el complemento repository; no hay migraciones de perfil, credenciales,
progreso, favoritos o historial.

## Instalación y actualización

Instalación nueva: instala Kodi 21.3, permite «Orígenes desconocidos» mediante
el diálogo nativo, añade
`https://actweeter.github.io/TwT-Actualizador/bootstrap/`, instala
`repository.actweeter-1.0.3.zip` y después AcTweeteR desde el repositorio.

Actualización: refresca el repositorio oficial y actualiza el servicio AcTweeteR;
Kodi resolverá XStream Pro 1.1.2.3 como dependencia requerida. No borres datos ni
reinstales Kodi. Los paquetes de versiones anteriores permanecen disponibles.

## Verificación y limitaciones

- **545 tests automatizados PASS**; ZIP/CRC, XML, índice, MD5 y SHA-256:
  **PASS_AUTOMATED / PASS_STATIC**.
- La corrección de XStream 1.1.2.3 aún no se ha probado en Kodi runtime; la
  validación runtime en Android, Android TV, tvOS, macOS, Windows y Linux queda
  **NOT_TESTED**.
- Permanece abierta la incidencia crítica de cierre de Kodi al cancelar trabajos
  de directorio `plugin://`; su componente causante sigue sin identificar. El
  propietario acepta expresamente este riesgo para la publicación 0.4.22. No se
  considera resuelto ni se levanta el gate para versiones posteriores.

XStream Pro sigue bajo **CC BY-NC 4.0**. Se conservan licencia, atribución y aviso
de modificaciones dentro del ZIP; distribución no comercial y sin aval del autor
upstream. Consulte [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
