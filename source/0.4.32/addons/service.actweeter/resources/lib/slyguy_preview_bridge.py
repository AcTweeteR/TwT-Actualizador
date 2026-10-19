"""SlyGuy-context worker for AcTweeteR's serialized automatic previews.

This module is imported by the SlyGuy Trailers service, so SlyGuy settings,
dependencies, and provider modules run in their owning add-on context. Network
resolution is isolated from Kodi's GUI thread; the provider service accepts at
most one resolver and only the latest queued request.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
import threading
from urllib.parse import parse_qs, unquote, urlparse


REQUEST_SENDER = "service.actweeter.SIGNAL"
RESULT_SENDER = "slyguy.trailers.SIGNAL"
MESSAGE = "actweeter_auto_preview"
_ANNOUNCEMENT_METHOD = "Other." + MESSAGE
_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{6,64}$")
_REQUEST_ID = re.compile(r"^[0-9a-f]{32}-[1-9][0-9]*$")


def _decode(data):
    try:
        envelope = json.loads(data) if isinstance(data, str) else data
        encoded = envelope[0] if isinstance(envelope, list) and envelope else None
        if not isinstance(encoded, str):
            return None
        payload = json.loads(base64.b64decode(encoded, validate=True).decode("utf-8"))
        return payload if isinstance(payload, dict) else None
    except (TypeError, ValueError, UnicodeError, binascii.Error):
        return None


def _send(xbmc, action, generation, status, request_id=""):
    payload = base64.b64encode(json.dumps(
        {"action": action, "generation": int(generation), "request_id": request_id,
         "status": status},
        separators=(",", ":"),
    ).encode("utf-8")).decode("ascii")
    request = {"jsonrpc": "2.0", "id": 1, "method": "JSONRPC.NotifyAll",
               "params": {"sender": RESULT_SENDER, "message": MESSAGE,
                          "data": [payload]}}
    xbmc.executeJSONRPC(json.dumps(request, separators=(",", ":")))


def _identity(data):
    for key in ("imdb", "tmdb", "dbid"):
        raw = data.get(key)
        value = raw.strip() if isinstance(raw, str) else ""
        if value and value.isascii() and value.isalnum():
            return key + ":" + value
    return ""


def preview_source(request):
    """Separate the selected episode identity from its parent trailer lookup."""
    media = request.get("media_type")
    if media not in ("movie", "tvshow", "season", "episode"):
        return None
    parent = media in ("season", "episode")
    ids = {key: request.get(("show_" if parent else "") + key)
           for key in ("imdb", "tmdb")
           if request.get(("show_" if parent else "") + key)}
    dbid = request.get("show_dbid" if parent else "dbid") or -1
    if parent and (not request.get("show_title") or
                   (not ids and (not str(dbid).isdigit() or int(dbid) < 0))):
        return None
    trailer_id = str(request.get("trailer_id") or "")
    return {
        "mediatype": "tvshow" if parent else media,
        "dbid": dbid,
        "title": request.get("show_title" if parent else "title") or "",
        "year": request.get("show_year" if parent else "year") or 0,
        "unique_ids": ids, "art": {},
        "trailer": ("https://www.youtube.com/watch?v=" + trailer_id
                    if not parent and _VIDEO_ID.fullmatch(trailer_id) else ""),
    }


def preview_target(path, get_youtube_id):
    parsed = urlparse(path)
    if parsed.scheme == "plugin" and parsed.netloc == "slyguy.trailers":
        identifier = (parse_qs(parsed.query).get("video_id") or [""])[0]
        if parsed.path.rstrip("/").endswith("/imdb"):
            return ("imdb", identifier) if re.fullmatch(r"tt\d+", identifier) else ("", "")
        if parsed.path.rstrip("/").endswith("/play") and _VIDEO_ID.fullmatch(identifier):
            return "youtube", identifier
        return "", ""
    if parsed.hostname in ("youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "plugin.video.youtube"):
        identifier = get_youtube_id(path) or ""
        if _VIDEO_ID.fullmatch(identifier):
            return "youtube", identifier
    return "", ""


def request_is_current(xbmc, request):
    """Revalidate the original Kodi window, focus, item identity and generation."""
    try:
        generation = int(request["generation"])
        window = int(request["window"])
        container = int(request["container"])
        focus = int(request["focus"])
        position = int(request["position"])
        if xbmc.getCondVisibility("Player.HasMedia"):
            return False
        if not xbmc.getCondVisibility("Window.IsActive(%d)" % window):
            return False
        if xbmc.getInfoLabel(
                "Window(Home).Property(ACTWEETER_AUTO_PREVIEW_REQUEST)") != request.get("request_id"):
            return False
        if int(xbmc.getInfoLabel("System.CurrentControlId") or "-1") != focus:
            return False
        if int(xbmc.getInfoLabel("Container(%d).CurrentItem" % container) or "-1") != position:
            return False
        labels = "Container(%d).ListItem." % container
        actual = _identity({
            "imdb": xbmc.getInfoLabel(labels + "UniqueID(imdb)"),
            "tmdb": xbmc.getInfoLabel(labels + "UniqueID(tmdb)"),
            "dbid": xbmc.getInfoLabel(labels + "DBID"),
        })
        return actual == request.get("identity")
    except (KeyError, TypeError, ValueError):
        return False


class SlyGuyPreviewService:
    """Single provider worker with a replaceable one-entry pending slot."""

    def __init__(self, xbmc, monitor, player, build_item, get_youtube_id,
                 play_yt_dlp, yt_dlp_mode, refresh_settings=None, resolve_imdb=None):
        self.xbmc = xbmc
        self.monitor = monitor
        self.player = player
        self.build_item = build_item
        self.get_youtube_id = get_youtube_id
        self.play_yt_dlp = play_yt_dlp
        self.yt_dlp_mode = yt_dlp_mode
        self.refresh_settings = refresh_settings or (lambda: None)
        self.resolve_imdb = resolve_imdb
        self.lock = threading.Condition()
        self.pending = None
        self.resolving = False
        self.closed = False
        self.thread = threading.Thread(target=self._run, name="SlyGuy-AcTweeteR-Preview",
                                       daemon=True)
        self.thread.start()

    def _is_current(self, request):
        return not self.closed and request_is_current(self.xbmc, request)

    def on_notification(self, sender, method, data):
        if self.closed:
            return False
        # Kodi 21.3 Monitor prefixes JSONRPC.NotifyAll messages with the
        # announcement category. Do not accept a broad suffix match.
        if method == _ANNOUNCEMENT_METHOD:
            method = MESSAGE
        if sender != REQUEST_SENDER or method != MESSAGE:
            if sender == REQUEST_SENDER or method == MESSAGE:
                self.xbmc.log("[SlyGuy] ACTWEETER_PREVIEW_NOTIFICATION status=rejected sender=%s method=%s" %
                              (sender, method), getattr(self.xbmc, "LOGINFO", 1))
            return False
        request = _decode(data)
        if not isinstance(request, dict) or request.get("action") != "resolve":
            try:
                parsed = json.loads(data) if isinstance(data, str) else data
                shape = ("list:%d" % len(parsed) if isinstance(parsed, list) else
                         "dict" if isinstance(parsed, dict) else type(parsed).__name__)
            except (TypeError, ValueError):
                shape = "invalid_json"
            self.xbmc.log("[SlyGuy] ACTWEETER_PREVIEW_NOTIFICATION status=decode_rejected data_type=%s data_shape=%s" %
                          (type(data).__name__, shape), getattr(self.xbmc, "LOGINFO", 1))
            return False
        try:
            valid_generation = int(request.get("generation")) > 0
        except (TypeError, ValueError):
            return False
        request_id = request.get("request_id")
        if (not valid_generation or not isinstance(request_id, str) or
                _REQUEST_ID.fullmatch(request_id) is None or
                not _identity(request) or preview_source(request) is None):
            _send(self.xbmc, "resolved", request.get("generation", 0), "no_results",
                  request.get("request_id", ""))
            return False
        self.xbmc.log("[SlyGuy] ACTWEETER_PREVIEW_REQUEST status=accepted generation=%d" %
                      int(request["generation"]), getattr(self.xbmc, "LOGINFO", 1))
        with self.lock:
            # Replace, never queue, work which has not started yet.
            self.pending = request
            self.lock.notify_all()
        return True

    def _resolve(self, request):
        generation = int(request["generation"])
        request_id = request["request_id"]
        manifest = "special://temp/actweeter_preview_%s.mpd" % request_id
        xbmcvfs = __import__("kodi_six.xbmcvfs", fromlist=["exists"])
        playback_requested = False
        try:
            self.xbmc.log("[SlyGuy] ACTWEETER_PREVIEW_RESOLUTION status=started generation=%d" %
                          generation, getattr(self.xbmc, "LOGINFO", 1))
            if not self._is_current(request):
                self.xbmc.log("[SlyGuy] ACTWEETER_PREVIEW_RESOLUTION status=stale generation=%d" %
                              generation, getattr(self.xbmc, "LOGINFO", 1))
                return "stale"
            source = preview_source(request)
            if source is None:
                return "no_results"
            item = self.build_item(source)
            if not item or not item.path:
                self.xbmc.log("[SlyGuy] ACTWEETER_PREVIEW_RESOLUTION status=no_results generation=%d" %
                              generation, getattr(self.xbmc, "LOGINFO", 1))
                return "no_results"
            provider, video_id = preview_target(item.path, self.get_youtube_id)
            if not provider:
                self.xbmc.log("[SlyGuy] ACTWEETER_PREVIEW_RESOLUTION status=no_video_id generation=%d" %
                              generation, getattr(self.xbmc, "LOGINFO", 1))
                return "no_results"
            if not self._is_current(request):
                return "stale"

            if provider == "imdb":
                resolved = self.resolve_imdb(video_id) if self.resolve_imdb else None
            else:
                resolved = self.play_yt_dlp(video_id, manifest_path=manifest)
            if not resolved or not resolved.path:
                self.xbmc.log("[SlyGuy] ACTWEETER_PREVIEW_RESOLUTION status=no_stream generation=%d" %
                              generation, getattr(self.xbmc, "LOGINFO", 1))
                return "no_results"
            if not self._is_current(request):
                return "stale"

            # The shared SlyGuy proxy starts in script.module.slyguy's service,
            # while this bridge runs in the trailers add-on service. Its
            # settings cache can therefore predate the proxy's persisted path.
            # Refresh only the provider's settings cache before get_li applies
            # SlyGuy's own manifest/segment proxy routing.
            self.refresh_settings()
            listitem = resolved.get_li(playing=True)
            # SlyGuy's item builder rewrites special:// manifests through its
            # localhost proxy, which is also responsible for serving the
            # temporary MPD and proxying signed segment URLs/headers. Bypass
            # neither that route nor its URL rewriting with the raw VFS/local
            # path: InputStream Adaptive cannot open either directly here.
            playback_path = getattr(resolved, "path", "")
            parsed_playback = urlparse(playback_path)
            manifest_name = manifest.rsplit("/", 1)[-1]
            local_proxy = parsed_playback.hostname in ("127.0.0.1", "localhost")
            manifest_match = manifest_name in unquote(parsed_playback.path)
            if (parsed_playback.scheme not in ("http", "https") or
                    (provider == "youtube" and (not local_proxy or not manifest_match))):
                self.xbmc.log(
                    "[SlyGuy] ACTWEETER_PREVIEW_RESOLUTION status=proxy_unavailable "
                    "generation=%d scheme=%s loopback=%s manifest_match=%s" %
                    (generation, parsed_playback.scheme or "none", local_proxy,
                     manifest_match), getattr(self.xbmc, "LOGWARNING", 2))
                return "error"
            self.xbmc.log(
                "[SlyGuy] ACTWEETER_PREVIEW_RESOLUTION status=proxy_ready "
                "generation=%d scheme=%s provider=%s loopback=%s manifest_match=%s" %
                (generation, parsed_playback.scheme, provider, local_proxy,
                 manifest_match), getattr(self.xbmc, "LOGINFO", 1))
            listitem.setProperty("AcTweeteR.PreviewOwner", "AUTO_PREVIEW")
            listitem.setProperty("AcTweeteR.PreviewGeneration", str(generation))
            listitem.setProperty("AcTweeteR.PreviewIdentity", request["identity"])
            listitem.setProperty("AcTweeteR.PreviewRequestId", request["request_id"])
            listitem.setProperty("AcTweeteR.PreviewManifest", manifest)
            # This final guard is adjacent to the only player handoff. The
            # coordinator also invalidates on non-preview Player callbacks.
            with self.lock:
                # Serialize the final generation check/player handoff against
                # service shutdown and replacement requests.
                if not self._is_current(request):
                    return "stale"
                self.player.play(playback_path, listitem, windowed=True)
                playback_requested = True
            return "started"
        except Exception as exc:
            # Avoid exception text: provider errors can contain private URLs.
            self.xbmc.log("[SlyGuy] AcTweeteR preview failed type=%s" %
                          type(exc).__name__, self.xbmc.LOGWARNING)
            return "error"
        finally:
            if not playback_requested:
                self.xbmc.log("[SlyGuy] ACTWEETER_PREVIEW_RESOLUTION status=cleaned generation=%d" %
                              generation, getattr(self.xbmc, "LOGINFO", 1))
            if not playback_requested and xbmcvfs.exists(self.xbmc.translatePath(manifest)):
                xbmcvfs.delete(self.xbmc.translatePath(manifest))

    def _run(self):
        while not self.closed and not self.monitor.abortRequested():
            with self.lock:
                while self.pending is None and not self.closed and not self.monitor.abortRequested():
                    self.lock.wait(0.5)
                if self.closed or self.monitor.abortRequested():
                    return
                request = self.pending
                self.pending = None
                self.resolving = True
            status = self._resolve(request)
            generation = request.get("generation", 0)
            if not self.closed and not self.monitor.abortRequested():
                _send(self.xbmc, "resolved", generation, status,
                      request.get("request_id", ""))
            with self.lock:
                self.resolving = False
                self.lock.notify_all()

    def close(self):
        with self.lock:
            self.closed = True
            self.pending = None
            self.lock.notify_all()


def run_slyguy_service():
    """Entry point called from SlyGuy's own installed service context."""
    from kodi_six import xbmc
    from resources.lib.plugin import _build_item
    from resources.lib.settings import settings as trailer_settings
    from resources.lib.youtube import get_youtube_id, play_yt_dlp
    from resources.lib.imdb import IMDB
    from resources.lib.constants import TrailerItem, IMDB_API_HEADERS, IMDB_QUALITY_MAP

    def resolve_imdb(identifier):
        best = IMDB(identifier).get_best()
        videos = best.get("videos", {}) if best else {}
        path = videos.get("DEF_AUTO") or next(
            (videos[key] for key in IMDB_QUALITY_MAP if videos.get(key)), "")
        # Use SlyGuy's native resolver without its shared temp/imdb.m3u8 file.
        return TrailerItem(path=path, headers=IMDB_API_HEADERS) if path else None

    class Monitor(xbmc.Monitor):
        def __init__(self):
            super().__init__()
            self.worker = None

        def onNotification(self, sender, method, data):
            if (sender in ("service.actweeter.SIGNAL", "slyguy.trailers.SIGNAL") or
                    method == "actweeter_auto_preview"):
                kind = type(data).__name__
                shape = "none"
                try:
                    parsed = json.loads(data) if isinstance(data, str) else data
                    shape = ("list:%d" % len(parsed) if isinstance(parsed, list) else
                             "dict" if isinstance(parsed, dict) else type(parsed).__name__)
                except (TypeError, ValueError):
                    shape = "invalid_json"
                xbmc.log("[SlyGuy] ACTWEETER_PREVIEW_NOTIFICATION sender=%s method=%s data_type=%s data_shape=%s" %
                         (sender, method, kind, shape), getattr(xbmc, "LOGINFO", 1))
            if self.worker:
                self.worker.on_notification(sender, method, data)

    monitor = Monitor()
    worker = SlyGuyPreviewService(xbmc, monitor, xbmc.Player(), _build_item,
                                  get_youtube_id, play_yt_dlp, None,
                                  refresh_settings=trailer_settings.reset,
                                  resolve_imdb=resolve_imdb)
    monitor.worker = worker
    xbmc.log("[SlyGuy] ACTWEETER_PREVIEW_BRIDGE status=started",
             getattr(xbmc, "LOGINFO", 1))
    try:
        while not monitor.abortRequested():
            if monitor.waitForAbort(1):
                break
    finally:
        worker.close()
