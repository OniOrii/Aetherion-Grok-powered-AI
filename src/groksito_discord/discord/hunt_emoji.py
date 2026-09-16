"""Aetherion Hunt custom emoji resolver (HUD / animals / weapons).

Discord cannot inline arbitrary PNGs in message text. Upload PNGs from
``assets/hunt_icons/`` (HUD) and ``assets/hunt_portraits/`` (animals) as
app/guild emojis, then set env keys to full ``<:name:id>`` markup.

Until IDs are set, helpers return unicode fallbacks so /team and tests keep
working without any Discord upload.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent / "assets" / "hunt_icons"
PORTRAIT_DIR = Path(__file__).resolve().parent / "assets" / "hunt_portraits"

# Suggested Discord emoji names when uploading the HUD PNGs.
SUGGESTED_STAT_NAMES = {
    "hp": "hunt_hp",
    "wp": "hunt_wp",
    "atk": "hunt_atk",
    "phys": "hunt_atk",  # alias of atk
    "mag": "hunt_mag",
    "pr": "hunt_pr",
    "mr": "hunt_mr",
}

# Settings attribute names for HUD stats (pydantic fields).
_STAT_SETTINGS_ATTR = {
    "hp": "hunt_emoji_hp",
    "wp": "hunt_emoji_wp",
    "atk": "hunt_emoji_atk",
    "phys": "hunt_emoji_atk",
    "mag": "hunt_emoji_mag",
    "pr": "hunt_emoji_pr",
    "mr": "hunt_emoji_mr",
}

# Match current /team color grouping: reds = H/P/p, blues = W/M/m.
STAT_UNICODE_FALLBACK = {
    "hp": "\U0001f7e5",    # 🟥
    "wp": "\U0001f7e6",    # 🟦
    "atk": "\U0001f7e5",   # 🟥 physical ATK
    "phys": "\U0001f7e5",
    "mag": "\U0001f7e6",   # 🟦
    "pr": "\U0001f7e5",    # 🟥
    "mr": "\U0001f7e6",    # 🟦
}

_STAT_PNG = {
    "hp": "hp.png",
    "wp": "wp.png",
    "atk": "atk.png",
    "phys": "phys.png",
    "mag": "mag.png",
    "pr": "pr.png",
    "mr": "mr.png",
}

_CUSTOM_EMOJI_RE = re.compile(r"^<a?:\w+:\d+>$")
_WEAPON_ROW_PREFIX_DEFAULT = "\u2694\ufe0f"  # ⚔️


def _strip_markup(raw: str | None) -> str:
    if raw is None:
        return ""
    text = str(raw).strip()
    return text


def _looks_like_custom_emoji(text: str) -> bool:
    return bool(text) and bool(_CUSTOM_EMOJI_RE.match(text))


def _from_settings(attr: str) -> str:
    try:
        from ..config import settings
    except Exception:
        return ""
    return _strip_markup(getattr(settings, attr, None))


def _from_env(key: str) -> str:
    return _strip_markup(os.environ.get(key, ""))


def stat_png_path(stat: str) -> Path | None:
    """On-disk HUD PNG for upload, or None if missing."""
    name = _STAT_PNG.get((stat or "").lower())
    if not name:
        return None
    path = ASSETS_DIR / name
    return path if path.is_file() else None


def animal_portrait_path(animal_id: str) -> Path | None:
    """Reuse hunt_portraits/{id}.png — do not duplicate binaries under hunt_icons."""
    aid = (animal_id or "").strip().lower()
    if not aid:
        return None
    path = PORTRAIT_DIR / f"{aid}.png"
    return path if path.is_file() else None


def stat_mark(stat: str) -> str:
    """Discord-usable HUD mark for HP/WP/ATK/MAG/PR/MR.

    Prefers ``HUNT_EMOJI_{STAT}`` / settings when set; else unicode square
    matching the existing /team red/blue grouping.
    """
    key = (stat or "").lower()
    if key not in STAT_UNICODE_FALLBACK:
        return STAT_UNICODE_FALLBACK["hp"]
    attr = _STAT_SETTINGS_ATTR.get(key)
    configured = _from_settings(attr) if attr else ""
    if not configured:
        # Allow direct env even if settings object is stale / unloaded.
        env_key = f"HUNT_EMOJI_{'ATK' if key == 'phys' else key.upper()}"
        configured = _from_env(env_key)
    if configured:
        return configured
    return STAT_UNICODE_FALLBACK[key]


def animal_mark(animal_id: str, *, unicode_fallback: str | None = None) -> str:
    """Animal avatar emoji: ``HUNT_EMOJI_ANIMAL_<id>`` or unicode species glyph."""
    aid = (animal_id or "").strip().lower()
    if not aid:
        return unicode_fallback or ""
    # Prefer explicit env (optional per-animal override). Accept upper or lower id.
    for key in (f"HUNT_EMOJI_ANIMAL_{aid.upper()}", f"HUNT_EMOJI_ANIMAL_{aid}"):
        configured = _from_env(key)
        if configured:
            return configured
    if unicode_fallback is not None:
        return unicode_fallback
    try:
        from .aether_hunt import ANIMAL_BY_ID
    except Exception:
        return ""
    row = ANIMAL_BY_ID.get(aid)
    return str(row[2]) if row else ""


def weapon_mark(kind: str | None, *, unicode_fallback: str | None = None) -> str:
    """Weapon emoji override: ``HUNT_EMOJI_WEAPON_<kind>`` or fallback glyph."""
    kid = (kind or "").strip().lower()
    if kid:
        for key in (f"HUNT_EMOJI_WEAPON_{kid.upper()}", f"HUNT_EMOJI_WEAPON_{kid}"):
            configured = _from_env(key)
            if configured:
                return configured
    return unicode_fallback or ""


def weapon_row_prefix() -> str:
    """Prefix for equipped weapon rows on /team (default ⚔️)."""
    configured = _from_settings("hunt_emoji_weapon_row") or _from_env("HUNT_EMOJI_WEAPON_ROW")
    return configured or _WEAPON_ROW_PREFIX_DEFAULT


def resolve_emoji(raw: str | None, *, fallback: str = "") -> str:
    """Normalize a configured value to Discord markup, else *fallback*."""
    text = _strip_markup(raw)
    if not text:
        return fallback
    return text
