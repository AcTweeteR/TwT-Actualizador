# Actualizaciones nativas en el asistente AcTweeteR

Rama `codex/smart-search-2026-10-21`. Servicio candidato0.4.49; no publicado.

## Resultado de investigación

Los identificadores reales de Omega21.3 son:

| Ajuste | ID | Valores |
|---|---|---|
| Actualizaciones automáticas | `general.addonupdates` |0 automático,1 notificar,2 nunca|
| Actualizar addons oficiales desde | `addons.updatemode` |0 oficiales Kodi,1 cualquier repositorio|

Fuente: [Settings.h](https://github.com/xbmc/xbmc/blob/21.3-Omega/xbmc/settings/Settings.h#L458)
y [settings.xml](https://github.com/xbmc/xbmc/blob/21.3-Omega/system/settings/settings.xml#L3597).
En la intervención anterior se confundieron esos IDs. Se corrigió el código y se restauró
la preferencia original de repositorios; no se mantiene aquella comprobación como PASS.

**Cualquier repositorio no es necesario para actualizar los tres componentes propios**
cuando están vinculados al repositorio AcTweeteR adecuado. Kodi comprueba primero
posibles actualizaciones oficiales; para addons terceros sin actualización oficial busca
en el repositorio de origen. La opción adicional permite a addons oficiales de Kodi buscar
versiones privadas. No resuelve orígenes vacíos ni selecciona Testing frente a Stable.
[CAddonRepos::DoAddonUpdateCheck, líneas200–251](https://github.com/xbmc/xbmc/blob/21.3-Omega/xbmc/addons/AddonRepos.cpp#L200).
El asistente consulta y muestra esa preferencia, pero nunca la cambia ni pide ampliarla
sin una necesidad que no existe para este caso.

## Implementación

- `resources/lib/addon_update_policy.py`: consulta ajustes con Settings.GetSettingValue.
  Solo configure(), tras yesno explícito, puede usar Settings.SetSettingValue para
  `general.addonupdates=0`. No descarga paquetes, ejecuta instalaciones ni cambia de canal.
- `setup.py`: configuración después de aceptar Bienvenida; revisión después de instalar
  y comprobar componentes; opción de mantenimiento «Actualizaciones y canal»; acción
  `RunScript(service.actweeter,updates)`. El usuario no navega a los ajustes globales.
- `service.py`: revisión de solo lectura al iniciar el servicio, también tras actualizarlo.
  El fingerprint incluye versiones de servicio/skin/XStream y problemas detectados;
  cinco revisiones iguales no generan cinco avisos. Se vuelve a avisar tras cambio de
  versión o aparición de un problema. Las actualizaciones de otros componentes se
  revisan al siguiente inicio del servicio/Kodi; no hay un sondeo permanente nuevo.
- Intención de canal y deduplicación de avisos se guardan únicamente en el addon_data
  propio: `update_policy.json`, mediante el escritor atómico existente, modo600.
- Origen de instalación y reglas individuales se consultan en Addons*.db con SQLite
  **mode=ro**. No se escribe la base. No hay setter JSON-RPC público para vincular
  orígenes o quitar las reglas individuales. Se informa del problema, sin falsificarlo.
- Si no se puede confirmar el canal se permite elegir la intención Testing/Stable;
  la selección no modifica el origen de ningún addon. Una discrepancia requiere usar
  el gestor nativo de Kodi, no sustituir una carpeta ni editar su base.
- Se conservan los ajustes rechazados. Un problema opcional de actualizaciones no
  destruye la configuración IPTV ni fuerza a repetir todo el asistente.

## Guardado: memoria frente a disco

Settings.SetSettingValue modifica el ajuste en memoria, pero su implementación no llama
a Save(). Véase [SettingsOperations.cpp,227–282](https://github.com/xbmc/xbmc/blob/21.3-Omega/xbmc/interfaces/json-rpc/SettingsOperations.cpp#L227).
El asistente comprueba la lectura posterior y lee exclusivamente el valor de ese ajuste
en guisettings.xml mediante Kodi VFS. No escribe el archivo. Si todavía no coincide,
muestra «guardado pendiente de verificar tras cerrar Kodi normalmente», nunca éxito de
persistencia. Tras un cierre normal de Kodi se vuelve a comprobar. No se reinicia Kodi
automáticamente ni se usa una modificación de skin como truco para provocar Save().

## Pruebas

Suite completa: **278/278 PASS_AUTOMATED**;16 pruebas nuevas. Incluyen aceptación/rechazo,
IDs correctos, ya activo, setter rechazado, lectura posterior incorrecta, guardado pendiente,
cinco inicializaciones, cambio de versión, preferencia desactivada, Stable/Testing con
ambos modos de repositorios, orígenes vacíos/mezclados, bloqueo individual, repositorio
deshabilitado, elección conservada, API/DB no disponible, error de escritura y cableado
del asistente/servicio. La prueba histórica que prohibía el antiguo módulo impositivo
ahora comprueba la misma garantía real: el servicio solo llama a review(), sin setters,
sin configure() y sin consentimiento modal. Las pruebas funcionales ejecutan también
las ramas de consentimiento; no se eliminó aquel contrato de protección.

| Comprobación real, Master21.3 | Resultado | Evidencia |
|---|---|---|
| Pantalla de configuración desde las fuentes |PASS_RUNTIME|Diálogo nativo muestra modo, preferencia de repositorios, origen de los tres componentes y bloqueos reales|
| Modo automático correcto |PASS_RUNTIME|general.addonupdates:1→0 mediante API oficial, consentimiento explícito ya recibido|
| Restauración de la preferencia de repositorios |PASS_RUNTIME|addons.updatemode:0→1, recuperando su valor original, no seleccionando una preferencia nueva|
| Persistencia después de cerrar/reabrir |PASS_RUNTIME|Disco y JSON-RPC: general.addonupdates=0, addons.updatemode=1; PID verificado en /Applications/Kodi.app|
| Aviso de guardado pendiente desaparece |PASS_RUNTIME|Reejecutar configure() tras reiniciar ya no registra el aviso en update_policy.json|
| Origen y bloqueo de addon |PASS_RUNTIME detección|XStream origen Testing; servicio/skin sin origen por los ZIP locales de la sesión anterior; skin con regla individual de bloqueo|
| Asistente completo en instalación nueva |NOT_TESTED|No se borran estados del perfil Master para simular un primer inicio|
| Descarga/instalación automática desde Testing |NOT_TESTED|No hay una candidata nueva publicada y los dos orígenes vacíos/bloqueo impiden certificar el recorrido|
| Android/tvOS |NOT_TESTED|Ninguna operación en Lenovo o Apple TV|

Los cambios globales se realizaron exclusivamente mediante la API oficial. Se comprobó
que no había reproducción antes de Cmd+Q. No se usó la acción de apagado del sistema.
No se cambiaron credenciales, Trakt, perfiles, favoritos ni bases de datos. Se utilizó
el respaldo privado verificado de la intervención anterior; update_policy.json no existía
antes de esta prueba. No se ha hecho push ni publicación.

## Distribución y límites pendientes

ZIP0.4.49 reproducido byte a byte en dos directorios privados:

`source/0.4.32/dist/smart-search-update-policy-final/service.actweeter-0.4.49.zip`

SHA-256 `cd148c32c4b7aea04f33e84381524a4442b27c5b603a42582d42e1af05717656`.
La skin no cambia: beta5 mantiene su mínimo compatible de servicio0.4.48.
Versiones instaladas siguen0.4.48/beta5/XStream1.1.2.14; la nueva revisión no está instalada
como servicio0.4.49. El ZIP incluye exactamente el módulo y el cableado de las fuentes.
Se validan CRC, AST Python, XML, ausencia de pyc/DB/logs y patrones de secretos; no es una
garantía de inexistencia de cualquier secreto. No se tocan índices ni paquetes públicos.

Para recibir futuras actualizaciones automáticamente hacen falta el modo global0,
ausencia de bloqueos individuales, un origen válido y habilitado, una versión superior
compatible disponible y red. La programación la controla Kodi. No se promete instalación
instantánea ni una garantía basada únicamente en el ajuste global. La migración de origen
local→Testing debe realizarse una vez desde el repositorio, cuando exista una versión
validada publicada. El gate independiente de alias TMDb sigue bloqueando esa publicación.
