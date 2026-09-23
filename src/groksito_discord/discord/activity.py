"""Per-server message / voice / XP tracking. Starts when first enabled. No backfill."""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ..config import settings

logger = logging.getLogger("aetherion.activity")
EASTERN = ZoneInfo("America/Detroit")
MSG_XP = 15
MSG_COOLDOWN = 45.0
VOICE_XP_PER_MIN = 10

_lock = threading.Lock()
_voice_started: dict[tuple[int, int], float] = {}
_msg_xp_at: dict[tuple[int, int], float] = {}


def _path() -> Path:
    base = Path(getattr(settings, "data_dir", Path("./data")))
    base.mkdir(parents=True, exist_ok=True)
    return base / "activity.json"


def _empty() -> dict:
    return {"guilds": {}}


def _load() -> dict:
    path = _path()
    if not path.exists():
        return _empty()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _empty()
        if not isinstance(data.get("guilds"), dict):
            data["guilds"] = {}
        return data
    except Exception:
        logger.exception("activity store read failed")
        return _empty()


def _save(data: dict) -> None:
    path = _path()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def _today() -> str:
    return datetime.now(EASTERN).date().isoformat()


def _guild(store: dict, guild_id: int) -> dict:
    guilds = store.setdefault("guilds", {})
    row = guilds.get(str(guild_id))
    if not isinstance(row, dict):
        row = {"started": _today(), "users": {}}
        guilds[str(guild_id)] = row
    row.setdefault("started", _today())
    if not isinstance(row.get("users"), dict):
        row["users"] = {}
    return row


def _user(guild_row: dict, user_id: int) -> dict:
    users = guild_row.setdefault("users", {})
    row = users.get(str(user_id))
    if not isinstance(row, dict):
        row = {"messages": 0, "voice_seconds": 0, "xp": 0, "channels": {}}
        users[str(user_id)] = row
    try:
        row["messages"] = int(row.get("messages", 0) or 0)
    except (TypeError, ValueError):
        row["messages"] = 0
    try:
        row["voice_seconds"] = int(row.get("voice_seconds", 0) or 0)
    except (TypeError, ValueError):
        row["voice_seconds"] = 0
    try:
        row["xp"] = int(row.get("xp", 0) or 0)
    except (TypeError, ValueError):
        row["xp"] = 0
    if not isinstance(row.get("channels"), dict):
        row["channels"] = {}
    return row


def xp_need(level: int) -> int:
    return 100 + 50 * max(0, int(level))


def level_from_xp(xp: int) -> tuple[int, int, int]:
    remain = max(0, int(xp))
    level = 0
    while True:
        need = xp_need(level)
        if remain < need:
            return level, remain, need
        remain -= need
        level += 1


