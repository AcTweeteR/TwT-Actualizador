"""Reproducible priority-fix overlay onto the verified Stable XStream ZIP.

The upstream package is not rebuilt or modified in place. All textual edits
are fail-closed (exact one anchor) to avoid shipping a partial patch.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source/0.4.32/third_party/xstream"


def once(text, before, after, name):
    count = text.count(before)
    if count != 1:
        raise ValueError("%s: expected one patch anchor; found %d" % (name, count))
    return text.replace(before, after, 1)


def patch_xstream(payloads):
    addon = "plugin.video.xstream-pro/"
    key = addon + "resources/settings.xml"
    settings = payloads[key].decode()
    settings = once(settings,
        'id="provider_series_enabled" default="false"',
        'id="provider_series_enabled" default="true"',
        "enable provider series artwork and synopsis on fresh profiles")
    payloads[key] = settings.encode()

    key = addon + "resources/lib/addon.py"
    s = payloads[key].decode()
    # Existing installations may persist the previous false default. For
    # season/episode navigation, use available artwork and descriptions while
    # still respecting the individual metadata-field switches.
    master = '    use_prov = addon.getSetting("provider_series_enabled").lower() == "true"'
    for route_name in ("xtream_series", "xtream_season"):
        start = s.index("def %s(" % route_name)
        end = s.find("\ndef ", start + 4)
        if end < 0:
            end = len(s)
        part = s[start:end]
        if part.count(master) != 1:
            raise ValueError("unexpected series metadata toggle in " + route_name)
        s = s[:start] + part.replace(
            master, '    use_prov = True  # ensure season/episode metadata') + s[end:]
    s = once(s,
        '''    xbmcplugin.setContent(addon_handle, "tvshows")
    xbmcplugin.setPluginCategory(addon_handle, "Temporadas")
''',
        '''    xbmcplugin.setContent(addon_handle, "seasons")
    xbmcplugin.setPluginCategory(addon_handle, "Temporadas")
''', "Kodi season content type")

    s = once(s, '''        info_tag.setMediaType("season")
        info_tag.setTitle(label)

        # Plot''',
        '''        info_tag.setMediaType("season")
        info_tag.setTitle(label)
        if series_meta.get("name"):
            info_tag.setTvShowTitle(series_meta["name"])

        # Plot''', "season metadata")

    s = once(s,
        '''        # Art
        art = {}
        if use_prov_posters and series_cover:
            art["icon"] = series_cover
            art["thumb"] = series_cover
            art["poster"] = series_cover
        else:
            art["icon"] = "DefaultFolder.png"
        if use_prov_posters and series_backdrop:
            art["fanart"] = series_backdrop
        li.setArt(art)
''',
        '''        # Standard Kodi art names are mandatory for Bingie season views.
        art = {"icon": "DefaultFolder.png"}
        if use_prov_posters and series_cover:
            art.update(icon=series_cover, thumb=series_cover, poster=series_cover)
            art["season.poster"] = series_cover
            art["tvshow.poster"] = series_cover
        if use_prov_posters and series_backdrop:
            art["fanart"] = series_backdrop
            art["landscape"] = series_backdrop
            art["tvshow.fanart"] = series_backdrop
        li.setArt(art)
''', "season artwork inheritance")

    s = once(s,
        '''        info_tag = li.getVideoInfoTag()
        info_tag.setMediaType("episode")
        info_tag.setTitle(title)

        # Plot
        if use_prov_plot:
            info_tag.setPlot(ep.get("info", {}).get("plot", ""))

        # Duration''',
        '''        info_tag = li.getVideoInfoTag()
        info_tag.setMediaType("episode")
        info_tag.setTitle(title)
        episode_info = ep.get("info") if isinstance(ep.get("info"), dict) else {}
        if series_meta.get("name"):
            info_tag.setTvShowTitle(series_meta["name"])
        try:
            info_tag.setSeason(int(season_num))
            info_tag.setEpisode(int(ep.get("episode_num")))
        except (ValueError, TypeError, OverflowError):
            pass

        # Do not substitute the series synopsis for a missing episode plot.
        if use_prov_plot:
            info_tag.setPlot(
                episode_info.get("plot") or ep.get("plot") or
                episode_info.get("description") or ep.get("description") or ""
            )

        # Duration''', "exact episode metadata")

    s = once(s,
        '''        movie_image = ep.get("info", {}).get("movie_image")
        if use_prov_posters and movie_image:
            li.setArt({"icon": movie_image, "thumb": movie_image})
        li.setProperty("IsPlayable", "true")
''',
        '''        movie_image = (episode_info.get("movie_image") or
                       ep.get("movie_image") or episode_info.get("thumbnail") or "")
        series_cover = (series_meta.get("cover") or series_meta.get("stream_icon") or
                        series_meta.get("poster_url") or "")
        backdrops = series_meta.get("backdrop_path") or []
        series_backdrop = (backdrops[0] if isinstance(backdrops, list) and backdrops else
                           backdrops if isinstance(backdrops, str) else "")
        art = {"icon": "DefaultVideo.png", "thumb": "DefaultVideo.png"}
        if use_prov_posters:
            fallback = movie_image or series_backdrop or series_cover
            if fallback:
                art.update(icon=fallback, thumb=fallback, landscape=fallback)
            if series_cover:
                art["poster"] = series_cover
                art["tvshow.poster"] = series_cover
                art["season.poster"] = series_cover
            if series_backdrop:
                art["fanart"] = series_backdrop
                art["tvshow.fanart"] = series_backdrop
        li.setArt(art)
        li.setProperty("IsPlayable", "true")
''', "episode artwork fallback")

    s = once(s,
        '''        li.addContextMenuItems(ctx)
        watched_actions = (premium_routes.content_state.watched_context(''',
        '''        watched_actions = (premium_routes.content_state.watched_context(''',
        "duplicate episode context action")

    s = once(s,
        '''        premium_routes.content_state.add_context_actions(li, ctx, watched_actions)
        series_name = info.get("info", {}).get("name", "")
''',
        '''        progress_action = []
        if series_id and str(season_num).isdigit() and str(episode_number).isdigit():
            route = build_url({
                "mode": "mark_progress_to", "series_id": str(series_id),
                "season": str(season_num), "episode": str(episode_number),
                "tmdb_id": str(series_tmdb_id or ""), "profile_num": str(pnum)
            })
            progress_action = [("Establecer progreso hasta aquí (AcTweeteR)",
                                "RunPlugin(%s)" % route)]
        premium_routes.content_state.add_context_actions(
            li, ctx, watched_actions, progress_action)
        series_name = info.get("info", {}).get("name", "")
''', "progress until episode context")

    s = once(s,
        '''elif mode == "toggle_tmdb_watched":
    from watched_actions import toggle_tmdb_watched
    toggle_tmdb_watched(globals(), args)
''',
        '''elif mode == "toggle_tmdb_watched":
    from watched_actions import toggle_tmdb_watched
    toggle_tmdb_watched(globals(), args)
elif mode == "mark_progress_to":
    from watched_progress import mark_progress, IncompleteSeriesInventory
    try:
        result = mark_progress(globals(), args)
        xbmcgui.Dialog().notification(
            "AcTweeteR", "Progreso actualizado: %d capítulos" %
            result["episodes_up_to_target"], xbmcgui.NOTIFICATION_INFO, 4000)
    except IncompleteSeriesInventory:
        xbmcgui.Dialog().notification(
            "AcTweeteR", "Inventario de capítulos incompleto; no se ha modificado el progreso",
            xbmcgui.NOTIFICATION_WARNING, 6000)
''', "progress until episode dispatch")

    # Manual synchronization remains available. The new scheduled mode is
    # separate and never opens a modal dialog or changes a profile.
    s = once(s,
        '''def _sync_pvr_epg_only(offer_reload=True):
''',
        '''def _auto_refresh_pvr_epg():
    """Refresh stale XMLTV only while idle, then reload owned IPTV Simple data."""
    from pvr_epg_health import should_refresh
    if xbmc.getCondVisibility("Player.HasMedia"):
        return False
    pnum = _get_pvr_profile_num()
    if not os.path.isfile(_pvr_m3u_path_for_profile(pnum)):
        return False
    if not xbmc.getCondVisibility("System.HasAddon(pvr.iptvsimple)"):
        return False
    if not _acquire_pvr_sync_lock():
        return False
    try:
        pnum = _get_pvr_profile_num()
        live_path = _pvr_epg_path_for_profile(pnum)
        if not should_refresh(live_path):
            return False
        _log("PVR automatic EPG: refreshing stale XMLTV")
        previous = os.path.getmtime(live_path) if os.path.exists(live_path) else 0
        if not _export_pvr_epg_for_profile(pnum, force_fetch=True):
            _log("PVR automatic EPG: no usable fresh source; preserving existing guide")
            return False
        updated = os.path.exists(live_path) and os.path.getmtime(live_path) > previous
        if not updated:
            return False
        # Sports uses the same freshly retrieved profile cache when possible.
        if addon.getSetting("sports_pvr_enabled").lower() == "true":
            sports_pnum = _get_sports_pvr_profile_num()
            sports_path = _sports_pvr_epg_path_for_profile(sports_pnum)
            if os.path.isfile(sports_path):
                try:
                    sports_channels = _export_sports_pvr_m3u()
                    if sports_channels:
                        _export_sports_pvr_epg_for_profile(
                            sports_pnum, sports_channels,
                            force_fetch=(str(sports_pnum) != str(pnum)))
                except Exception:
                    _log("PVR automatic EPG: sports refresh unavailable")
        # IPTV Simple 21.11.0 does not watch changes to local XMLTV files.
        # Reload is allowed only after the fetch, and never during playback.
        if not xbmc.getCondVisibility("Player.HasMedia") and xbmc.getGlobalIdleTime() >= 30:
            _reload_iptv_simple_addon("PVR automatic EPG", stop_manager=False)
        else:
            _log("PVR automatic EPG: files refreshed, PVR reload deferred until idle/restart")
        return True
    except Exception as exc:
        _log("PVR automatic EPG: failed error_type=%s" % type(exc).__name__)
        return False
    finally:
        _release_pvr_sync_lock()


def _sync_pvr_epg_only(offer_reload=True):
''', "background PVR EPG action")

    s = once(s,
        '''elif mode == "sync_pvr_epg_only":
''',
        '''elif mode == "auto_refresh_pvr_epg":
    _auto_refresh_pvr_epg()
elif mode == "sync_pvr_epg_only":
''', "background PVR EPG dispatch")

    s = once(s,
        '''        _apply_epg_fallback_from_other_profiles(
''',
        '''        _apply_epg_fallback_from_other_profiles(
''', "noop check") if False else s

    # Gate both the main and Sports exports against a stale-but-valid feed.
    s = once(s,
        '''        if epg.programs and epg.export_xmltv(epg_path):
''',
        '''        from pvr_epg_health import acceptable
        if epg.programs and not acceptable(epg.programs):
            _log("PVR EPG: no current programming on enough channels; preserving existing XMLTV")
            return False
        if epg.programs and epg.export_xmltv(epg_path):
''', "main EPG freshness")

    s = once(s,
        '''        if not epg.programs:
            if epg_file_has_data(epg_path):
                _log("Sports PVR: no fresh EPG data; keeping existing Sports EPG")
''',
        '''        from pvr_epg_health import acceptable
        if epg.programs and not acceptable(epg.programs):
            _log("Sports PVR: EPG has insufficient current programmes; keeping previous guide")
            return False
        if not epg.programs:
            if epg_file_has_data(epg_path):
                _log("Sports PVR: no fresh EPG data; keeping existing Sports EPG")
''', "sports EPG freshness")
    payloads[key] = s.encode()

    key = addon + "resources/lib/premium_routes.py"
    routes = payloads[key].decode()
    # A public Trakt rank may resolve to fewer than 19 provider titles.
    # Still offer the full subscribed catalogue at the end of the row.
    routes = once(routes,
        """    elif indexed is None and view in ('trending', 'popular'):
        items = ranked_provider_items(g, items, stype, view)
