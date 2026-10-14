# AcTweeteR 0.4.21 — Trakt, recomendaciones y evidencia de plataforma

Documento de alcance y verificación del release. Las pruebas automatizadas y estáticas no se presentan como validación runtime.

## Portable widget layout and migration

Movie and Series hub default order is:

1. Continue Watching
2. Recently Added
3. Trending
4. Popular
5. Recommendations for You (present in defaults; the route returns no items
   until XStream is authorized and exact provider matches exist)
6. Current-year premieres
7. Previous-year premieres
8. Remaining provider catalog/category/favorites rows

Release skin 1.2.18 supplies the native XStream movie and TV routes. Service
0.4.21 advances the versioned layout migration to v7 while retaining previous
layout migrations. Backups remain profile-local, repeat application is
idempotent, and detected user edits are preserved unless consent is given.
Portable `shortcuts/*.DATA.xml` files are the source; generated includes from
a personal Kodi profile are not packaged.

The distributed XStream 1.1.2.2 package is built from the pinned upstream 1.1.2
archive plus hash-checked AcTweeteR patches. Its recommendation-specific
filter accepts only exact TMDb IDs in the active provider's movie/show
availability cache. It fails closed when the cache is absent, authorization
is missing, the match is ambiguous/unavailable, the TMDb media type is invalid,
or results are empty. The widget directory call never performs a network
catalogue rebuild; the asynchronous XStream profile refresh owns that work and
its callback refreshes the Kodi container only after success. It does not
depend on `tmdb_provider_only_available`, whose general behavior is not a
sufficient strictness guarantee. Kodi's widget templates collapse empty
containers. No manual widget edits/reinstall are intended. This is
implementation and automated evidence, not runtime UI proof.

## Trakt ownership

Trakt is optional. The official `script.trakt` add-on remains the only owner of
Kodi playback scrobbling/library sync. XStream remains the owner of its native
recommendations, account lists, history, watchlist, collection and resume
features. AcTweeteR does not implement a third client, copy tokens, inspect
private add-on settings, or duplicate playback scrobbling. Its setup can finish
without either authorization.

The exact upstream package and all patch hashes are verified by the package
builder; automated tests inspect the generated package and route integration.
The source has native Device Code functions and non-empty upstream-bundled app
credentials which XStream itself uses as fallback. AcTweeteR neither prints nor
copies these values. The authorization flow and recommendation rendering have
not been tested at runtime, and AcTweeteR cannot inspect XStream's private
token/status. No claim of successful authorization is made.

New-series/new-episode badges remain based on the prior provider-ID baseline
implementation. They are preserved; this release does not alter that logic.
The existing XStream `XStream.ChangeStatus` provider-ID state remains the badge
source in Poster, Landscape and Square cards; this release adds no new badge
heuristics or polling.

## Compatibility matrix

| Platform | Structural/package evidence | Runtime for this candidate |
| --- | --- | --- |
| macOS | Shared Python/XML, Kodi VFS paths — `PASS_STATIC` | `NOT_TESTED` |
| Windows | Shared Python/XML, Kodi VFS paths — `PASS_STATIC` | `NOT_TESTED` |
| Linux | Shared Python/XML, Kodi VFS paths — `PASS_STATIC` | `NOT_TESTED` |
| Android / Android TV / Google TV | Shared Python/XML; binary add-ons depend on Kodi build — `PASS_STATIC` | `NOT_TESTED` |
| tvOS / Apple TV | Kodi VFS/native repository design — `PASS_STATIC` | `NOT_TESTED` |

Automated tests can cover XML order, optional setup gates, migration backup and
idempotence, and package metadata. They cannot prove rendering, OAuth,
recommendation matching, playback, or cross-platform runtime.

## Release gate

La incidencia crítica de cierre de Kodi/plugin:// continúa abierta y no está corregida. El propietario autorizó expresamente aceptar ese riesgo para 0.4.21 únicamente. XStream Pro 1.1.2.2 se publica respetando CC BY-NC 4.0, atribución, enlace y aviso de modificaciones; queda prohibido el uso comercial. OAuth, renderizado real de recomendaciones e instalación limpia/actualización en dispositivos permanecen `NOT_TESTED`.
