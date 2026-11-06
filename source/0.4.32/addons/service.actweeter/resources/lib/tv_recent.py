"""Profile-local MRU history for live TV (never stores playlists or credentials)."""
from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path

MAX_CHANNELS = 20
_LOCK = threading.RLock()


def _id(value):
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return number if number > 0 and str(value).strip() == str(number) else None


def channel_from_item(item):
    """Player.OnPlay and Player.GetItem expose a TV channel as type=channel."""
    if not isinstance(item, dict) or item.get("type") != "channel":
        return None
    return _id(item.get("channelid", item.get("id")))


def read_history(path):
    path = Path(path)
    if path.is_symlink():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return []
    if not isinstance(value, dict) or value.get("version") != 1:
        return []
    channels = value.get("channels")
    if not isinstance(channels, list):
        return []
    result = []
    for raw in channels[:200]:
        ident = _id(raw)
        if ident is not None and ident not in result:
            result.append(ident)
        if len(result) == MAX_CHANNELS:
            break
    return result


def record(path, channel_id):
    """Move a channel to the front; write atomically only when order changes."""
    ident = _id(channel_id)
    if ident is None:
        return False
    path = Path(path)
    if path.is_symlink() or path.parent.is_symlink():
        return False
    with _LOCK:
        previous = read_history(path)
        updated = [ident] + [entry for entry in previous if entry != ident]
        updated = updated[:MAX_CHANNELS]
        if updated == previous:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        blob = json.dumps({"version": 1, "channels": updated},
                          separators=(",", ":")).encode("utf-8")
        fd, tmp = tempfile.mkstemp(prefix=".tv-recent-", dir=str(path.parent))
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(blob)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        return True


def rpc_call(kodi, method, params=None):
    query = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        query["params"] = params
    try:
        result = json.loads(kodi.executeJSONRPC(
            json.dumps(query, separators=(",", ":"))))
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return {}
    return result.get("result", {}) if isinstance(result, dict) else {}


def current_tv_channel(kodi):
    response = rpc_call(kodi, "Player.GetItem", {
        "playerid": 1, "properties": ["file"],
    })
    return channel_from_item(response.get("item"))


def channel_catalog(rpc):
    """Kodi's alltv group avoids scanning all groups and loads channels once."""
    params = {"channelgroupid": "alltv",
              "properties": ["channel", "thumbnail", "icon", "broadcastnow", "channeltype"],
              "limits": {"start": 0, "end": 5000}}
    result = rpc("PVR.GetChannels", params)
    if "channels" not in result:
        params["properties"] = ["channel", "thumbnail", "channeltype"]
        result = rpc("PVR.GetChannels", params)
    if "channels" not in result:
        # Fallback for older PVR backends that cannot resolve the alltv token.
        groups = rpc("PVR.GetChannelGroups", {"channeltype": "tv"}).get("channelgroups", [])
        if isinstance(groups, list) and groups and isinstance(groups[0], dict):
            group = groups[0].get("channelgroupid")
            if isinstance(group, int) or group == "alltv":
                params["channelgroupid"] = group
                result = rpc("PVR.GetChannels", params)
    channels = result.get("channels", [])
    return {_id(row["channelid"]): row for row in channels
            if isinstance(row, dict) and _id(row.get("channelid")) is not None}


def tv_rows(history, rpc):
    catalog = channel_catalog(rpc)
    rows = []
    for ident in history[:MAX_CHANNELS]:
        channel = catalog.get(ident)
        if channel is None:
            channel = rpc("PVR.GetChannelDetails", {
                "channelid": ident,
                "properties": ["channel", "thumbnail", "icon", "broadcastnow", "channeltype"],
            }).get("channeldetails")
        if not isinstance(channel, dict) or channel.get("channeltype") == "radio":
            continue
        title = channel.get("channel")
        if not isinstance(title, str) or not title.strip():
            continue
        broadcast = channel.get("broadcastnow")
        now = broadcast.get("title") if isinstance(broadcast, dict) else None
        icon = channel.get("icon") or channel.get("thumbnail") or ""
        rows.append({"id": ident, "name": title.strip(), "icon": icon
                     if isinstance(icon, str) else "",
                     "now": now.strip() if isinstance(now, str) and now.strip()
                     else "Sin información EPG"})
    return rows
