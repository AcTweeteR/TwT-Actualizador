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

from smart_search_engine import LatestRequest, MAX_QUERY, normalize, words
from smart_search_sources import Metadata, catalogue, context, programmes, rpc

ROWS = {5101: "movie", 5102: "series", 5103: "programme", 5104: "person", 5105: "discovery"}
KEYS = list("QWERTYUIOPASDFGHJKLÑZXCVBNM") + ["ESPACIO", "BORRAR", "LISTO"]


def listitem(row):
    item = xbmcgui.ListItem(label=row["title"], label2=str(row.get("subtitle") or
        row.get("year") or ("Persona" if row["kind"] == "person" else "")),
        path=row.get("path", ""))
    item.setArt({"poster": row.get("poster", ""), "thumb": row.get("poster", ""),
                 "fanart": row.get("fanart", ""), "icon": "DefaultVideo.png"})
    if row["kind"] in ("movie", "series"):
        tag = item.getVideoInfoTag()
        tag.setTitle(row.get("canonical_title") or row["title"])
        tag.setMediaType("movie" if row["kind"] == "movie" else "tvshow")
        tag.setPlot(row.get("plot", ""))
        year = str(row.get("year") or "")[:4]
        if year.isdigit():
            tag.setYear(int(year))
        if row.get("tmdb_id"):
            tag.setUniqueIDs({"tmdb": str(row["tmdb_id"])})
        item.setProperty("IsPlayable", "true" if row.get("available") and row["kind"] == "movie" else "false")
    item.setProperty("search.availability", "EN TU CATÁLOGO" if row.get("available") else
                     ("ACTORES Y CREADORES" if row["kind"] == "person" else "SOLO INFORMACIÓN · TMDb"))
    return item


class SearchWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stop = threading.Event()
        self.jobs, self.remote = LatestRequest(), LatestRequest()
        self.updates = queue.Queue(maxsize=12)
        self.ready = False
        self.rows = {key: [] for key in ROWS}
        self.serial, self.query, self.scope = 0, "", None
        self.person = None
        self.person_facet = "all"
        self.facet = "all"
        self.detail = None
        self.detail_origin = 100
        self.in_info = False
        self.metadata = Metadata(xbmc)
        self.monitor = xbmc.Monitor()

    def onInit(self):
        if self.ready:
            return
        self.ready = True
        self.setProperty("search.facet", "all")
        self.setProperty("search.status", "Un título, un actor, un director o un programa. Empieza a escribir.")
        self.getControl(120).addItems([xbmcgui.ListItem(label=key) for key in KEYS])
        self.setFocusId(100)
        for target in (self._local_worker, self._metadata_worker, self._pump):
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
                self._post(serial, "local", rows, (time.perf_counter() - started) * 1000)
            except (OSError, ValueError, RuntimeError, sqlite3.Error):
                self._post(serial, "local_error", [])
            if self.jobs.current(generation):
                try:
                    epg = programmes(xbmcvfs.translatePath("special://database"), query)
                    self._post(serial, "epg", epg)
                except (OSError, ValueError, RuntimeError, sqlite3.Error):
                    self._post(serial, "epg_error", [])

    def _metadata_worker(self):
        engine, previous = None, None
        while (job := self.remote.take()) is not None:
            generation, (serial, query, scope, person) = job
            current = lambda: self.remote.current(generation) and not self.stop.is_set()
            started = time.perf_counter()
            try:
                rows = self.metadata.credits(person, current) if person else self.metadata.search(query)
                if not current():
                    continue
                if not person:
                    people = [row for row in rows if row["kind"] == "person"]
                    self._post(serial, "people", people)
                    # A name search returns the person's available films as well as their card.
                    exact_person = next((p for p in people if normalize(p["title"]) == normalize(query)), None)
                    if exact_person and len(words(query)) > 1:
                        rows += self.metadata.credits(exact_person, current)
                if not current():
                    continue
                try:
                    if scope != previous:
                        engine, previous = catalogue(scope), scope
                    matched = engine.match_metadata(rows)
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
                self._post(serial, "metadata_error", [])

    def _clear_rows(self):
        for control in ROWS:
            self._fill(control, [])

    def _fill(self, control, rows):
        if self.stop.is_set():
            return
        rows = rows[:40]
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
        pending, changed_at, remote_sent, context_at = None, 0, False, 0
        last_selected = None
        try:
            while not self.stop.is_set() and not self.monitor.abortRequested():
                if self.in_info or self.detail:
                    self.stop.wait(0.08)
                    continue
                now = time.monotonic()
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
                    self.setProperty("search.person", "")
                if self.person and query != self.query:
                    self.person = None
                    self.setProperty("search.person", "")
                if (query != self.query or scope != self.scope) and not self.person:
                    self.query, self.scope = query, scope
                    self.serial += 1
                    self.jobs.invalidate()
                    # Invalidate previous metadata immediately, before the longer debounce.
                    self.remote.invalidate()
                    pending, changed_at, remote_sent = (self.serial, query, scope), now, False
                    self._clear_rows()
                    self.setProperty("search.hero.title", "")
                    self.setProperty("search.hero.plot", "")
                    self.setProperty("search.hero.art", "")
                    self.setProperty("search.epg", "")
                    self.setProperty("search.remote", "")
                    self.setProperty("search.status", "Buscando en tu catálogo…" if len(query) >= 2 else
                                     "Escribe al menos dos caracteres. Títulos, personas y programas, en un mismo lugar.")
                if pending and now - changed_at >= 0.20:
                    serial, text, source = pending
                    if len(text) >= 2:
                        self.jobs.submit((serial, text, source))
                    pending = None
                if self.query and not remote_sent and not self.person and now - changed_at >= 0.65:
                    if len(self.query) >= 2:
                        self.remote.submit((self.serial, self.query, self.scope, None))
                        self.setProperty("search.remote", "Consultando personas y títulos alternativos…")
                    remote_sent = True
                while not self.updates.empty():
                    serial, source, data, elapsed = self.updates.get_nowait()
                    if serial != self.serial:
                        continue
                    if source == "local":
                        for control, kind in ((5101, "movie"), (5102, "series")):
                            self._merge(control, [row for row in data if row["kind"] == kind])
                        count = len(data)
                        self.setProperty("search.status", "%d coincidencias en tu catálogo · %.0f ms" % (count, elapsed)
                                         if count else "Sin coincidencias locales. Buscando títulos alternativos…")
                    elif source == "local_error":
                        enabled = xbmc.getCondVisibility("System.AddonIsEnabled(plugin.video.xstream-pro)")
                        self.setProperty("search.status", "Índice del proveedor no disponible. Los metadatos siguen accesibles."
                                         if enabled else "XStream está deshabilitado. Puedes consultar personas, metadatos y la guía TV.")
                    elif source == "epg":
                        self._fill(5103, data)
                    elif source == "people":
                        self._fill(5104, data)
                    elif source == "metadata":
                        matched, other = data
                        for control, kind in ((5101, "movie"), (5102, "series")):
                            self._merge(control, [row for row in matched if row["kind"] == kind])
                        self._fill(5105, other)
                        self.setProperty("search.remote", "TMDb · Personas y títulos alternativos actualizados")
                    elif source == "metadata_error":
                        self.setProperty("search.remote", "Metadatos temporalmente no disponibles · tu catálogo sigue funcionando")
                    elif source == "epg_error":
                        self.setProperty("search.epg", "Guía EPG no disponible en esta sesión")
                    xbmc.log("[AcTweeteR] SEARCH source=%s elapsed_ms=%d" % (source, elapsed), xbmc.LOGDEBUG)
                try:
                    control = self.getFocusId()
                    if control in ROWS:
                        index = self.getControl(control).getSelectedPosition()
                        if (control, index) != last_selected and 0 <= index < len(self.rows[control]):
                            row = self.rows[control][index]
                            self.setProperty("search.hero.title", row.get("canonical_title") or row["title"])
                            self.setProperty("search.hero.plot", row.get("plot", "")[:380])
                            self.setProperty("search.hero.art", row.get("fanart") or row.get("poster", ""))
                            last_selected = control, index
                except (RuntimeError, IndexError):
                    pass
                self.stop.wait(0.08)
        except Exception as exc:
            xbmc.log("[AcTweeteR] SEARCH source=window error_type=" + type(exc).__name__, xbmc.LOGERROR)
        finally:
            self.jobs.close()
            self.remote.close()

    def onClick(self, control):
        if self.detail and control not in (701, 702, 703):
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
            self.setFocusId(120 if opened else 100)
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
                self.person = row
                self.person_facet, self.facet = self.facet, "all"
                self.setProperty("search.facet", "all")
                self.serial += 1
                self.jobs.invalidate()
                self._clear_rows()
                self.setProperty("search.person", row["title"])
                self.setProperty("search.hero.title", row["title"])
                self.setProperty("search.hero.plot", row.get("plot") or "Filmografía · títulos disponibles en tu catálogo y otras obras")
                self.setProperty("search.hero.art", row.get("poster", ""))
                self.setProperty("search.remote", "Cargando filmografía de " + row["title"] + "…")
                self.remote.submit((self.serial, self.query, self.scope, row))
                self.setFocusId(104)
            elif row["kind"] == "programme" or not row.get("available"):
                self._show_detail(row)
            else:
                self.in_info = True
                try:
                    xbmcgui.Dialog().info(listitem(row))
                finally:
                    self.in_info = False
        elif control == 702:
            self.detail = None
            self.setProperty("search.detail", "false")
            self.setFocusId(self.detail_origin)
        elif control == 701 and self.detail and self.detail.get("live"):
            row = self.detail
            self._shutdown()
            rpc(xbmc, "Player.Open", {"item": {"channelid": row["channel_id"]}})

    def _show_detail(self, row):
        self.detail_origin = self.getFocusId()
        self.detail = row
        self.setProperty("search.detail.title", row["title"])
        self.setProperty("search.detail.plot", row.get("plot", ""))
        self.setProperty("search.detail.art", row.get("poster", ""))
        subtitle = "TMDb · Biografía" if row["kind"] == "person" else "TMDb · Disponibilidad sin confirmar en tu proveedor"
        self.setProperty("search.detail.subtitle", row.get("subtitle") or subtitle)
        self.setProperty("search.detail.live", "true" if row.get("live") else "false")
        self.setProperty("search.detail", "true")
        self.setFocusId(702)

    def _back(self):
        if self.detail:
            self.onClick(702)
        elif self.getProperty("search.keyboard") == "true":
            self.setProperty("search.keyboard", "false")
            self.setFocusId(100)
        elif self.person:
            self.person = None
            self.facet = self.person_facet
            self.setProperty("search.facet", self.facet)
            self.setProperty("search.person", "")
            self.query = ""  # Re-run the previous query, retaining the edit text.
            self.setFocusId(100)
        else:
            self._shutdown()

    def onAction(self, action):
        if action.getId() in (10, 92, 216, 247):
            self._back()

    def _shutdown(self):
        self.stop.set()
        self.jobs.close()
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
        window.doModal()
    finally:
        window.stop.set()
        window.jobs.close()
        window.remote.close()
        home.clearProperty("AcTweeteR.SearchOpen")
        del window
    if xbmc.getCondVisibility("Window.IsActive(1109)"):
        xbmc.executebuiltin("Action(Back)")


if __name__ == "__main__":
    run()
