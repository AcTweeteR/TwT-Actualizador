# WorldTV — LauncherM3U en AcTweeteR (Beta, 2026-11-06)

WorldTV NO es un segundo proveedor PVR ni un widget. El elemento WorldTV del
submenú lateral de TV ejecuta **RunAddon(plugin.video.launcherm3u)** y abre el
addon de vídeo LauncherM3U, autónomo y separado de IPTV Simple Client.

## Origen y licencias

- Addon upstream: https://github.com/entreunosyceros/launcherm3u,
  snapshot Git 02e9bfc, versión 1.3.3 (GPL-2.0-or-later).
- Archivo fuente íntegro (con LICENSE):
  source/0.4.32/third_party/worldtv/launcherM3U-1.3.3-upstream.zip.
- SHA-256 de ese archivo:
  4fe218d404218f2f65b46ee6d2307c53fbebd936fe91e232f4e4cdc109edbcd1.
- La Beta crea una versión derivada 1.3.3~beta1 que cambia solo ajustes
  iniciales, metadatos y normalización tvg-id @SD/@HD para XMLTV.
- IPTV-org (URL M3U por países):
  https://iptv-org.github.io/iptv/index.country.m3u
- Fuente XMLTV independiente, sin copiar sus datos al repositorio:
  https://raw.githubusercontent.com/teleonline/listas/main/epg.xml.gz

El 6 de noviembre de 2026 la lista tenía 12.972 entradas en 189 grupos.
No es una cifra de streams reproducibles. La fuente de guía teleonline
incluía 2.406 canales XMLTV y únicamente ~70 IDs idénticos al quitar el sufijo
de calidad a los IDs IPTV-org. Por tanto, la EPG es **parcial**; no anunciar
una guía completa ni asignar programas ambiguos por título. XMLTV requiere red.
Las fuentes y datos pueden cambiar, bloquearse o desaparecer.

## Instalación y actualización

- Skin Beta 1.2.43~beta1 -> Service >= 0.4.103~beta1 -> LauncherM3U
  >= 1.3.3~beta1, dependencia Kodi declarada, resuelta por Kodi.
- Los tres ZIP y el índice checksum están en docs/testing/repo.
- Kodi instala y actualiza por su repositorio Testing estándar; no copiar
  directamente addons instalados ni modificar la base de Addons.
- Ajustes M3U y XMLTV quedan precargados en el propio paquete, con
  actualización de lista cada 12 horas y autocarga XMLTV.
- El Service configura instalaciones preexistentes de LauncherM3U **solo si
  la lista estaba vacía o ya era la URL WorldTV**. Si el addon contiene una
  lista distinta, se preservan todos sus ajustes. Nunca se modifican los
  ajustes de pvr.iptvsimple ni la fuente EPG del proveedor.
- La migración de Skin Shortcuts a v21 incorpora el único submenú WorldTV,
  conserva los elementos antiguos y otros accesos personalizados, crea copia
  de seguridad y evita duplicar WorldTV. Puede requerir regeneración de Skin
  Shortcuts la primera vez tras actualizar.
- No hay widgets de WorldTV, ni cambios en Inicio, Películas, Series,
  Spotlight, grabaciones o en el PVR existente.

## Limitaciones de la Beta

- Sin prueba visual confirmada en Kodi Mac, Lenovo o Apple TV hasta ejecutar
  la instalación estándar en cada plataforma.
- La cobertura XMLTV es escasa; Kodi seguirá mostrando canales sin programa.
- La app utiliza un único feed XMLTV, no fusiona guías de 189 países.
- Las URLs de streams pueden fallar, requerir región o contener publicidad.
- No se prueba ni garantiza ninguna cifra de canales efectivamente
  reproducibles.
- Upstream auto-installer de ZIP permanece desactivado: mantener las
  actualizaciones bajo control del repositorio de Kodi y sus verificaciones.

## Reproducir

python3.11 tools/build_worldtv_beta.py

Este comando crea paquetes únicamente si no existen; rechaza sobreescritura
y requiere el checksum del archivo fuente pinneado.
