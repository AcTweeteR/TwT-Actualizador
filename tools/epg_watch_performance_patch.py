#!/usr/bin/env python3
"""Fail-closed targeted overlays for XStream's released Beta1 zip.

This script does not touch Kodi profiles, external sources, credentials, or
historical archives. It changes only watched UI invalidation and widget
rendering budgets. The input XStream package checksum is enforced by builder.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'plugin.video.xstream-pro/'


def once(source: str, before: str, after: str, reason: str):
    found = source.count(before)
    if found != 1:
        raise ValueError('%s: expected one source anchor, got %s' % (reason, found))
    return source.replace(before, after, 1)


def replace_member(payloads, name, mapper):
    key = PREFIX + name
    before = payloads[key].decode('utf-8')
    after = mapper(before)
    if after == before:
        raise ValueError('No actual package change in '+ name)
    payloads[key] = after.encode('utf-8')


def watched_actions(source):
    return once(source,
        '    g["xbmc"].executebuiltin("Container.Refresh")\n    return state\n',
        '''    # RunPlugin executes while Kodi may still be dismissing its context
    # menu. The original immediate refresh was often lost; update the
    # generated widget-route tokens and refresh after the menu closes.
    if state is not None:
        from watch_ui_refresh import invalidate_after_watched_mutation
        invalidate_after_watched_mutation(g, event='toggle_tmdb_watched')
    return state
''',
        'watched state immediate visual refresh')


def addon_routes(source):
    return once(source,
        '''        result = mark_progress(globals(), args)
        xbmcgui.Dialog().notification(''',
        '''        result = mark_progress(globals(), args)
        # Rebuild the existing episode/season/series cards and their
        # COMPLETE, watched-eye and new-episode status after persistence.
        from watch_ui_refresh import invalidate_after_watched_mutation
        invalidate_after_watched_mutation(globals(), event='mark_progress_to')
        xbmcgui.Dialog().notification(''',
        'episode progress visual refresh')


def premium_routes(source):
    s = source
    s = once(s, '''def ranked_provider_items(g, items, stype, section):''',
                '''def ranked_provider_items(g, items, stype, section, *, fast=False):''',
                'provider ranks fast signature')
    s = once(s,
        '''    key = 'premium_rank_%s_%s_es' % (stype, section)
    cached = g['_cache_load'](key) or {}
    if cached.get('expires', 0) > time.time():
        ranks = cached.get('ranks', [])
''',
        '''    key = 'premium_rank_%s_%s_es' % (stype, section)
    cached = g['_cache_load'](key) or {}
    expiry = cached.get('expires', 0)
    # On Home, avoid a synchronous Trakt/TMDb refresh while perfectly usable
    # ranking IDs remain cached. Full browse still refreshes normally.
    if (expiry > time.time() or
            (fast and cached.get('ranks') and expiry > time.time() - 86400)):
        ranks = cached.get('ranks', [])
''',
        'stale rank use for first paint')
    s = once(s,
        '''            if cached_ranks.get('expires', 0) <= time.time():
                return None''',
        '''            if cached_ranks.get('expires', 0) <= time.time() and not (
                    get('actweeter_expand') == '1' and get('browse') != '1'
                    and cached_ranks.get('ranks')
                    and cached_ranks.get('expires', 0) > time.time() - 86400):
                return None''',
        'movie index use warm cached ranks while widget refresh pending')
    s = once(s,
        '''            if cached.get('expires', 0) <= time.time():
                return None
            result = index.ranked(cached.get('ranks') or [], **args)''',
        '''            if cached.get('expires', 0) <= time.time() and not (
                    get('actweeter_expand') == '1' and get('browse') != '1'
                    and cached.get('ranks')
                    and cached.get('expires', 0) > time.time() - 86400):
                return None
            result = index.ranked(cached.get('ranks') or [], **args)''',
        'series index use warm cached ranks while widget refresh pending')
    s = once(s,
        '''    budget = [4, 1]
    if view in ('recent_tv', 'recent_tv_play'):''',
        '''    # Widget first paint is not a metadata-enrichment task. Provider
    # rows have titles and artwork; warm TMDb cache still supplies the extra
    # values. Full-screen browse keeps the original enrichment budget.
    fast_widget = get('actweeter_expand') == '1' and get('browse') != '1'
    budget = [0, 0] if fast_widget else [4, 1]
    if view in ('recent_tv', 'recent_tv_play'):''',
        'fast widget network budget')
    s = once(s,
        '''        items = ranked_provider_items(g, items, stype, view)''',
        '''        items = ranked_provider_items(g, items, stype, view, fast=fast_widget)''',
        'fast widget ranking fallback')
    return s


def series_changes(source):
    # Only a verified complete inventory can prove that a series has new
    # episodes. That event must invalidate cached home widgets in the same
    # installation instead of waiting for the next Kodi restart.
    return once(source,
        '''        _write(addon, profile_num, data)
    return True


def inventory_map(''',
        '''        _write(addon, profile_num, data)
    if previous_complete and added_ids and not catalog_is_new:
        # A new-episode sticker is generated from this exact inventory;
        # changing the dynamic widget URL token refreshes it on the fly.
        # Keep Kodi imports optional so legacy headless/index tests work.
        try:
            import xbmcgui
            xbmcgui.Window(10000).setProperty(
                'Premium.CollectionsRefresh', str(time.time_ns()))
        except (ImportError, AttributeError, RuntimeError, TypeError):
            pass
    return True


def inventory_map(''',
        'new episodes update the existing Home widget URL token')


def patch(payloads):
    replace_member(payloads, 'resources/lib/watched_actions.py', watched_actions)
    replace_member(payloads, 'resources/lib/addon.py', addon_routes)
    replace_member(payloads, 'resources/lib/premium_routes.py', premium_routes)
    replace_member(payloads, 'resources/lib/series_changes.py', series_changes)
    payloads[PREFIX + 'resources/lib/watch_ui_refresh.py'] = (
        ROOT/'source/0.4.32/third_party/xstream/refinements/watch_ui_refresh.py').read_bytes()
    return payloads
