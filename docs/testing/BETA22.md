# Beta22 — Trakt, Arcade e indicadores vistos

## Paquetes Testing

- XStream Pro `1.1.2.28~beta20` (sin cambios).
- Service AcTweeteR `0.4.84`.
- Skin AcTweeteR `1.2.32~beta9`.
- Bootstrap de repositorio oficial `repository.zachmorris 1.0.4`; IAGL se obtiene y actualiza desde ese repositorio.
- SHA-256: Service `f5f8cab17fa1de5d82d5702106e7acb685954b9bea64ffb674268c7743467adc`; Skin `edb1fb33b7d6d2297990ee9a2a9e6c94a6ba8e71b4d6b040f7d980162865b8d2`; XStream `18641e3c240ca2f75a15acb6fcf717618d93ee16677405d94b72ef64f384da71`; Zach Morris `3dde8f37dcd64f122cf1e897e139e5b8b7a3cd0ec15db6a1f5c7b59852cb661b`.
- Índice Testing SHA-256 `be4ce18d8f80463d794a3eccfa557be36993968b588a715e91cbda4d18dee9fd`; `addons.xml.md5` SHA-256 `52d010e4f8e4b6eeb820b8078c9d89b399a1b3a6f24bec9eb7da970c445d1a35`.

## Cambios

Service instala el bootstrap del repositorio Zach Morris por el gestor nativo, refresca los repositorios y espera a que Kodi descubra IAGL antes de solicitar su instalación por el mismo mecanismo nativo que Rivulet. IAGL conserva sus datos de usuario; la instalación no descarga juegos ni ROMs. Skin agrega `ARCADE` después de `RIVULET`; migración de Skin Shortcuts conserva las elecciones existentes e inserta la entrada por `defaultID`, para que persista tras regenerar el menú.

## Trakt y checks

La auditoría estática asigna scrobbling y sincronización de biblioteca Kodi al complemento `script.trakt`; XStream conserva OAuth, endpoints de UI y su proyección local de vistos/progreso en propiedades nativas Kodi; Service hace importación autenticada de solo lectura, resolución exacta de identidades y puente explícito de acciones solicitadas. Coexisten mecanismos de sincronización y no se retiraron almacenes ni funciones. No se hicieron escrituras remotas a Trakt. Las seis operaciones ambiguas previamente identificadas siguen pendientes: cinco episodios sin identidad externa inequívoca y una reanudación sin referencia exacta de reproducción.

XStream aplica `playcount`/resume a películas y episodios con identidades verificadas. La completitud de series/temporadas depende de inventario de episodios vigente y completo, y falla cerrada si falta o está incompleto. La skin consume propiedades nativas para checks y progreso. Código y pruebas automatizadas pasan; el renderizado real en Kodi Mac debe validarse tras instalar.

## Clasificación

- Paquetes, XML, AST, CRC, checksums, suite y matrices de responsabilidades: `PASS_AUTOMATED` / `PASS_STATIC`.
- Instalación, apertura de `ARCADE`, persistencia visual, Rivulet, Trakt en vivo, indicadores en superficies Kodi, PVR y reproducción: `NOT_TESTED` hasta la comprobación runtime posterior a la publicación.
- Mac es la única plataforma objetivo de validación runtime en esta misión. Compatibilidad Android/tvOS es estática; disponibilidad de núcleos RetroPlayer depende de cada plataforma. No se descargan ROMs en la prueba.

## Fuentes upstream

IAGL: [repositorio oficial](https://github.com/zach-morris/plugin.program.iagl); bootstrap: [repository.zachmorris](https://github.com/zach-morris/repository.zachmorris). La licencia del complemento es GPL-3.0; sus bases de datos suplementarias tienen términos CC BY-NC 4.0.
