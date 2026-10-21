"""Kodi adapters for Smart Search. Read-only catalogue/EPG and existing TMDb routes."""
from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
import json
from pathlib import Path
import re
import time
from urllib.parse import parse_qs, urlencode, urlsplit

from smart_search_engine import CatalogSearch, normalize, readonly, unique_rows, words
from search_background import xstream_profile_number

TMDB_HELPER = "plugin.video.tmdb.bingie.helper"


def rpc(kodi, method, params=None):
    request = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        request["params"] = params
    response = json.loads(kodi.executeJSONRPC(json.dumps(request)))
    if "error" in response:
        raise RuntimeError("Kodi method unavailable: " + method)
    return response.get("result", {})


def context(addon_factory, vfs, kodi=None):
    if kodi is not None and not kodi.getCondVisibility("System.AddonIsEnabled(plugin.video.xstream-pro)"):
        raise ValueError("provider addon is disabled")
    addon = addon_factory("plugin.video.xstream-pro")
    number = xstream_profile_number(addon.getSetting("active_profile") or "Profile 1")
    root = Path(vfs.translatePath(addon.getAddonInfo("profile")))
    return str(root), number


def catalogue(scope):
    root, number = scope
    if not root or not Path(root).is_absolute():
        raise ValueError("provider profile unavailable")
    return CatalogSearch(Path(root) / ("provider_search_%d.sqlite" % number), number)


def provider_children(kodi, parent, scope):
    """Browse only XStream's returned season/episode routes, without synthesizing playback URLs."""
    parsed = urlsplit(parent.get("path", ""))
    query = parse_qs(parsed.query)
    profile = str(scope[1])
    if (parsed.scheme != "plugin" or parsed.netloc != "plugin.video.xstream-pro" or
            query.get("mode", [""])[0] not in ("xtream_series", "xtream_season") or
            query.get("profile_num") != [profile]):
        raise ValueError("invalid provider series destination")
    series = query.get("series_id", [""])[0]
    if not series.isdigit():
        raise ValueError("invalid provider series identity")
    result = rpc(kodi, "Files.GetDirectory", {"directory": parent["path"], "media": "video",
        "properties": ["title", "year", "plot", "art", "season", "episode"],
        "limits": {"start": 0, "end": 100}})
    rows = []
    for item in result.get("files", []):
        path = item.get("file", "")
        target = urlsplit(path)
        params = parse_qs(target.query)
        if target.scheme != "plugin" or target.netloc != "plugin.video.xstream-pro":
            continue
        mode = params.get("mode", [""])[0]
        if mode == "xtream_season":
            if params.get("series_id") != [series] or params.get("profile_num") != [profile]:
                continue
            kind, season, episode = "season", params.get("season_num", [""])[0], ""
        elif mode == "source_select" and params.get("tmdb_type") == ["tv"]:
            kind = "episode"
            season, episode = params.get("season", [""])[0], params.get("episode", [""])[0]
        else:
            continue
        if not season.isdigit() or (kind == "episode" and not episode.isdigit()):
            continue
        art = item.get("art") or {}
        rows.append(dict(kind=kind, id="provider:%s:%s:%s" % (series, season, episode),
            title=item.get("title") or item.get("label") or "", plot=item.get("plot") or "",
            year=item.get("year") or "", poster=art.get("poster") or art.get("thumb") or parent.get("poster", ""),
            fanart=art.get("fanart") or parent.get("fanart", ""), available=True, path=path,
            season=int(season), episode=int(episode) if episode else -1,
            subtitle="Temporada " + season if kind == "season" else "T%s · E%s" % (season, episode)))
    return unique_rows(rows)


def metadata_row(item):
    path = item.get("file", "")
    parsed = urlsplit(path)
    if parsed.scheme != "plugin" or parsed.netloc != TMDB_HELPER:
        return None
    query = parse_qs(parsed.query)
    kind = {"movie": "movie", "tv": "series", "person": "person"}.get(
        query.get("tmdb_type", [""])[0])
    identity = query.get("tmdb_id", [""])[0]
    if kind is None or not identity.isdigit():
        return None
    art = item.get("art") or {}
    title = item.get("title") or item.get("label") or ""
    return dict(kind=kind, tmdb_id=identity, id="tmdb:" + identity, title=title,
                originaltitle=item.get("originaltitle", ""), year=item.get("year", ""),
                genre=item.get("genre") or [], director=item.get("director") or [],
                cast=item.get("cast") or [], rating=item.get("rating") or 0,
                plot=item.get("plot", ""), poster=art.get("poster") or art.get("profile") or art.get("thumb", ""),
                fanart=art.get("fanart", ""), path=path, available=False)