""",
        """    elif indexed is None and view in ('trending', 'popular'):
        full_provider_catalog_count = len(items)
        items = ranked_provider_items(g, items, stype, view)
""", "ranked provider expansion source")
    routes = once(routes,
        """    if (get('actweeter_expand') == '1' and stype in ('movie', 'series')
            and view in expandable_views and has_more):
""",
        """    ranked_has_more = (indexed is None and view in ('trending', 'popular')
                       and full_provider_catalog_count > len(items))
    if (get('actweeter_expand') == '1' and stype in ('movie', 'series')
            and view in expandable_views and (has_more or ranked_has_more)):
""", "ranked expansion visibility")
    routes = once(routes,
        """        query['browse'] = '1'
        query['page'] = '1'
        query['limit'] = '48'
        li = g['_new_listitem']('[COLOR FFE50914]EXPANDIR[/COLOR]')
""",
        """        query['browse'] = '1'
        query['page'] = '1'
        query['limit'] = '48'
        if ranked_has_more and not has_more:
            query['view'] = 'catalog'
        li = g['_new_listitem']('[COLOR FFE50914]EXPANDIR[/COLOR]')
""", "ranked expansion target")
    payloads[key] = routes.encode()

    key = addon + "service.py"
    service = payloads[key].decode()
    service = once(service,
        '''import datetime
import xbmcaddon''',
        '''import datetime
import time
import re
import xbmcaddon''',
        "EPG scheduler imports")
    service = once(service,
        '''last_year_check = None
resume_signature = None''',
        '''last_year_check = None
last_epg_check = 0
resume_signature = None''',
        "EPG scheduler state")
    service = once(service,
        '''    now = datetime.datetime.now()
''',
        '''    # Run one refresh attempt at startup/periodically after the user has
    # stopped interacting. Never acquire player ownership or block the UI.
    if time.monotonic() - last_epg_check >= 1800:
        try:
            addon = xbmcaddon.Addon()
            active = addon.getSetting("active_pvr_profile") or "Profile 1"
            match = re.search(r"(\\d+)$", active)
            profile = match.group(1) if match else "1"
            directory = xbmcvfs.translatePath(addon.getAddonInfo("profile"))
            filename = "pvr_epg_xstream_pro_p%s.xml" % profile
            from pvr_epg_health import should_refresh
            if not xbmc.getCondVisibility("Player.HasMedia") and xbmc.getGlobalIdleTime() >= 30:
                if should_refresh(os.path.join(directory, filename)):
                    xbmc.executebuiltin(
                        "RunPlugin(plugin://plugin.video.xstream-pro/?mode=auto_refresh_pvr_epg)")
                last_epg_check = time.monotonic()
        except Exception:
            xbmc.log("[Xstream Pro] Automatic PVR EPG tick unavailable", xbmc.LOGWARNING)
            last_epg_check = time.monotonic()
    now = datetime.datetime.now()
''', "EPG scheduler tick")
    payloads[key] = service.encode()

    for name in ("watched_progress.py", "pvr_epg_health.py"):
        payloads[addon + "resources/lib/" + name] = (SOURCE / name).read_bytes()
    return payloads
