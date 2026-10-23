# Contrato Trakt y catálogo — candidato privado 2026-10-23

Rama: `codex/trakt-unified-beta-2026-10-22`, continuación de `cabd460`.
Candidatos: Service 0.4.59 y XStream 1.1.2.28~beta1. Skin sin cambios.
No instalar, publicar, hacer push ni aplicar datos automáticamente.

## Correcciones

- El contenedor de exportación avanza a schema 2; el snapshot normalizado sigue
  con schema 1. El manifest declara contract_version 2 y complete solo después
  de GET completos, cabeceras page/limit/page-count/item-count y las dos barreras
  de cuenta y actividad. Se conserva únicamente el slug necesario de settings.
- Exportador, importador y XStream comparten el mismo `trakt_sync.py` byte a byte.
  `validate_export` reproduce el transcript completo y compara los datos
  normalizados y los recuentos. Un checksum o un flag no prueban completitud.
- Exportaciones v1: se verifica el transcript sin modificar el archivo original.
  Al no conservar item-count ni las respuestas de cuenta, requieren una referencia
  v2 reciente, íntegra, de la misma cuenta/perfil y con estado exactamente igual.
  Una captura antigua diferente se preserva pero no se promueve a completa.
- `trakt.snapshot_request` permite solo GET de los endpoints de snapshot y nunca
  renueva OAuth mediante POST. Las rutas de exportación, ciclo, binding y consumo
  de lotes utilizan este transporte; el cliente ordinario no cambia.
- El índice de películas incorpora IDs tipados del catálogo vigente, VOD details
  y metadatos cacheados; filtra pertenencia y contradicciones. Categorías repetidas
  con el mismo provider ID no son versiones distintas. Los IDs contradictorios
  se rechazan, no se resuelven por título.
- Las series usan catálogo, metadatos, series_info e inventarios existentes.
  Los episodios requieren una serie exacta, inventario completo, coordenadas e ID
  explícitos. Se conservan duración y tipado; no se infieren episodios ni URLs.
- El consumidor comparte esos lectores y verifica el origen del catálogo contra
  la huella de proveedor vigente. Ya no rechaza todos los catálogos que superen el
  antiguo límite arbitrario de 32 MB ni exige que cada ID aparezca una sola vez
  entre categorías.
- La validación de cada lote abre la evidencia una sola vez. Si hay un índice
  lateral de offsets válido, los elementos solicitados se leen por offsets en modo
  SQLite de solo lectura. Ausente, obsoleto o corrupto: fallback al JSON original;
  nunca se construye un índice desde este consumidor.
- `preview_changes` calcula adiciones reales y se comparte entre UI y productor
  de lotes. Vistos ya presentes y avances más recientes/desconocidos se conservan.
  Un estado explícitamente no visto no se confirma falsamente como aplicado.
- El checkpoint incorpora generación de catálogo/metadatos y versión de planner.
  Cambios de identidad reevalúan elementos antes no identificados aunque Trakt no
  cambie. La comprobación usa stat, no deserialización completa cada cinco minutos.
  Si solo cambia el catálogo se reutiliza el último export verificado; un export
  cacheado inválido se recupera con una lectura nueva, nunca con un plan vacío.
- Se revalida el binding antes de consumir y después de exportar. No se aplica
  durante reproducción ni ante cambios de cuenta/perfil/proveedor. La cola y los
  recibos conservan su coordinación durable existente y no avanzan checkpoints
  sin confirmación.
- La UI ordena snapshots cronológicamente, no por el nombre aleatorio del directorio.

## Herramientas de solo lectura

Todos los destinos deben estar fuera del repositorio y de Kodi, en directorios
privados. No contienen consentimiento ni invocan al consumidor de datos reales.

```sh
python3 tools/export_trakt_readonly_mac.py --output /ruta/privada/export
python3 tools/prepare_trakt_catalog_mac.py --export /ruta/privada/export/snapshot-ID --output /ruta/privada/catalogo --with-translations
python3 tools/preview_trakt_mac.py --export /ruta/privada/export/snapshot-ID --catalog /ruta/privada/catalogo --output /ruta/privada/previsualizacion
python3 tools/benchmark_trakt_catalog_gate.py --catalog /ruta/privada/catalogo --operations /ruta/privada/previsualizacion/private-operations.json --output /ruta/privada/gate.json
```