class Metadata:
    def __init__(self, kodi, clock=time.monotonic, *, alias_api_key=""):
        self.kodi, self.clock, self.cache = kodi, clock, OrderedDict()
        self.alias_cache = OrderedDict()
        self.alias_api_factory = None
        self.alias_api_key = alias_api_key if isinstance(alias_api_key, str) and re.fullmatch(r"[0-9a-fA-F]{32}", alias_api_key) else ""
        self.retry_after, self.alias_retry_after = 0, 0

    def _directory(self, params):
        key = tuple(sorted((str(k), str(v)) for k, v in params.items()))
        cached = self.cache.get(key)
        if cached and self.clock() - cached[0] < 600:
            self.cache.move_to_end(key)
            return [dict(row) for row in cached[1]]
        if self.clock() < self.retry_after:
            raise RuntimeError("metadata source cooling down")
        path = "plugin://" + TMDB_HELPER + "/?" + urlencode(dict(params, widget="true"))
        try:
            result = rpc(self.kodi, "Files.GetDirectory", {
                "directory": path, "media": "video", "properties":
                ["title", "originaltitle", "year", "plot", "art", "genre", "director", "cast", "rating"],
                "limits": {"start": 0, "end": 100},
            })
        except RuntimeError:
            self.retry_after = self.clock() + 10
            raise
        rows = unique_rows(row for item in result.get("files", []) if (row := metadata_row(item)))
        self.cache[key] = (self.clock(), rows)
        while len(self.cache) > 24:
            self.cache.popitem(last=False)
        return [dict(row) for row in rows]

    def search(self, query):
        return self._directory({"info": "search", "tmdb_type": "both", "query": query})

    def details(self, item):
        identity, kind = str(item.get("tmdb_id", "")), item.get("kind")
        if not identity.isdigit() or kind not in ("movie", "series", "person"):
            return item
        rows = self._directory({"info": "details", "tmdb_type":
            {"movie": "movie", "series": "tv", "person": "person"}[kind], "tmdb_id": identity})
        row = next((row for row in rows if row["kind"] == kind and row["tmdb_id"] == identity), None)
        if row:
            # Metadata may enrich a provider result, never replace its destination/availability.
            return dict(item, **{key: row[key] for key in
                ("plot", "originaltitle", "genre", "director", "cast", "rating", "poster", "fanart")
                if row.get(key)})
        return item

    def aliases(self, items, current=lambda: True, budget=3):
        """The exported API requires the user's own key; the helper's key is private."""
        if not self.alias_api_key or self.alias_api_factory is False:
            return items
        if self.alias_api_factory is None:
            try:
                from tmdbbingiehelper_lib.api.tmdb.api import TMDb
                self.alias_api_factory = TMDb
            except (ImportError, RuntimeError):
                self.alias_api_factory = False
                return items
        api, output = None, []
        for item in items:
            row = dict(item)
            kind = {"movie": "movie", "series": "tv"}.get(row.get("kind"))
            identity = str(row.get("tmdb_id", ""))
            key = kind, identity
            if kind and identity.isdigit() and current():
                if key not in self.alias_cache and budget and self.clock() >= self.alias_retry_after:
                    budget -= 1
                    try:
                        api = api or self.alias_api_factory(api_key=self.alias_api_key)
                        payload = api.get_request_lc(kind, identity, "alternative_titles") or {}
                        if not isinstance(payload, dict) or not isinstance(payload.get("titles", payload.get("results")), list):
                            raise ValueError("alias response unavailable")
                        self.alias_cache[key] = [r["title"] for r in
                            (payload.get("titles") or payload.get("results") or [])
                            if isinstance(r, dict) and isinstance(r.get("title"), str)][:80]
                        while len(self.alias_cache) > 64:
                            self.alias_cache.popitem(last=False)
                    except Exception:
                        self.alias_retry_after = self.clock() + 10
                if key in self.alias_cache:
                    row["aliases"] = list(self.alias_cache[key])
            output.append(row)
        return output

    def related(self, item, section, current=lambda: True):
        identity = str(item.get("tmdb_id", ""))
        kind = {"movie": "movie", "series": "tv"}.get(item.get("kind"))
        if not identity.isdigit() or not kind or section not in ("cast", "related"):
            return []
        rows = []
        for info in (("cast", "crew") if section == "cast" else ("recommendations", "similar")):
            if not current():
                break
            batch = self._directory({"info": info, "tmdb_type": kind, "tmdb_id": identity})
            if section == "cast":
                directors = item.get("director") or []
                if isinstance(directors, str):
                    directors = [directors]
                names = {normalize(name) for name in directors}
                for row in batch:
                    row["subtitle"] = "Dirección" if normalize(row["title"]) in names else "Reparto" if info == "cast" else "Equipo técnico"
            rows += batch
        if section == "cast":
            rows.sort(key=lambda row: row.get("subtitle") != "Dirección")
        return unique_rows(rows)

    def credits(self, person, current=lambda: True):
        identity = str(person.get("tmdb_id", ""))
        if not identity.isdigit():
            return []
        result, seen = [], set()
        for info in ("stars_in_movies", "stars_in_tvshows", "crew_in_movies", "crew_in_tvshows"):
            if not current():
                break
            for row in self._directory({"info": info, "tmdb_type": "person", "tmdb_id": identity}):
                key = row["kind"], row["tmdb_id"]
                if key not in seen:
                    result.append(row)
                    seen.add(key)
        return result


