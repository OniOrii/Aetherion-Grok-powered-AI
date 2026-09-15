"""Flatten Discord embeds so replies to game boards keep the result text."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("aetherion.embed_text")


def flatten_referenced_text(referenced: Any) -> str:
    parts: list[str] = []
    raw = (getattr(referenced, "content", "") or "").strip()
    if raw:
        parts.append(raw)
    for emb in getattr(referenced, "embeds", []) or []:
        title = (getattr(emb, "title", None) or "").strip()
        desc = (getattr(emb, "description", None) or "").strip()
        if title:
            parts.append(title)
        if desc:
            parts.append(desc)
        for field in getattr(emb, "fields", []) or []:
            name = (getattr(field, "name", None) or "").strip()
            value = (getattr(field, "value", None) or "").strip()
            bit = ": ".join(piece for piece in (name, value) if piece)
            if bit:
                parts.append(bit)
        footer = getattr(emb, "footer", None)
        footer_text = (getattr(footer, "text", None) or "").strip() if footer else ""
        if footer_text:
            parts.append(footer_text)
    seen: set[str] = set()
    ordered: list[str] = []
    for part in parts:
        if part not in seen:
            seen.add(part)
            ordered.append(part)
    return " | ".join(ordered)


def enrich_referenced_context(referenced: Any, ctx: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(ctx or {})
    flat = flatten_referenced_text(referenced)
    if flat:
        out["content"] = flat[:700]
    image_urls = list(out.get("image_urls") or [])
    for emb in getattr(referenced, "embeds", []) or []:
        for key in ("image", "thumbnail"):
            obj = getattr(emb, key, None)
            url = getattr(obj, "url", None) if obj else None
            if url and url not in image_urls:
                image_urls.append(url)
    if image_urls:
        out["image_urls"] = image_urls
    return out


def remember_connect4(match: Any) -> None:
    line = (
        f"Connect Four: {getattr(match, 'p1_name', '?')} (Red) vs "
        f"{getattr(match, 'p2_name', '?')} (Gold). "
        f"{getattr(match, 'reason', None) or 'Game over.'}"
    )
    try:
        from .core import update_from_message
        update_from_message(
            channel_id=int(getattr(match, "channel_id", 0) or 0),
            user_id=0,
            author_name="Aetherion",
            content=line,
            is_bot=True,
        )
    except Exception:
        logger.debug("connect4 channel memory skipped", exc_info=True)
    try:
        from .short_memory import record_turn
        record_turn(getattr(match, "p1", None), "[connect four]", line)
        if not getattr(match, "vs_bot", True):
            record_turn(getattr(match, "p2", None), "[connect four]", line)
    except Exception:
        logger.debug("connect4 short memory skipped", exc_info=True)


def patch_runtime_hooks() -> None:
    try:
        from ..core import conversation

        orig = conversation._build_referenced_context

        async def wrapped(referenced: Any) -> dict[str, Any]:
            ctx = await orig(referenced)
            return enrich_referenced_context(referenced, ctx)

        conversation._build_referenced_context = wrapped
    except Exception:
        logger.debug("reply embed hook skipped", exc_info=True)

    try:
        from ..discord import slash_connect4

        orig_finish = slash_connect4._finish

        def wrapped_finish(match: Any, *, winner: int = 0, reason: str = "") -> None:
            orig_finish(match, winner=winner, reason=reason)
            remember_connect4(match)

        slash_connect4._finish = wrapped_finish
    except Exception:
        logger.debug("connect4 memory hook skipped", exc_info=True)
