"""Safe access to Kodi's current video ListItem from player callbacks."""


def get_playing_video_item(player):
    """Return the current video item only while Kodi reports video playback.

    Kodi raises and logs an exception if getPlayingItem() is called after the
    terminal callback has already closed the file. The state check avoids that
    noisy, expected race while preserving the callback's tagged-item lookup.
    """
    try:
        is_playing_video = getattr(player, "isPlayingVideo", None)
        if not callable(is_playing_video) or not is_playing_video():
            return None
        return player.getPlayingItem()
    except Exception:
        return None
