"""Aetherion Hunt rarity letter badges + Discord mark resolver.

PNG tiles live under ``assets/hunt_ranks/`` (original Aetherion art — not OwO).
Discord cannot inline arbitrary PNGs in message text, so ``rarity_mark()`` returns:

1. Configured custom emoji markup from settings/env (``HUNT_RANK_EMOJI_*``), or
2. A unicode color-square + capital letter fallback until Ori uploads the PNGs.
"""
from __future__ import annotations

from pathlib import Path

COMMON, UNCOMMON, RARE, EPIC, MYTHIC, ASTRAL, PRIMORDIAL = (
    "common",
    "uncommon",
    "rare",
    "epic",
    "mythic",
    "astral",
    "primordial",
)

# Suggested Discord emoji names when uploading the PNGs as app/guild emojis.
SUGGESTED_EMOJI_NAMES = {
    COMMON: "aether_c",
    UNCOMMON: "aether_u",
    RARE: "aether_r",
    EPIC: "aether_e",
    MYTHIC: "aether_m",
    ASTRAL: "aether_a",
    PRIMORDIAL: "aether_p",
}

# Fill hex for the generated PNG tiles (and embed tint alignment).
RANK_FILL_HEX = {
    COMMON: "#9A4442",
    UNCOMMON: "#388B9A",
    RARE: "#D4A746",
    EPIC: "#4057E1",
    MYTHIC: "#9558EF",
    ASTRAL: "#7EC8FF",
    PRIMORDIAL: "#C45C26",
}

# Readable mid-message fallback (Discord cannot show the PNGs inline without IDs).
# Squares approximate the badge fills: brick / teal / gold / blue / purple / cyan / ember.
UNICODE_FALLBACK = {
    COMMON: "\U0001f7e5C",       # 🟥C
    UNCOMMON: "\U0001fa75U",     # 🩵U (closest teal-ish)
    RARE: "\U0001f7e8R",         # 🟨R
    EPIC: "\U0001f7e6E",         # 🟦E
    MYTHIC: "\U0001f7eaM",       # 🟪M
    ASTRAL: "\U0001f535A",       # 🔵A (starlight cyan stand-in)
    PRIMORDIAL: "\U0001f7e7P",   # 🟧P
}

_SETTINGS_ATTR = {
    COMMON: "hunt_rank_emoji_common",
    UNCOMMON: "hunt_rank_emoji_uncommon",
    RARE: "hunt_rank_emoji_rare",
    EPIC: "hunt_rank_emoji_epic",
    MYTHIC: "hunt_rank_emoji_mythic",
    ASTRAL: "hunt_rank_emoji_astral",
    PRIMORDIAL: "hunt_rank_emoji_primordial",
}

_PNG_FILES = {
    COMMON: "rank_c.png",
    UNCOMMON: "rank_u.png",
    RARE: "rank_r.png",
    EPIC: "rank_e.png",
    MYTHIC: "rank_m.png",
    ASTRAL: "rank_a.png",
    PRIMORDIAL: "rank_p.png",
}

ASSETS_DIR = Path(__file__).resolve().parent / "assets" / "hunt_ranks"


def rank_png_path(rarity: str) -> Path | None:
    """Return the on-disk PNG for a rarity, or None if missing."""
    name = _PNG_FILES.get((rarity or "").lower())
    if not name:
        return None
    path = ASSETS_DIR / name
    return path if path.is_file() else None


def rank_png_bytes(rarity: str) -> bytes | None:
    path = rank_png_path(rarity)
    if path is None:
        return None
    return path.read_bytes()


def _configured_emoji(rarity: str) -> str:
    attr = _SETTINGS_ATTR.get((rarity or "").lower())
    if not attr:
        return ""
    try:
        from ..config import settings
    except Exception:
        return ""
    raw = getattr(settings, attr, None)
    if raw is None:
        return ""
    text = str(raw).strip()
    return text


def rarity_mark(rarity: str) -> str:
    """Discord-usable rarity mark for catch/zoo/checklist/gear lines.

    Prefers ``<:name:id>`` (or ``<a:name:id>``) from settings when set.
    Otherwise returns a unicode square + capital letter fallback.
    """
    key = (rarity or COMMON).lower()
    configured = _configured_emoji(key)
    if configured:
        return configured
    return UNICODE_FALLBACK.get(key, UNICODE_FALLBACK[COMMON])


class _RarityMarkMap:
    """Dict-like view so ``RARITY_MARK[rar]`` / ``.get`` stay settings-aware."""

    def __getitem__(self, rarity: str) -> str:
        return rarity_mark(rarity)

    def get(self, rarity: str, default: str | None = None) -> str | None:
        key = (rarity or "").lower()
        if key not in UNICODE_FALLBACK and key not in _SETTINGS_ATTR:
            return default
        return rarity_mark(key)

    def __contains__(self, rarity: object) -> bool:
        return isinstance(rarity, str) and rarity.lower() in UNICODE_FALLBACK


RARITY_MARK = _RarityMarkMap()
