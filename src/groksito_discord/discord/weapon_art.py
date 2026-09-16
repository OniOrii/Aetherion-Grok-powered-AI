"""Small painted weapon icons for Hunt crate, equip, and inventory."""
from __future__ import annotations

import hashlib
import io
from typing import Any

from PIL import Image, ImageDraw

from .aether_gear import COMMON, RARITY_LABEL, WEAPON_BY_ID

RARITY_COLOR = {
    "common": (196, 72, 72),
    "uncommon": (56, 158, 88),
    "rare": (214, 176, 48),
    "epic": (72, 128, 214),
    "mythic": (156, 88, 214),
}


def _kind_colors(kind: str) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    digest = hashlib.md5((kind or "weapon").encode()).hexdigest()
    ink = (16 + int(digest[0:2], 16) % 40, 18 + int(digest[2:4], 16) % 36, 28 + int(digest[4:6], 16) % 50)
    glow = (90 + int(digest[6:8], 16) % 140, 80 + int(digest[8:10], 16) % 140, 70 + int(digest[10:12], 16) % 160)
    return ink, glow


def weapon_icon_png(kind: str, rarity: str | None = None, size: int = 96) -> io.BytesIO:
    rarity = rarity if rarity in RARITY_COLOR else COMMON
    ink, glow = _kind_colors(kind)
    img = Image.new("RGBA", (size, size), (12, 10, 18, 255))
    draw = ImageDraw.Draw(img)
    rim = RARITY_COLOR[rarity]
    draw.rounded_rectangle((2, 2, size - 3, size - 3), radius=14, outline=rim + (255,), width=4)
    draw.rounded_rectangle((8, 8, size - 9, size - 9), radius=10, fill=(24, 20, 32, 255))
    style = (WEAPON_BY_ID.get(kind) or ("", "", "", "strike"))[3]
    cx = cy = size // 2
    if style == "mend":
        draw.ellipse((cx - 22, cy - 22, cx + 22, cy + 22), outline=glow + (255,), width=5)
        draw.ellipse((cx - 8, cy - 8, cx + 8, cy + 8), fill=glow + (255,))
        draw.rectangle((cx - 3, cy - 26, cx + 3, cy + 26), fill=rim + (255,))
        draw.rectangle((cx - 26, cy - 3, cx + 26, cy + 3), fill=rim + (255,))
    elif style == "cleave":
        draw.polygon([(cx - 8, cy + 28), (cx + 6, cy + 24), (cx + 18, cy - 26), (cx - 2, cy - 30)], fill=glow + (255,))
        draw.rectangle((cx - 6, cy + 10, cx + 6, cy + 34), fill=ink + (255,))
        draw.polygon([(cx + 4, cy - 28), (cx + 28, cy - 18), (cx + 10, cy - 8)], fill=rim + (255,))
    else:
        draw.polygon([(cx - 6, cy + 30), (cx + 6, cy + 30), (cx + 4, cy - 8), (cx - 4, cy - 8)], fill=ink + (255,))
        draw.polygon([(cx - 20, cy - 6), (cx + 26, cy - 28), (cx + 22, cy - 8), (cx - 16, cy + 8)], fill=glow + (255,))
        draw.polygon([(cx + 8, cy - 30), (cx + 30, cy - 22), (cx + 18, cy - 10)], fill=rim + (255,))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    buf.name = f"{kind or 'weapon'}.png"
    return buf


def inventory_sheet_png(blob: dict[str, Any], limit: int = 8) -> io.BytesIO | None:
    rows = []
    for wid, raw in list((blob.get("weapons") or {}).items())[:limit]:
        if not isinstance(raw, dict):
            continue
        meta = WEAPON_BY_ID.get(raw.get("kind"))
        if not meta:
            continue
        rows.append((wid, meta[0], meta[1], raw.get("rarity") or COMMON, int(raw.get("atk") or 0)))
    if not rows:
        return None
    tile = 56
    img = Image.new("RGBA", (420, 12 + len(rows) * (tile + 8)), (16, 14, 22, 255))
    draw = ImageDraw.Draw(img)
    y = 8
    for wid, kind, name, rar, atk in rows:
        icon = Image.open(weapon_icon_png(kind, rar, size=tile)).convert("RGBA")
        img.paste(icon, (8, y), icon)
        draw.text((tile + 20, y + 10), f"#{wid}  {name}", fill=(235, 228, 210, 255))
        draw.text((tile + 20, y + 30), f"{RARITY_LABEL.get(rar, rar)}  +{atk} ATK", fill=RARITY_COLOR.get(rar, (180, 180, 180)) + (255,))
        y += tile + 8
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    buf.name = "inventory_weapons.png"
    return buf