El descubrimiento copia evidencia existente a una cápsula privada; las traducciones
TMDb solo dirigen consultas de detalles por título/año exacto. **Jamás constituyen
identidad para marcar visto**. Solo IDs externos del proveedor permiten casar
contenido. Se limita la concurrencia y se detiene el lote si el proveedor no
responde a la primera prueba; no se lanzan cientos de timeouts.

Un registro sin correspondencia en `import_plan.unavailable` conserva ese nombre
histórico de API, pero significa falta de identidad exacta, no ausencia demostrada
en el proveedor. El informe de previsualización lo clasifica como metadata_pending y
availability_unknown. No se contabiliza como contenido no disponible confirmado.

## Verificación y paquetes

Las pruebas nuevas usan exclusivamente IDs, títulos, URLs y respuestas sintéticas.
Cubren tres formas históricas sin flags, prueba v2, truncación final, repetición de
páginas, cambio de cuenta/perfil, manifest falso, índices completos/obsoletos,
series/episodios no materializados, referencia cacheada corrupta, origen del
proveedor, deltas y preservación de avances. Se conserva toda la suite anterior.

Ejecutar sin omitir integración con las clases de XStream reales:

```sh
ACTWEETER_XSTREAM_UPSTREAM_ZIP=/ruta/upstream-fijado.zip \
ACTWEETER_XSTREAM_TEST_ZIP=/ruta/candidato-xstream.zip \
ACTWEETER_XSTREAM_LIVE_ZIP=/ruta/candidato-xstream.zip \
python3 -m unittest discover -s source/0.4.32/tests -q
```

El constructor comprueba rutas, hashes de fuentes/parches/runtime, sintaxis, CRC,
licencia y contrato. Service 0.4.59 exige XStream 1.1.2.28~beta1. El manifest privado
final debe señalar los dos ZIP reproducibles. Los feeds públicos y Stable no cambian.

## Limitaciones y puerta de autorización

- La cobertura depende de IDs exactos del proveedor; los catálogos pueden carecer
  de ellos y requerir consultas dirigidas. Sin conexión al proveedor no se infiere
  disponibilidad por título ni se afirma una recuperación completa.
- Los lectores completos tienen un coste de memoria proporcional al catálogo.
  Se evita repetirlos cuando no cambian actividad ni evidencia; la ruta acotada
  de consumo puede aprovechar SQLite sin otra base de datos.
- Los tests de ciclo, persistencia, acuses y refresco son aislados. Sin instalación
  autorizada no demuestran el recorrido visual del candidato dentro de Kodi.
- La autenticación del lector estricto no renueva tokens por sí sola: OAuth se
  mantiene en el flujo nativo separado. Un token expirado se rechaza; nunca se
  convierte en una colección vacía.
- Antes de la primera aplicación: conectividad del proveedor, identidades actuales,
  export nuevo íntegro, preview contra stores actuales, backups verificados y
  autorización explícita. Mantener sync automático desactivado durante instalación
  y QA. No aplicar el lote solo por haber pasado las pruebas.

## Comprobación local final

- Commit funcional: `6ec526b`.
- 493 pruebas y 45 subtests correctos, sin fallos, errores ni omisiones.
- Suite repetida con Python 3.11: 493 correctas, cero omisiones.
- 78 fuentes Python parseadas; `git diff --check` correcto.
- Service 0.4.59 SHA-256: `872ce8e1f353348d3f3831219f1dc17fc375c18a3347095db74a7d7c119eef36`.
- XStream 1.1.2.28~beta1 SHA-256: `aaa471919b104ffa2d8a635a6c4e90ff1eb0e572cc4d4df09be6b7d995032657`.
- Dos builds idénticos por paquete, CRC correcto y cinco módulos de contrato
  compartidos byte a byte. No se cambió la skin ni se instalaron paquetes.
