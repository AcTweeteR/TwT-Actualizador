"""AcTweeteR's visual search window. No provider/profile writes or autoplay."""
from __future__ import annotations

import queue
import sqlite3
import threading
import time
from pathlib import Path

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from smart_search_engine import LatestRequest, MAX_QUERY, normalize, unique_rows, words
from smart_search_sources import Metadata, catalogue, context, programmes, provider_children, rpc

ROWS = {5101: "movie", 5102: "series", 5103: "programme", 5104: "person", 5105: "discovery"}
KEYS = list("QWERTYUIOPASDFGHJKLÑZXCVBNM") + ["ESPACIO", "BORRAR", "LISTO"]


def listitem(row):
    item = xbmcgui.ListItem(label=row["title"], label2=str(row.get("subtitle") or
        row.get("year") or ("Persona" if row["kind"] == "person" else "")),
        path=row.get("path", ""))
    item.setArt({"poster": row.get("poster", ""), "thumb": row.get("poster", ""),
                 "fanart": row.get("fanart", ""), "icon": "DefaultVideo.png"})
    if row["kind"] in ("movie", "series", "season", "episode"):
        tag = item.getVideoInfoTag()
        tag.setTitle(row.get("canonical_title") or row["title"])
        tag.setMediaType("tvshow" if row["kind"] == "series" else row["kind"])
        if row["kind"] in ("season", "episode"):
            tag.setSeason(row["season"])
            tag.setEpisode(row["episode"])
        tag.setPlot(row.get("plot", ""))
        genre, directors = row.get("genre") or [], row.get("director") or []
        tag.setGenres([genre] if isinstance(genre, str) else genre)
        tag.setDirectors([directors] if isinstance(directors, str) else directors)
        cast = row.get("cast") or []
        if cast:
            tag.setCast([xbmc.Actor(name=person["name"], role=person.get("role", ""),
                order=person.get("order", n), thumbnail=person.get("thumbnail", ""))
                for n, person in enumerate(cast) if isinstance(person, dict) and person.get("name")])
        year = str(row.get("year") or "")[:4]
        if year.isdigit():
            tag.setYear(int(year))
        if row.get("tmdb_id"):
            tag.setUniqueIDs({"tmdb": str(row["tmdb_id"])})
        item.setProperty("IsPlayable", "true" if row.get("available") and row["kind"] in ("movie", "episode") else "false")
    item.setProperty("search.availability", "EN TU CATÁLOGO" if row.get("available") else
                     ("ACTORES Y CREADORES" if row["kind"] == "person" else "SOLO INFORMACIÓN · TMDb"))
    item.setProperty("search.badge", "TV / EPG" if row["kind"] == "programme" else
                     "PERSONA" if row["kind"] == "person" else "EN IPTV" if row.get("available") else "TMDb")
    item.setProperty("path", row.get("path", ""))
    return item


class SearchWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stop = threading.Event()
        self.jobs, self.remote = LatestRequest(), LatestRequest()
        self.epg_jobs = LatestRequest()
        self.updates = queue.Queue(maxsize=12)
        self.ready = False
        self.rows = {key: [] for key in ROWS}
        self.serial, self.query, self.scope = 0, "", None
        self.rows_serial = 0
        self.person = None
        self.person_facet = "all"
        self.history = []
        self.facet = "all"
        self.detail = None
        self.detail_origin = 100
        self.in_info = False
        self.info_can_launch = False
        self.info_close_requested = False
        self.suspended = False
        self.resume_positions = {}
        self.keyboard_focus_pending = False
        self.metadata = Metadata(xbmc)
        self.shared_index = None
        self.monitor = xbmc.Monitor()

    def onInit(self):
        if self.ready:
            if self.suspended:
                rows = self.rows
                self.rows = {key: [] for key in ROWS}
                self.getControl(100).setText(self.query)
                self.getControl(120).reset()
                self.getControl(120).addItems([xbmcgui.ListItem(label=key) for key in KEYS])
                for control, values in rows.items():
                    self._fill(control, values)
                    if values:
                        self.getControl(control).selectItem(self.resume_positions.get(control, 0))
                self.setFocusId(701 if self.detail else 100)
                self.suspended = False
            return
        self.ready = True
        self.setProperty("search.facet", "all")
        self.setProperty("search.series.heading", "Series · en tu catálogo")
        self.setProperty("search.status", "Un título, un actor, un director o un programa. Empieza a escribir.")
        self.getControl(120).addItems([xbmcgui.ListItem(label=key) for key in KEYS])
        self.setFocusId(100)
        for target in (self._local_worker, self._epg_worker, self._metadata_worker, self._pump):
            threading.Thread(target=target, daemon=True).start()

    def _post(self, serial, source, data, elapsed=0):
        if self.stop.is_set():
            return
        try:
            self.updates.put_nowait((serial, source, data, elapsed))
        except queue.Full:
            pass  # Stale completions are expendable; never block a Kodi worker on a closed UI.

    def _local_worker(self):
        engine, previous = None, None
        while (job := self.jobs.take()) is not None:
            generation, (serial, query, scope) = job
            if not self.jobs.current(generation):
                continue
            started = time.perf_counter()
            try:
                if scope != previous:
                    engine, previous = catalogue(scope), scope
                rows = engine.search(query)
                self.shared_index = engine.fork()
                self._post(serial, "local", rows, (time.perf_counter() - started) * 1000)
            except (OSError, ValueError, RuntimeError, sqlite3.Error):
                self._post(serial, "local_error", [])

    def _epg_worker(self):
        while (job := self.epg_jobs.take()) is not None:
            generation, (serial, query) = job
            current = lambda: self.epg_jobs.current(generation) and not self.stop.is_set()
            try:
                epg = programmes(xbmcvfs.translatePath("special://database"), query, current=current)
                if current():
                    self._post(serial, "epg", epg)
            except (OSError, ValueError, RuntimeError, sqlite3.Error):
                if current():
                    self._post(serial, "epg_error", [])

    def _metadata_worker(self):
        engine, previous = None, None
        while (job := self.remote.take()) is not None:
            generation, (serial, query, scope, person) = job
            current = lambda: self.remote.current(generation) and not self.stop.is_set()
            started = time.perf_counter()
            try:
                if person and person.get("_section") == "provider":
                    rows = provider_children(xbmc, person, scope)
                    if current():
                        self._post(serial, "children", rows)
                    continue
                if person and person.get("_section") == "details":
                    detail = self.metadata.details(person)
                    if current():
                        self._post(serial, "detail", detail)
                    continue
                if person and person["kind"] != "person":
                    rows = self.metadata.related(person, person["_section"], current)
                else:
                    rows = self.metadata.credits(person, current) if person else self.metadata.search(query)
                if not current():
                    continue
                people = [row for row in rows if row["kind"] == "person"]
                self._post(serial, "people", people)
                if not person:
                    # A name search returns the person's available films as well as their card.
                    exact_person = next((p for p in people if normalize(p["title"]) == normalize(query)), None)
                    if exact_person and len(words(query)) > 1:
                        rows += self.metadata.credits(exact_person, current)
                if not current():
                    continue
                try:
                    if scope != previous:
                        engine, previous = catalogue(scope), scope
                    shared = self.shared_index
                    if shared and shared.path == engine.path and shared.profile == engine.profile:
                        engine = shared.fork()
                    matched = engine.match_metadata(rows)
                    matched_ids = {(row["kind"], row.get("tmdb_id")) for row in matched}
                    unmatched = [row for row in rows if row["kind"] in ("movie", "series") and
                                 (row["kind"], row.get("tmdb_id")) not in matched_ids]
                    if current() and unmatched:
                        matched += engine.match_metadata(self.metadata.aliases(unmatched, current))
                except (OSError, ValueError, RuntimeError, sqlite3.Error):
                    matched = []
                matched_ids = {(row["kind"], row.get("tmdb_id")) for row in matched}
                other = [row for row in rows if row["kind"] in ("movie", "series")
                         and (row["kind"], row.get("tmdb_id")) not in matched_ids]
                self._post(serial, "metadata", (matched, other), (time.perf_counter() - started) * 1000)
            except Exception as exc:
                # Kodi cannot cancel an in-flight plugin directory request. Only the latest
                # generation can publish; failures never clear already visible local results.
                xbmc.log("[AcTweeteR] SEARCH source=metadata error_type=" + type(exc).__name__, xbmc.LOGWARNING)
                self._post(serial, "provider_error" if person and person.get("_section") == "provider" else "metadata_error", [])

    def _clear_rows(self):
        for control in ROWS:
            self._fill(control, [])

    def _fill(self, control, rows):
        if self.stop.is_set():
            return
        rows = unique_rows(rows)[:40]
        if rows == self.rows[control]:
            return
        listing = self.getControl(control)
        index = listing.getSelectedPosition()
        previous = self.rows[control]
        selected = previous[index].get("id") if 0 <= index < len(previous) else None
        self.rows[control] = rows
        listing.reset()
        listing.addItems([listitem(row) for row in self.rows[control]])
        if selected:
            position = next((i for i, row in enumerate(rows) if row.get("id") == selected), 0)
            listing.selectItem(position)
        self.setProperty("search.count." + ROWS[control], str(len(self.rows[control])))
        self._visibility()

    def _visibility(self):
        for control, kind in ROWS.items():
            visible = bool(self.rows[control]) and (self.facet == "all" or self.facet == kind)
            self.setProperty("search.show." + kind, "true" if visible else "false")

    def _merge(self, control, new):
        previous = self.rows[control]
        by_id = {(row["kind"], row["id"]): row for row in previous}
        for row in new:
            by_id[row["kind"], row["id"]] = row
        self._fill(control, list(by_id.values()))

    def _pump(self):
        pending, changed_at, remote_sent, epg_sent, context_at = None, 0, False, False, 0
        last_selected = None
        try:
            while not self.stop.is_set() and not self.monitor.abortRequested():
                if self.in_info or self.suspended:
                    self._handoff_info_playback()
                    self.stop.wait(0.08)
                    continue
                now = time.monotonic()
                self._focus_keyboard_if_ready()
                query = self.getControl(100).getText()[:MAX_QUERY].strip()
                scope = self.scope
                if now >= context_at:
                    try:
                        scope = context(xbmcaddon.Addon, xbmcvfs, xbmc)
                    except Exception:
                        scope = ("", 1)
                    context_at = now + 1
                if scope != self.scope:
                    self.person = None
                    self.history.clear()
                    self.detail = None
                    self.setProperty("search.detail", "false")
                    self.setProperty("search.person", "")
                if self.person and query != self.query:
                    self.person = None
                    self.history.clear()
                    self.setProperty("search.person", "")
                if (query != self.query or scope != self.scope) and not self.person:
                    clear = scope != self.scope or len(query) < 2
                    self.query, self.scope = query, scope
                    self.serial += 1
                    self.jobs.invalidate()
                    self.epg_jobs.invalidate()
                    # Invalidate previous metadata immediately, before the longer debounce.
                    self.remote.invalidate()
                    pending, changed_at, remote_sent, epg_sent = (self.serial, query, scope), now, False, False
                    if clear:
                        self._clear_rows()
                    self.setProperty("search.loading", "true" if len(query) >= 2 else "false")
                    self.setProperty("search.hero.title", "")
                    self.setProperty("search.hero.plot", "")
                    self.setProperty("search.hero.art", "")
                    self.setProperty("search.epg", "")
                    self.setProperty("search.remote", "")
                    self.setProperty("search.status", "Buscando en tu catálogo…" if len(query) >= 2 else
                                     "Escribe al menos dos caracteres. Títulos, personas y programas, en un mismo lugar.")
                if pending and now - changed_at >= 0.12:
                    serial, text, source = pending
                    if len(text) >= 2:
                        self.jobs.submit((serial, text, source))
                    pending = None
                if self.query and not epg_sent and not self.person and now - changed_at >= 0.45:
                    if len(self.query) >= 2:
                        self.epg_jobs.submit((self.serial, self.query))
                    epg_sent = True
                if self.query and not remote_sent and not self.person and now - changed_at >= 0.65:
                    if len(self.query) >= 2:
                        self.remote.submit((self.serial, self.query, self.scope, None))
                        self.setProperty("search.remote", "Consultando personas y títulos alternativos…")
                    remote_sent = True
                while not self.updates.empty():
                    serial, source, data, elapsed = self.updates.get_nowait()
                    if serial != self.serial:
                        continue
                    if source != "detail" and self.rows_serial != self.serial:
                        self._clear_rows()
                        self.rows_serial = self.serial
                        self.setProperty("search.loading", "false")
                    if source == "local":
                        for control, kind in ((5101, "movie"), (5102, "series")):
                            self._merge(control, [row for row in data if row["kind"] == kind])
                        count = len(data)
                        self.setProperty("search.status", "%d coincidencias en tu catálogo · %.0f ms" % (count, elapsed)
                                         if count else "Sin coincidencias por título en IPTV. Consulta personas, guía y TMDb.")
                        self.setProperty("search.local_ready_ms", str(round((time.monotonic() - changed_at) * 1000)))
                    elif source == "local_error":
                        enabled = xbmc.getCondVisibility("System.AddonIsEnabled(plugin.video.xstream-pro)")
                        self.setProperty("search.status", "Índice del proveedor no disponible. Los metadatos siguen accesibles."
                                         if enabled else "XStream está deshabilitado. Puedes consultar personas, metadatos y la guía TV.")
                    elif source == "epg":
                        self._fill(5103, data)
                    elif source == "detail":
                        if self.detail and data.get("id") == self.detail.get("id"):
                            self._show_detail(data, remember=False)
                    elif source == "people":
                        self._fill(5104, data)
                    elif source == "children":
                        self._fill(5102, data)
                        self.setProperty("search.remote", "%d elementos · rutas del proveedor" % len(data))
                    elif source == "provider_error":
                        self.setProperty("search.remote", "No se pudieron cargar las temporadas o episodios. Puedes volver y reintentar.")
                    elif source == "metadata":
                        matched, other = data
                        for control, kind in ((5101, "movie"), (5102, "series")):
                            self._merge(control, [row for row in matched if row["kind"] == kind])
                        self._fill(5105, other)
                        self.setProperty("search.remote", "TMDb · Resultados y personas actualizados")
                    elif source == "metadata_error":
                        self.setProperty("search.remote", "Metadatos temporalmente no disponibles · tu catálogo sigue funcionando")
                    elif source == "epg_error":
                        self.setProperty("search.epg", "Guía EPG no disponible en esta sesión")
                    xbmc.log("[AcTweeteR] SEARCH source=%s elapsed_ms=%d" % (source, elapsed), xbmc.LOGDEBUG)
                try:
                    control = self.getFocusId()
                    if control in ROWS:
                        index = self.getControl(control).getSelectedPosition()
                        if 0 <= index < len(self.rows[control]):
                            row = self.rows[control][index]
                            signature = control, index, row.get("id"), row.get("canonical_title"), row.get("plot")
                            if signature == last_selected:
                                self.stop.wait(0.08)
                                continue
                            self.setProperty("search.hero.title", row.get("canonical_title") or row["title"])
                            self.setProperty("search.hero.plot", row.get("plot", "")[:380])
                            self.setProperty("search.hero.art", row.get("fanart") or row.get("poster", ""))
                            last_selected = signature
                            self.setProperty("search.hero.availability", row.get("canonical_title") and
                                "EN TU CATÁLOGO · título identificado" or
                                ("EN TU CATÁLOGO" if row.get("available") else "TMDb · disponibilidad sin confirmar"))
                except (RuntimeError, IndexError):
                    pass
                self.stop.wait(0.08)
        except Exception as exc:
            xbmc.log("[AcTweeteR] SEARCH source=window error_type=" + type(exc).__name__, xbmc.LOGERROR)
        finally:
            self.jobs.close()
            self.epg_jobs.close()
            self.remote.close()

    def onClick(self, control):
        if self.detail and control not in (701, 702, 703, 704, 705, 707):
            return
        if control == 101:
            value = xbmcgui.Dialog().input("Buscar · teclado del dispositivo / dictado si está disponible",
                defaultt=self.getControl(100).getText(), type=xbmcgui.INPUT_ALPHANUM)
            if value:
                self.person = None
                self.getControl(100).setText(value[:MAX_QUERY])
        elif control == 102:
            self.person = None
            self.getControl(100).setText("")
            self.setFocusId(100)
        elif control == 103:
            opened = self.getProperty("search.keyboard") != "true"
            self.setProperty("search.keyboard", "true" if opened else "false")
            self.keyboard_focus_pending = opened
            self.setFocusId(103 if opened else 100)
        elif control == 104:
            self._back()
        elif control == 105 and self.person:
            self._show_detail(self.person)
        elif 111 <= control <= 116:
            self.facet = ("all", "movie", "series", "programme", "person", "discovery")[control - 111]
            self.setProperty("search.facet", self.facet)
            self._visibility()
        elif control == 120:
            key = KEYS[self.getControl(120).getSelectedPosition()]
            text = self.getControl(100).getText()
            if key == "LISTO":
                self.setProperty("search.keyboard", "false")
                self.setFocusId(100)
            else:
                self.person = None
                self.getControl(100).setText((text[:-1] if key == "BORRAR" else
                    text + (" " if key == "ESPACIO" else key.lower()))[:MAX_QUERY])
        elif control in ROWS:
            position = self.getControl(control).getSelectedPosition()
            if not 0 <= position < len(self.rows[control]):
                return
            row = self.rows[control][position]
            if row["kind"] == "person":
                self._browse(row)
            elif row["kind"] == "season":
                self._browse(row, "provider")
            else:
                self._show_detail(row)
                if row.get("tmdb_id"):
                    self.remote.submit((self.serial, self.query, self.scope, dict(row, _section="details")))
        elif control == 702:
            self.detail = None
            self.setProperty("search.detail", "false")
            self.setFocusId(self.detail_origin)
        elif control in (704, 705) and self.detail and self.detail.get("tmdb_id"):
            self._browse(self.detail, "cast" if control == 704 else "related")
        elif control == 707 and self.detail and self.detail.get("available") and self.detail["kind"] == "series":
            self._browse(self.detail, "provider")
        elif control == 701 and self.detail and self.detail.get("available") and self.detail["kind"] in ("movie", "series", "episode"):
            if context(xbmcaddon.Addon, xbmcvfs, xbmc) != self.scope:
                self.setProperty("search.detail.subtitle", "El perfil ha cambiado. Vuelve a buscar antes de reproducir.")
                return
            self.info_can_launch = not xbmc.Player().isPlayingVideo()
            self.info_close_requested = False
            self.in_info = True
            try:
                xbmcgui.Dialog().info(listitem(self.detail))
            finally:
                self.in_info = False
                if self.info_can_launch and xbmc.Player().isPlayingVideo():
                    self.resume_positions = {key: self.getControl(key).getSelectedPosition() for key in ROWS}
                    self.suspended = True
                    self.close()
                    xbmc.executebuiltin("ActivateWindow(fullscreenvideo)")
        elif control == 701 and self.detail and self.detail.get("live"):
            row = self.detail
            self._shutdown()
            rpc(xbmc, "Player.Open", {"item": {"channelid": row["channel_id"]}})

    def _handoff_info_playback(self):
        # Native info can remain modal after Play; close it only for video started in this context.
        if self.in_info and self.info_can_launch and not self.info_close_requested and xbmc.Player().isPlayingVideo():
            self.info_close_requested = True
            xbmc.executebuiltin("Dialog.Close(movieinformation)")

    def _focus_keyboard_if_ready(self):
        if self.keyboard_focus_pending and xbmc.getCondVisibility("Control.IsVisible(120)"):
            self.keyboard_focus_pending = False
            self.setFocusId(120)

    def _show_detail(self, row, remember=True):
        if remember:
            self.detail_origin = self.getFocusId()
        self.detail = row
        self.setProperty("search.detail.title", row["title"])
        original = row.get("originaltitle", "")
        genre = row.get("genre") or []
        if isinstance(genre, str):
            genre = [genre]
        directors = row.get("director") or []
        if isinstance(directors, str):
            directors = [directors]
        text = ("Título original: " + original + "\n\n" if original and original != row["title"] else "")
        text += (" · ".join(str(g) for g in genre) + "\n\n" if genre else "")
        text += ("Dirección: " + ", ".join(directors) + "\n\n" if directors else "") + row.get("plot", "")
        self.setProperty("search.detail.plot", text)
        self.setProperty("search.detail.art", row.get("poster", ""))
        subtitle = "TMDb · Biografía" if row["kind"] == "person" else "TMDb · Disponibilidad sin confirmar en tu proveedor"
        self.setProperty("search.detail.subtitle", row.get("subtitle") or subtitle)
        if row.get("available") and row["kind"] in ("movie", "series", "episode"):
            self.setProperty("search.detail.subtitle", "EN TU CATÁLOGO · " + str(row.get("year") or ""))
        self.setProperty("search.detail.content", "true" if row["kind"] in ("movie", "series") else "false")
        self.setProperty("search.detail.related", "true" if row.get("tmdb_id") and row["kind"] in ("movie", "series") else "false")
        self.setProperty("search.detail.play", "true" if row.get("available") and row["kind"] in ("movie", "series", "episode") else "false")
        self.setProperty("search.detail.seasons", "true" if row.get("available") and row["kind"] == "series" else "false")
        self.setProperty("search.detail.action", "Ver canal en directo" if row.get("live") else
                         "Ficha y reproducción" if row["kind"] in ("movie", "episode") else "Ficha y temporadas")
        self.setProperty("search.detail.live", "true" if row.get("live") else "false")
        self.setProperty("search.detail", "true")
        if remember:
            self.setFocusId(702)

    def _browse(self, row, section=None):
        self.history.append((self.person, self.facet, {k: list(v) for k, v in self.rows.items()},
                             {k: self.getControl(k).getSelectedPosition() for k in ROWS},
                             self.detail_origin if self.detail else self.getFocusId()))
        # shortcut: retain eight exploration levels; extend only if real navigation needs more.
        self.history = self.history[-8:]
        self.detail = None
        self.setProperty("search.detail", "false")
        self.person, self.facet = dict(row, _section=section), "all"
        self.serial += 1
        self.jobs.invalidate()
        self.epg_jobs.invalidate()
        self._clear_rows()
        self.setProperty("search.facet", "all")
        self.setProperty("search.person", row["title"])
        self.setProperty("search.subject.label", "Biografía" if row["kind"] == "person" else "Ficha")
        self.setProperty("search.series.heading", "Temporadas" if section == "provider" and row["kind"] == "series" else
                         "Episodios" if section == "provider" else "Series · en tu catálogo")
        self.setProperty("search.hero.title", row["title"])
        self.setProperty("search.hero.plot", "Reparto y equipo" if section == "cast" else
                         "Temporadas y episodios del proveedor" if section == "provider" else
                         "Títulos relacionados" if section else row.get("plot", "Filmografía"))
        self.setProperty("search.status", "Explorando · " + row["title"])
        self.setProperty("search.hero.art", row.get("fanart") or row.get("poster", ""))
        self.setProperty("search.remote", "Cargando…")
        self.remote.submit((self.serial, self.query, self.scope, self.person))
        self.setFocusId(104)

    def _back(self):
        if self.detail:
            self.onClick(702)
        elif self.getProperty("search.keyboard") == "true":
            self.keyboard_focus_pending = False
            self.setProperty("search.keyboard", "false")
            self.setFocusId(100)
        elif self.person and self.history:
            self.serial += 1
            self.remote.invalidate()
            self.person, self.facet, rows, positions, focus = self.history.pop()
            self.setProperty("search.facet", self.facet)
            self.setProperty("search.person", self.person["title"] if self.person else "")
            self.setProperty("search.subject.label", "Biografía" if self.person and self.person["kind"] == "person" else "Ficha")
            self.setProperty("search.series.heading", "Temporadas" if self.person and self.person.get("_section") == "provider" and self.person["kind"] == "series" else
                             "Episodios" if self.person and self.person.get("_section") == "provider" else "Series · en tu catálogo")
            for control, values in rows.items():
                self._fill(control, values)
                if values:
                    self.getControl(control).selectItem(positions[control])
            self.setProperty("search.hero.title", "")
            self.setProperty("search.hero.plot", "")
            self.setProperty("search.hero.art", "")
            self.setProperty("search.status", "Explorando · " + self.person["title"] if self.person else
                             "Resultados · " + self.query)
            self.setProperty("search.remote", "Resultados restaurados · sin repetir consultas")
            self.setFocusId(focus)
        elif self.person:
            self.person = None
            self.query = ""
            self.setProperty("search.person", "")
            self.setFocusId(100)
        else:
            self._shutdown()

    def onAction(self, action):
        if action.getId() in (10, 92, 216, 247):
            self._back()

    def _shutdown(self):
        self.stop.set()
        self.jobs.close()
        self.epg_jobs.close()
        self.remote.close()
        self.close()


def run():
    # A launcher remains compatible with existing user-owned BUSCAR shortcuts.
    home = xbmcgui.Window(10000)
    if home.getProperty("AcTweeteR.SearchOpen") == "true":
        return
    home.setProperty("AcTweeteR.SearchOpen", "true")
    root = str(Path(__file__).resolve().parents[2])
    window = SearchWindow("AcTweeteRSearch.xml", root, "Default", "1080i")
    try:
        while not window.stop.is_set() and not window.monitor.abortRequested():
            window.doModal()
            if not window.suspended:
                break
            while xbmc.Player().isPlayingVideo() and not window.monitor.abortRequested():
                window.monitor.waitForAbort(0.1)
    finally:
        window.stop.set()
        window.jobs.close()
        window.epg_jobs.close()
        window.remote.close()
        home.clearProperty("AcTweeteR.SearchOpen")
        del window
    if xbmc.getCondVisibility("Window.IsActive(1109)"):
        xbmc.executebuiltin("Action(Back)")


if __name__ == "__main__":
    run()
