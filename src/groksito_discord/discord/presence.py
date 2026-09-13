"""Aetherion presence / custom status. Owner-only via /status."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import discord

from ..config import settings
from ..llm.persona import CREATOR_DISCORD_ID

logger = logging.getLogger("aetherion.presence")

DEFAULT_KIND = "watching"
DEFAULT_TEXT = "The Cosmos"
MAX_TEXT = 128

KIND_WATCHING = "watching"
KIND_PLAYING = "playing"
KIND_LISTENING = "listening"
KIND_COMPETING = "competing"
KIND_CUSTOM = "custom"


def _store_path() -> Path:
    base = Path(getattr(settings, "data_dir", Path("./data")))
    base.mkdir(parents=True, exist_ok=True)
    return base / "presence.json"


def load_presence() -> dict:
    path = _store_path()
    if not path.exists():
        return {"kind": DEFAULT_KIND, "text": DEFAULT_TEXT}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"kind": DEFAULT_KIND, "text": DEFAULT_TEXT}
        kind = str(data.get("kind") or DEFAULT_KIND).strip().lower()
        text = str(data.get("text") or DEFAULT_TEXT).strip()[:MAX_TEXT]
        return {"kind": kind or DEFAULT_KIND, "text": text or DEFAULT_TEXT}
    except Exception:
        logger.exception("presence store read failed")
        return {"kind": DEFAULT_KIND, "text": DEFAULT_TEXT}


def save_presence(kind: str, text: str) -> dict:
    payload = {"kind": (kind or DEFAULT_KIND).strip().lower(), "text": (text or "").strip()[:MAX_TEXT]}
    if not payload["text"]:
        payload["text"] = DEFAULT_TEXT
    _store_path().write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def is_status_owner(user_id: int | None) -> bool:
    try:
        return int(user_id or 0) == int(CREATOR_DISCORD_ID)
    except (TypeError, ValueError):
        return False


def build_activity(kind: str, text: str):
    name = (text or DEFAULT_TEXT).strip()[:MAX_TEXT] or DEFAULT_TEXT
    key = (kind or DEFAULT_KIND).strip().lower()
    if key == KIND_CUSTOM:
        return discord.CustomActivity(name=name)
    if key == KIND_PLAYING:
        return discord.Game(name=name)
    if key == KIND_LISTENING:
        return discord.Activity(type=discord.ActivityType.listening, name=name)
    if key == KIND_COMPETING:
        return discord.Activity(type=discord.ActivityType.competing, name=name)
    return discord.Activity(type=discord.ActivityType.watching, name=name)


async def apply_presence(client, kind: str | None = None, text: str | None = None) -> dict:
    if kind is None or text is None:
        stored = load_presence()
        kind = stored["kind"]
        text = stored["text"]
    activity = build_activity(kind, text)
    await client.change_presence(activity=activity)
    return {"kind": kind, "text": text}
