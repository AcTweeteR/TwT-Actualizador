# AcTweeteR 0.4.17 — estable

**Paquetes:** skin 1.2.15 · servicio 0.4.17 · repositorio 1.0.3 · XStream Pro 1.1.2.1.
Baseline previsto: Kodi 21.3 Omega.

## Cambios

- Configurador inicial reanudable, con textos de bienvenida en español y
  preparación del proveedor Xtream sin mandar contraseñas a logs propios.
- Trakt se ofrece mediante el flujo oficial de autorización por dispositivo,
  o se puede posponer. Una autorización detectada localmente no se presenta
  como prueba de sincronización.
- La revisión XStream 1.1.2.1 permite recibir las correcciones de actualización
  de catálogo, callback y PVR mediante el actualizador de Kodi. Conserva datos
  y ajustes, y la versión 1.1.2 anterior permanece disponible para rollback.
- Los errores al iniciar la actualización del catálogo dejan reintentar sin
  volver a introducir las credenciales.

## Instalación

1. Instala Kodi 21.3 desde la fuente oficial.
2. Activa «Orígenes desconocidos» en Kodi y confirma su advertencia.
3. Añade como fuente `https://actweeter.github.io/TwT-Actualizador/bootstrap/`
   e instala `repository.actweeter-1.0.3.zip` desde esa fuente.
4. Desde **Instalar desde repositorio → AcTweeteR Repository → Apariencia →
   Skin**, instala AcTweeteR. Confirma las solicitudes nativas de Kodi y su
   activación de la skin.
5. En el configurador, introduce servidor, usuario y contraseña Xtream. Autoriza
   Trakt con el flujo del complemento oficial o selecciona «Más tarde».

Guía detallada: [Instalación en Kodi](https://actweeter.github.io/TwT-Actualizador/INSTALLATION_ALL_IN_ONE_ES.html).

## Alcance y limitaciones conocidas

- 510 pruebas automatizadas PASS. **No equivalen a pruebas runtime.** La
  instalación limpia, actualización y ejecución de este candidato no se han
  probado en Apple TV, Android TV ni otras plataformas. La primera validación
  externa prevista es Apple TV con Kodi 21.3.
- Continúa abierta una incidencia de cierre normal de Kodi: se han observado
  trabajos de directorio `plugin://` al cancelar trabajos del administrador,
  pero no se aisló la ruta responsable ni se validó una corrección. Se publica
  esta versión estable por decisión del propietario; este problema sigue
  pendiente y no se afirma que esté resuelto.
- La autenticación y sincronización Trakt reales no se han validado con una
  cuenta. La sincronización remota de listas/colección y su presentación en
  widgets AcTweeteR no forman parte de esta versión.
- No se declara reproducción nueva de IPTV, VOD, PVR, EPG ni tráiler con estos
  paquetes. El bridge de preview SlyGuy solicita consentimiento y aplica una
  integración local reversible a la versión soportada; no se redistribuye
  código SlyGuy y no se garantiza compatibilidad con futuras versiones suyas.
- En tvOS se depende de los componentes binarios que incluya Kodi oficial.
  Instalación, PVR y reproducción requieren prueba en el dispositivo.
- XStream Pro conserva CC BY-NC 4.0. La distribución es para uso no comercial,
  con atribución, licencia y aviso de modificaciones; no cuenta con respaldo
  del autor upstream. Consulta [avisos de terceros](THIRD_PARTY_NOTICES.md).

Los fallos de dependencias deben permanecer visibles en Kodi; no se desactivan
las confirmaciones ni las protecciones de la plataforma.
