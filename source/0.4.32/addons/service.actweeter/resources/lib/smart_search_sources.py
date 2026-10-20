"""Kodi adapters for Smart Search. Read-only catalogue/EPG and existing TMDb routes."""
from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
import json
from pathlib import Path
import re
import time
from urllib.parse import parse_qs, urlencode, urlsplit

from smart_search_engine import CatalogSearch, normalize, readonly, words
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
                plot=item.get("plot", ""), poster=art.get("poster") or art.get("profile") or art.get("thumb", ""),
                fanart=art.get("fanart", ""), path=path, available=False)


class Metadata:
    def __init__(self, kodi, clock=time.monotonic):
        self.kodi, self.clock, self.cache = kodi, clock, OrderedDict()

    def _directory(self, params):
        key = tuple(sorted((str(k), str(v)) for k, v in params.items()))
        cached = self.cache.get(key)
        if cached and self.clock() - cached[0] < 600:
            self.cache.move_to_end(key)
            return [dict(row) for row in cached[1]]
        path = "plugin://" + TMDB_HELPER + "/?" + urlencode(dict(params, widget="true"))
        result = rpc(self.kodi, "Files.GetDirectory", {
            "directory": path, "media": "video", "properties":
            ["title", "originaltitle", "year", "plot", "art"],
            "limits": {"start": 0, "end": 100},
        })
        rows = [row for item in result.get("files", []) if (row := metadata_row(item))]
        self.cache[key] = (self.clock(), rows)
        while len(self.cache) > 24:
            self.cache.popitem(last=False)
        return [dict(row) for row in rows]

    def search(self, query):
        return self._directory({"info": "search", "tmdb_type": "both", "query": query})

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


def programmes(database_root, query, now=None, limit=30):
    """Search Kodi 21's existing guide, never a provider request per channel.

    No database writes/migrations. A schema/platform mismatch is an explicit
    unavailable source in the UI, not an empty successful search.
    """
    terms = words(query)
    if not terms:
        return []
    now = int(time.time() if now is None else now)
    with readonly(_database(database_root, "TV")) as tv:
        channels = {int(row[0]): (int(row[1]), row[2], row[3]) for row in tv.execute(
            "SELECT idEpg,idChannel,sChannelName,sIconPath FROM channels "
            "WHERE bIsHidden=0 AND bIsLocked=0 AND bIsRadio=0 AND bEPGEnabled=1")}
    if not channels:
        return []
    with readonly(_database(database_root, "Epg")) as db:
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