- 133 archivos Stable y los feeds Testing permanecen iguales a la base.
- Evidencias privadas fuera del repositorio. El informe operativo distingue
  cobertura confirmada de candidatos que aún requieren metadatos del proveedor.
- Sin push ni CI remoto: solo verificaciones locales reproducibles.

## Continuación: lectura autorizada y vista previa — 2026-10-23

- Se obtuvo un snapshot nuevo mediante el exportador nativo en modo GET: contrato
  v2, completo, 3.235 eventos, 1.830 registros y cero sin identificar. SHA-256 del
  snapshot: `89852713f8d0f2fe0f5cc1f52931e85e5a9d35a80d2c01c2dbf7e941585de231`.
  Se mantuvo en `/private/tmp`; no se hizo POST ni se renovó OAuth.
- Las exportaciones v1 históricas se volvieron a contrastar sin editarlas: dos
  coinciden exactamente con una referencia v2 fresca de la misma cuenta/perfil;
  una difiere y se rechaza fail-closed. No se añadió un indicador `complete` a
  ninguna exportación histórica.
- La previsualización de diez muestras leyó los almacenes activos en solo lectura
  y verificó que sus hashes no cambiaron. Propuso 2 películas vistas nuevas y 2
  actualizaciones de avance; 38 películas ya estaban vistas, 8 avances locales se
  conservarían y 1 avance queda diferido. No propuso episodios vistos ni avances
  nuevos. Cero escrituras locales o remotas.
- Cobertura observada: catálogos actuales con 13.003 IDs de películas y 5.117 de
  series; identidad externa verificada para 172 películas y 121 series, y 35
  episodios exactos. De 1.830 registros Trakt, 1.787 siguen sin identidad exacta
  suficiente; se clasifican como pendientes/availability unknown, nunca como
  ausentes. Los listados completos no equivalen a metadatos de identidad completos.
- Con autorización del usuario se inició el descubrimiento dirigido, limitado a
  285 GET Xtream como máximo y concurrencia 3 (274 candidatos de película y 11
  de serie). El único probe intentado no obtuvo respuesta HTTP: DNS resolvió,
  pero la conexión TCP al endpoint configurado agotó el tiempo. El guard detuvo
  la operación antes de lanzar el lote; no se registraron credenciales ni URL y
  no se consultó TMDb. Resultado: 0 respuestas de proveedor, 0 IDs adicionales
  verificados. La cobertura no puede ampliarse hasta que el endpoint vuelva a ser
  accesible desde el Mac.
- Por seguridad, el extractor ahora copia los catálogos como proyecciones de
  campos de identidad, con `_src` redactado, excluyendo URL y credenciales. Además
  omite GET de películas cuya identidad externa ya está verificada y tiene un
  límite codificado de 285. Dos pruebas nuevas cubren redacción/lectura y el
  límite de candidatos ya verificados. La cápsula resultante es modo 0700 y todos
  sus archivos modo 0600; el escaneo encontró cero credenciales o URL del
  proveedor.
- Suite completa posterior a la corrección: 495 pruebas PASS, cero fallos y cero
  omisiones, con integración al ZIP XStream candidato 1.1.2.28~beta1 y al ZIP
  upstream fijado. No se reconstruyeron ni instalaron paquetes: los únicos cambios
  son a la herramienta de descubrimiento y sus pruebas, no al código de addons.
- Medición de preview (10 muestras, Mac): wall p50/p90 418,889/426,799 ms; CPU
  p50/p90 418,564/426,550 ms; memoria máxima Python 77.841.511 bytes; comprobación
  de generación p50 1,298 ms. Es una medición de la etapa de preparación local, no
  de latencia visual ni una comparación antes/después.
- El primer intento de inspección DNS falló por un error de sintaxis en el comando
  de diagnóstico; no accedió al proveedor. La comprobación corregida posterior
  resolvió DNS. La prueba TCP fue solo de conectividad y no envió credenciales.
- No se activó consentimiento, no se consumió la cola, no se aplicaron estados,
  no se escribió en Trakt, no se instalaron candidatos y no se publicó nada.
