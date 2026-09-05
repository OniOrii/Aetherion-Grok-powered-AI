"""Rename a locked voice channel to today's date (America/New_York)."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import discord

from ..config import settings

logger = logging.getLogger("groksito.date_dock")

TZ = ZoneInfo("America/New_York")
NAME_PREFIX = "🗓️ |"


def _store_path() -> Path:
    base = Path(getattr(settings, "data_dir", Path("./data")))
    base.mkdir(parents=True, exist_ok=True)
    return base / "date_channels.json"


def _load_store() -> dict:
    path = _store_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        logger.exception("date dock store read failed")
        return {}


def _save_store(data: dict) -> None:
    _store_path().write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_guild_date_channel_id(guild_id: int) -> int:
    store = _load_store()
    raw = store.get(str(guild_id)) or store.get(guild_id)
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def set_guild_date_channel(guild_id: int, channel_id: int) -> None:
    store = _load_store()
    store[str(guild_id)] = int(channel_id)
    _save_store(store)


def clear_guild_date_channel(guild_id: int) -> None:
    store = _load_store()
    store.pop(str(guild_id), None)
    store.pop(guild_id, None)
    _save_store(store)


def _ordinal(n: int) -> str:
    if 10 <= (n % 100) <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def format_date_channel_name(now: datetime | None = None) -> str:
    now = now or datetime.now(TZ)
    # "Friday, Sep 4th" — matches The Great Indoors screenshot
    day = now.strftime("%A")
    month = now.strftime("%b")
    return f"{NAME_PREFIX} {day}, {month} {_ordinal(now.day)}"


def seconds_until_next_midnight_et() -> float:
    now = datetime.now(TZ)
    tomorrow = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=5, microsecond=0
    )
    return max(5.0, (tomorrow - now).total_seconds())


async def update_guild_date_channel(guild: discord.Guild) -> bool:
    cid = get_guild_date_channel_id(guild.id)
    if not cid:
        return False
    channel = guild.get_channel(cid)
    if channel is None:
        try:
            channel = await guild.fetch_channel(cid)
        except Exception:
            logger.warning("date dock: channel %s missing in guild %s", cid, guild.id)
            return False
    if not isinstance(channel, discord.VoiceChannel):
        logger.warning("date dock: %s is not a voice channel", cid)
        return False

    new_name = format_date_channel_name()
    if channel.name == new_name:
        return False
    try:
        await channel.edit(name=new_name, reason="Aetherion daily date dock")
        logger.info("date dock updated %s -> %s", guild.id, new_name)
        return True
    except discord.Forbidden:
        logger.warning("date dock: missing Manage Channels in guild %s", guild.id)
    except discord.HTTPException:
        logger.exception("date dock rename failed in guild %s", guild.id)
    return False


async def update_all_guilds(client: discord.Client) -> None:
    for guild in list(client.guilds):
        try:
            await update_guild_date_channel(guild)
        except Exception:
            logger.exception("date dock update failed for guild %s", guild.id)
        await asyncio.sleep(1.5)


async def date_dock_loop(client: discord.Client) -> None:
    await asyncio.sleep(8)
    await update_all_guilds(client)
    while True:
        wait = seconds_until_next_midnight_et()
        logger.info("date dock sleeping %.0f seconds until next ET midnight", wait)
        await asyncio.sleep(wait)
        await update_all_guilds(client)
