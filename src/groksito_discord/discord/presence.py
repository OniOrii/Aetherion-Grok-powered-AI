"""Aetherion presence / custom status. Owner-only via /status."""
from __future__ import annotations

import asyncio
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
ROTATION_SECONDS = 90

KIND_WATCHING = "watching"
KIND_PLAYING = "playing"
KIND_LISTENING = "listening"
KIND_COMPETING = "competing"
KIND_CUSTOM = "custom"

DEFAULT_ROTATION: list[dict[str, str]] = [
    {"kind": KIND_WATCHING, "text": "The Cosmos"},
    {"kind": KIND_PLAYING, "text": "Aetherion Hunt"},
    {"kind": KIND_LISTENING, "text": "the rift"},
    {"kind": KIND_PLAYING, "text": "poker with the house"},
    {"kind": KIND_WATCHING, "text": "the stars"},
    {"kind": KIND_COMPETING, "text": "Crown Rift"},
    {"kind": KIND_CUSTOM, "text": "God of AI!"},
]

_rotation_task: asyncio.Task | None = None


def _store_path() -> Path:
    base = Path(getattr(settings, "data_dir", Path("./data")))
    base.mkdir(parents=True, exist_ok=True)
    return base / "presence.json"


def _normalize_item(kind: str | None, text: str | None) -> dict:
    key = str(kind or DEFAULT_KIND).strip().lower() or DEFAULT_KIND
    if key not in {KIND_WATCHING, KIND_PLAYING, KIND_LISTENING, KIND_COMPETING, KIND_CUSTOM}:
        key = DEFAULT_KIND
    name = str(text or DEFAULT_TEXT).strip()[:MAX_TEXT] or DEFAULT_TEXT
    return {"kind": key, "text": name}


def load_presence() -> dict:
    path = _store_path()
    fallback = {
        "kind": DEFAULT_KIND,
        "text": DEFAULT_TEXT,
        "rotate": True,
        "index": 0,
    }
    if not path.exists():
        return dict(fallback)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return dict(fallback)
        item = _normalize_item(data.get("kind"), data.get("text"))
        rotate = data.get("rotate")
        if rotate is None:
            rotate = True
        try:
            index = int(data.get("index") or 0)
        except (TypeError, ValueError):
            index = 0
        if index < 0:
            index = 0
        index %= len(DEFAULT_ROTATION)
        return {
            "kind": item["kind"],
            "text": item["text"],
            "rotate": bool(rotate),
            "index": index,
        }
    except Exception:
        logger.exception("presence store read failed")
        return dict(fallback)


def _write_store(payload: dict) -> dict:
    clean = {
        "kind": payload["kind"],
        "text": payload["text"],
        "rotate": bool(payload.get("rotate", True)),
        "index": int(payload.get("index") or 0) % len(DEFAULT_ROTATION),
    }
    _store_path().write_text(json.dumps(clean, indent=2), encoding="utf-8")
    return clean


def save_presence(kind: str, text: str, rotate: bool | None = None) -> dict:
    stored = load_presence()
    item = _normalize_item(kind, text)
    stored["kind"] = item["kind"]
    stored["text"] = item["text"]
    if rotate is not None:
        stored["rotate"] = bool(rotate)
    return _write_store(stored)


def pin_presence(kind: str, text: str) -> dict:
    item = _normalize_item(kind, text)
    return _write_store({"kind": item["kind"], "text": item["text"], "rotate": False, "index": 0})


def enable_rotation(index: int = 0) -> dict:
    item = DEFAULT_ROTATION[index % len(DEFAULT_ROTATION)]
    return _write_store({"kind": item["kind"], "text": item["text"], "rotate": True, "index": index % len(DEFAULT_ROTATION)})


def advance_rotation() -> dict:
    stored = load_presence()
    nxt = (int(stored.get("index") or 0) + 1) % len(DEFAULT_ROTATION)
    item = DEFAULT_ROTATION[nxt]
    return _write_store({"kind": item["kind"], "text": item["text"], "rotate": True, "index": nxt})


def is_status_owner(user_id: int | None) -> bool:
    try:
        return int(user_id or 0) == int(CREATOR_DISCORD_ID)
    except (TypeError, ValueError):
        return False


def build_activity(kind: str, text: str):
    item = _normalize_item(kind, text)
    name = item["text"]
    key = item["kind"]
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


async def _rotation_loop(client) -> None:
    while True:
        try:
            await asyncio.sleep(ROTATION_SECONDS)
            stored = load_presence()
            if not stored.get("rotate", True):
                continue
            nxt = advance_rotation()
            await apply_presence(client, nxt["kind"], nxt["text"])
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("presence rotation tick failed")


def start_presence_loop(client) -> None:
    global _rotation_task
    task = _rotation_task
    if task is not None and not task.done():
        return
    _rotation_task = asyncio.create_task(_rotation_loop(client), name="aetherion-presence-rotation")
