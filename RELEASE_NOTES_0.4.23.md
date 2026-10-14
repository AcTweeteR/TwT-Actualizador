# AcTweeteR 0.4.23 — estable

**Kodi 21.3 Omega · Skin 1.2.18 · Servicio 0.4.23 · Repositorio 1.0.3 · XStream Pro 1.1.2.4**

## Cambios

XStream Pro 1.1.2.4 propaga metadatos identificativos de películas y episodios
al ListItem reproducible, incluyendo `mediatype` e IDs conocidos, y expone
`script.trakt.ids` para la integración soportada por script.trakt 3.9.0. No se
añade una integración OAuth o un cliente de scrobbling propio. No se alteran las
URL de reproducción, cabeceras, subtítulos ni el estado de reanudación de
XStream. El servicio 0.4.23 declara la versión de XStream compatible; la skin y
el repositorio permanecen en 1.2.18 y 1.0.3.

La actualización no migra ni sobrescribe credenciales, autorizaciones, favoritos,
historial o progreso. Se conservan los paquetes históricos para recuperación.

## Integridad y licencias

Los cuatro ZIP se verificaron contra el candidato privado autorizado y sus
SHA-256. XStream conserva `LICENCE.txt`, atribución, enlace CC BY-NC 4.0 y el
aviso `ACTWEETER_MODIFICATIONS.txt`. Distribución no comercial; no hay aval del
autor upstream. Véase [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Validación y limitaciones

- 553 pruebas automatizadas PASS.
- ZIP/CRC, Python AST, XML, addons.xml, MD5 y SHA-256: PASS_AUTOMATED.
- Reproducción real y scrobbling mediante script.trakt: **NOT_TESTED**.
- Runtime Kodi en Apple TV/tvOS, Android, macOS, Windows y Linux: **NOT_TESTED**
  para esta versión.
- La incidencia crítica de cierre de Kodi durante trabajos `plugin://` continúa
  abierta; su causa sigue sin identificarse. El propietario aceptó expresamente
  ese riesgo solo para publicar 0.4.23; no se considera resuelta.

## Instalar o actualizar

Instalación limpia: añade `https://actweeter.github.io/TwT-Actualizador/bootstrap/`,
instala `repository.actweeter-1.0.3.zip` desde Kodi y luego instala AcTweeteR
desde el repositorio.

Actualización: refresca el repositorio oficial y actualiza AcTweeteR mediante
Kodi. No borres el perfil ni reinstales complementos manualmente.