def format_voice(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes = rem // 60
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m"
    return f"{seconds}s"


def snapshot(guild_id: int, user_id: int, guild=None) -> dict:
    with _lock:
        store = _load()
        grow = _guild(store, guild_id)
        row = _user(grow, user_id)
        live = 0
        started = _voice_started.get((int(guild_id), int(user_id)))
        if started:
            live = max(0, int(time.time() - started))
        voice = int(row["voice_seconds"]) + live
        level, into, need = level_from_xp(int(row["xp"]))
        people = []
        for uid, data in (grow.get("users") or {}).items():
            if not isinstance(data, dict):
                continue
            try:
                mid = int(uid)
                msgs = int(data.get("messages") or 0)
                vs = int(data.get("voice_seconds") or 0)
            except (TypeError, ValueError):
                continue
            extra = _voice_started.get((int(guild_id), mid))
            if extra:
                vs += max(0, int(time.time() - extra))
            people.append((mid, msgs, vs))
        msg_rank = None
        voice_rank = None
        if people:
            by_msg = sorted(people, key=lambda r: r[1], reverse=True)
            by_voice = sorted(people, key=lambda r: r[2], reverse=True)
            for i, rowp in enumerate(by_msg, start=1):
                if rowp[0] == int(user_id) and rowp[1] > 0:
                    msg_rank = i
                    break
            for i, rowp in enumerate(by_voice, start=1):
                if rowp[0] == int(user_id) and rowp[2] > 0:
                    voice_rank = i
                    break
        scored = []
        raw_ch = row.get("channels") or {}
        for cid, val in raw_ch.items():
            try:
                count = int(val if not isinstance(val, dict) else val.get("n") or 0)
            except (TypeError, ValueError):
                continue
            if count <= 0:
                continue
            name = str(cid)
            if guild is not None:
                try:
                    ch = guild.get_channel(int(cid))
                except (TypeError, ValueError):
                    ch = None
                if ch is not None:
                    name = getattr(ch, "name", name)
            scored.append((name, count))
        scored.sort(key=lambda r: r[1], reverse=True)
        return {
            "started": str(grow.get("started") or _today()),
            "messages": int(row["messages"]),
            "voice_seconds": voice,
            "xp": int(row["xp"]),
            "level": level,
            "into": into,
            "need": need,
            "msg_rank": msg_rank,
            "voice_rank": voice_rank,
            "tracked": len(people),
            "top_channels": scored[:4],
        }


def record_message(guild_id: int, user_id: int, channel_id: int | None = None) -> None:
    key = (int(guild_id), int(user_id))
    now = time.time()
    with _lock:
        store = _load()
        row = _user(_guild(store, guild_id), user_id)
        row["messages"] += 1
        if channel_id:
            channels = row.setdefault("channels", {})
            cid = str(int(channel_id))
            cur = channels.get(cid)
            if isinstance(cur, dict):
                cur["n"] = int(cur.get("n") or 0) + 1
                channels[cid] = cur
            else:
                try:
                    channels[cid] = int(cur or 0) + 1
                except (TypeError, ValueError):
                    channels[cid] = 1
        last = _msg_xp_at.get(key, 0.0)
        if now - last >= MSG_COOLDOWN:
            row["xp"] += MSG_XP
            _msg_xp_at[key] = now
        _save(store)


def voice_join(guild_id: int, user_id: int) -> None:
    _voice_started[(int(guild_id), int(user_id))] = time.time()


def voice_leave(guild_id: int, user_id: int) -> None:
    key = (int(guild_id), int(user_id))
    started = _voice_started.pop(key, None)
    if not started:
        return
    gained = max(0, int(time.time() - started))
    if gained <= 0:
        return
    with _lock:
        store = _load()
        row = _user(_guild(store, guild_id), user_id)
        row["voice_seconds"] += gained
        mins = gained // 60
        if mins:
            row["xp"] += mins * VOICE_XP_PER_MIN
        _save(store)


def seed_open_voice(guild_id: int, user_id: int) -> None:
    key = (int(guild_id), int(user_id))
    if key not in _voice_started:
        _voice_started[key] = time.time()


def _wrap(client, name, fn) -> None:
    hooked = getattr(client, "_aetherion_activity_events", None)
    if hooked is None:
        hooked = set()
        client._aetherion_activity_events = hooked
    if name in hooked:
        return
    existing = getattr(client, name, None)
    if existing is fn:
        hooked.add(name)
        return
    if existing is not None and callable(existing):
        def _bind(old, new, ev):
            async def _wrapped(*args, **kwargs):
                try:
                    await new(*args, **kwargs)
                except Exception:
                    logger.exception("activity %s failed", ev)
                return await old(*args, **kwargs)
            _wrapped.__name__ = ev
            return _wrapped
        setattr(client, name, _bind(existing, fn, name))
    else:
        setattr(client, name, fn)
    hooked.add(name)


async def on_message(message) -> None:
    if getattr(message, "guild", None) is None:
        return
    author = getattr(message, "author", None)
    if author is None or getattr(author, "bot", False):
        return
    channel = getattr(message, "channel", None)
    record_message(message.guild.id, author.id, getattr(channel, "id", None))


async def on_voice_state_update(member, before, after) -> None:
    if member is None or getattr(member, "bot", False) or getattr(member, "guild", None) is None:
        return
    old = getattr(before, "channel", None)
    new = getattr(after, "channel", None)
    if old is None and new is not None:
        voice_join(member.guild.id, member.id)
    elif old is not None and new is None:
        voice_leave(member.guild.id, member.id)
    elif old is not None and new is not None and old.id != new.id:
        voice_leave(member.guild.id, member.id)
        voice_join(member.guild.id, member.id)


def attach_listeners(client) -> None:
    if client is None or getattr(client, "_aetherion_activity", False):
        return
    client._aetherion_activity = True

    async def _seed_ready() -> None:
        try:
            for guild in list(getattr(client, "guilds", []) or []):
                for channel in getattr(guild, "voice_channels", []) or []:
                    for member in getattr(channel, "members", []) or []:
                        if getattr(member, "bot", False):
                            continue
                        seed_open_voice(guild.id, member.id)
        except Exception:
            logger.exception("activity voice seed failed")

    _wrap(client, "on_message", on_message)
    _wrap(client, "on_voice_state_update", on_voice_state_update)
    _wrap(client, "on_ready", _seed_ready)
    logger.info("activity listeners attached")