def _database(root, prefix):
    paths = [p for p in Path(root).glob(prefix + "*.db")
             if re.fullmatch(prefix + r"\d+\.db", p.name)]
    if not paths:
        raise FileNotFoundError("Kodi " + prefix + " database unavailable")
    return max(paths, key=lambda p: int(re.search(r"\d+", p.name).group()))


def programmes(database_root, query, now=None, limit=30, current=lambda: True):
    """Search Kodi 21's existing guide, never a provider request per channel.

    No database writes/migrations. A schema/platform mismatch is an explicit
    unavailable source in the UI, not an empty successful search.
    """
    terms = words(query)
    if not terms or not current():
        return []
    now = int(time.time() if now is None else now)
    with readonly(_database(database_root, "TV")) as tv:
        channels = {int(row[0]): (int(row[1]), row[2], row[3]) for row in tv.execute(
            "SELECT idEpg,idChannel,sChannelName,sIconPath FROM channels "
            "WHERE bIsHidden=0 AND bIsLocked=0 AND bIsRadio=0 AND bEPGEnabled=1")}
    if not channels:
        return []
    with readonly(_database(database_root, "Epg")) as db:
        db.set_progress_handler(lambda: 0 if current() else 1, 1000)
        db.create_function("search_match", 2, lambda epg, value:
            int(epg in channels and all(term in normalize(value) for term in terms)))
        rows = db.execute(
            "SELECT idBroadcast,idEpg,sTitle,sPlot,sIconPath,iStartTime,iEndTime "
            "FROM epgtags WHERE iEndTime>? AND iStartTime<? "
            "AND search_match(idEpg,coalesce(sTitle,'') || ' ' || coalesce(sCast,'') || ' ' || "
            "coalesce(sDirector,''))=1 "
            "ORDER BY search_match(idEpg,coalesce(sTitle,'')) DESC,iStartTime,idBroadcast LIMIT ?",
            (now, now + 7 * 86400, limit)).fetchall()
    result = []
    for broadcast, epg, title, plot, icon, start, end in rows:
        channel_id, channel_name, channel_icon = channels[int(epg)]
        live = start <= now < end
        when = datetime.fromtimestamp(start).strftime("%a %d · %H:%M")
        result.append(dict(kind="programme", id=str(broadcast), title=title or "",
            plot=plot or "", poster=icon or channel_icon or "", fanart="",
            subtitle=("AHORA · " if live else "") + channel_name + " · " + when,
            channel_id=channel_id, channel=channel_name, start=start, end=end,
            live=live, available=True))
    return result
