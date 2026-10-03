# TwT-Actualizador — distribución AcTweeteR

Este repositorio es **público** y funciona exclusivamente como canal de distribución/actualización de AcTweeteR.

## Regla absoluta

**CERO SECRETOS.** Nunca publicar credenciales, usuarios de proveedores, contraseñas, tokens, cookies, API keys, URLs privadas, M3U/EPG privadas, userdata personal ni configuraciones exportadas desde iCloud.

## Modelo

- Desarrollo y código canónico: `AcTweeteR/TweeteR-Kodi` (privado).
- Distribución: `AcTweeteR/TwT-Actualizador` (público).
- Provisioning privado: iCloud Drive/`actweeter kodi`.

El Mac es el entorno master de desarrollo, build y validación.

## Publicación continua desde desarrollo

No esperar a que AcTweeteR esté terminado para empezar a distribuir.

Cada unidad de trabajo suficientemente instalable y validada debe poder producir un paquete/candidate para probarlo en Apple TV y demás dispositivos.

Canales previstos:

- `dev`: builds frecuentes para validación cruzada.
- `beta`: candidates que han pasado regresión principal en Mac.
- `stable`: releases consideradas aptas para uso normal.

Una build dev nunca debe promocionarse automáticamente a stable.

## Repositorio Kodi

Aprovechar el mecanismo nativo de repositorios Kodi siempre que sea posible:

- `addons.xml`
- checksum
- paquetes ZIP versionados
- repository addon instalable una sola vez

Objetivo: tras instalar una vez el repositorio AcTweeteR, las actualizaciones posteriores llegan mediante el sistema de addons de Kodi.

## Manifest propio

Mantener además manifests legibles por AcTweeteR para compatibilidad, canales, componentes y futuras plataformas.

Ejemplo conceptual:

```json
{
  "version": "x.y.z",
  "channel": "dev|beta|stable",
  "kodi": ["21", "22"],
  "components": {}
}
```

## Changelog post-update

Cada release debe incluir changelog estructurado.

AcTweeteR debe guardar localmente la última versión cuyo changelog fue mostrado.

Al primer arranque posterior a una actualización:

```
installed_version != last_changelog_seen
→ abrir changelog
→ marcar versión como vista
```

En los siguientes arranques no debe volver a abrirse automáticamente.

Debe existir una opción manual para consultar posteriormente las novedades.

No mostrar automáticamente changelog en instalación inicial salvo decisión expresa futura.

## Rollback

Conservar artefactos de versiones anteriores y hashes para permitir diagnóstico/rollback controlado.

## Integridad

Generar SHA-256 de artefactos publicados. El pipeline debe impedir la publicación si detecta secretos o artefactos no saneados.

## iCloud provisioning

NO se publica aquí. El provisioning privado vive en iCloud Drive/`actweeter kodi`.



## Política temporal de publicación

Durante la fase de desarrollo intensivo:

1. Publicar **ahora**, antes de la reuse audit, una primera versión instalable con el estado funcional actual y saneado de AcTweeteR.
2. Después de esa primera publicación, **no publicar por cada cambio ni por cada commit**.
3. Las siguientes publicaciones serán **manuales**, únicamente cuando el propietario del proyecto lo solicite expresamente.
4. Codex puede seguir desarrollando, probando y haciendo commits en el repositorio privado sin generar una actualización pública.
5. Cuando el proyecto alcance una versión estable, se migrará a publicación automática. La política exacta de automatización se definirá entonces; no activar todavía publicación automática por commit.

La primera publicación debe hacerse antes de comenzar la auditoría reuse-first, pero solo después de verificar que el artefacto es instalable y no contiene secretos.
