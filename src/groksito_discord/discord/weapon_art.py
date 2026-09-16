"""Small painted weapon icons for Hunt crate, equip, and inventory."""
from __future__ import annotations

import io
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .aether_gear import COMMON, RARITY_LABEL, WEAPON_BY_ID

RARITY_COLOR = {
    "common": (196, 72, 72),
    "uncommon": (56, 158, 88),
    "rare": (214, 176, 48),
    "epic": (72, 128, 214),
    "mythic": (156, 88, 214),
}

_FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# Per-kind draw recipe → distinct silhouette at Discord thumbnail size.
# Keys are weapon kind ids from aether_gear.WEAPONS.
_KIND_SHAPE = {
    "rift_blade": "blade",
    "ember_bow": "bow",
    "ash_spear": "spear",
    "peat_knife": "dagger",
    "copper_axe": "axe",
    "moss_club": "club",
    "glass_rapier": "rapier",
    "storm_hammer": "hammer",
    "tide_trident": "trident",
    "thorn_flail": "flail",
    "cinder_maul": "hammer",
    "quartz_wand": "wand",
    "void_scythe": "scythe",
    "aurora_lance": "spear",
    "moon_fan": "fan",
    "star_chakram": "chakram",
    "aether_scepter": "scepter",
    "eclipse_glaive": "glaive",
    "grave_pick": "pick",
    "crown_halberd": "halberd",
    "sol_brand": "blade",
    "fog_needle": "needle",
    "river_hook": "hook",
    "lantern_staff": "staff",
    "weed_sling": "sling",
    "clay_shield": "shield",
    "iron_gauntlet": "gauntlet",
    "drift_javelin": "spear",
    "prism_orb": "orb",
    "wyrm_fang": "fang",
    "mist_dagger": "dagger",
    "peat_mace": "mace",
    "sol_crossbow": "crossbow",
    "void_orb": "orb",
    "storm_cleaver": "cleaver",
    "glass_shard": "shard",
    "moon_censer": "censer",
    "ember_chain": "chain",
    "rift_pike": "spear",
    "aether_tome": "tome",
    "peat_sickle": "sickle",
    "prism_blade": "blade",
}


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    path = _FONT_BOLD if bold else _FONT_REG
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def _style_fallback(style: str) -> str:
    return {"mend": "wand", "cleave": "axe", "strike": "blade"}.get(style or "strike", "blade")


def _draw_shape(draw: ImageDraw.ImageDraw, shape: str, cx: int, cy: int, ink, glow, rim) -> None:
    """Paint a readable weapon silhouette; shapes stay distinct when downscaled."""
    if shape == "bow":
        draw.arc((cx - 26, cy - 28, cx + 10, cy + 28), 270, 90, fill=glow + (255,), width=5)
        draw.line((cx + 8, cy - 26, cx + 8, cy + 26), fill=ink + (255,), width=3)
        draw.line((cx + 8, cy, cx + 26, cy), fill=rim + (255,), width=3)
    elif shape == "crossbow":
        draw.rectangle((cx - 4, cy - 26, cx + 4, cy + 26), fill=ink + (255,))
        draw.rectangle((cx - 24, cy - 6, cx + 18, cy + 6), fill=glow + (255,))
        draw.polygon([(cx + 18, cy), (cx + 30, cy - 8), (cx + 30, cy + 8)], fill=rim + (255,))
    elif shape == "axe":
        draw.rectangle((cx - 4, cy - 8, cx + 4, cy + 30), fill=ink + (255,))
        draw.pieslice((cx - 8, cy - 28, cx + 30, cy + 8), 200, 40, fill=glow + (255,))
        draw.arc((cx - 8, cy - 28, cx + 30, cy + 8), 200, 40, fill=rim + (255,), width=3)
    elif shape == "cleaver":
        draw.rectangle((cx - 6, cy + 4, cx + 4, cy + 30), fill=ink + (255,))
        draw.polygon([(cx - 8, cy + 6), (cx + 28, cy - 26), (cx + 28, cy + 2), (cx - 4, cy + 10)], fill=glow + (255,))
    elif shape == "hammer":
        draw.rectangle((cx - 4, cy - 4, cx + 4, cy + 30), fill=ink + (255,))
        draw.rounded_rectangle((cx - 22, cy - 28, cx + 22, cy - 4), radius=4, fill=glow + (255,))
        draw.rectangle((cx - 22, cy - 18, cx + 22, cy - 12), fill=rim + (255,))
    elif shape == "mace":
        draw.rectangle((cx - 3, cy - 4, cx + 3, cy + 30), fill=ink + (255,))
        draw.ellipse((cx - 16, cy - 28, cx + 16, cy - 2), fill=glow + (255,))
        for ang in (-18, 0, 18):
            draw.ellipse((cx + ang - 4, cy - 30, cx + ang + 4, cy - 22), fill=rim + (255,))
    elif shape == "club":
        draw.polygon([(cx - 8, cy + 28), (cx + 8, cy + 28), (cx + 14, cy - 20), (cx - 10, cy - 16)], fill=glow + (255,))
        draw.ellipse((cx - 12, cy - 28, cx + 16, cy - 6), fill=rim + (255,))
    elif shape == "spear":
        draw.rectangle((cx - 3, cy - 8, cx + 3, cy + 32), fill=ink + (255,))
        draw.polygon([(cx, cy - 32), (cx - 12, cy - 8), (cx + 12, cy - 8)], fill=glow + (255,))
        draw.rectangle((cx - 10, cy + 6, cx + 10, cy + 10), fill=rim + (255,))
    elif shape == "trident":
        draw.rectangle((cx - 3, cy - 4, cx + 3, cy + 30), fill=ink + (255,))
        for dx in (-14, 0, 14):
            draw.polygon([(cx + dx, cy - 30), (cx + dx - 5, cy - 10), (cx + dx + 5, cy - 10)], fill=glow + (255,))
        draw.arc((cx - 18, cy - 16, cx + 18, cy + 4), 200, 340, fill=rim + (255,), width=3)
    elif shape == "halberd":
        draw.rectangle((cx - 3, cy - 6, cx + 3, cy + 30), fill=ink + (255,))
        draw.polygon([(cx, cy - 32), (cx - 10, cy - 10), (cx + 10, cy - 10)], fill=glow + (255,))
        draw.polygon([(cx + 2, cy - 8), (cx + 26, cy - 18), (cx + 22, cy - 2)], fill=rim + (255,))
    elif shape == "glaive":
        draw.rectangle((cx - 3, cy + 2, cx + 3, cy + 30), fill=ink + (255,))
        draw.polygon([(cx - 6, cy + 4), (cx + 8, cy - 30), (cx + 22, cy - 18), (cx + 6, cy + 8)], fill=glow + (255,))
    elif shape == "scythe":
        draw.rectangle((cx - 4, cy - 10, cx + 2, cy + 30), fill=ink + (255,))
        draw.pieslice((cx - 6, cy - 32, cx + 30, cy + 6), 220, 20, fill=glow + (255,))
        draw.arc((cx - 6, cy - 32, cx + 30, cy + 6), 220, 20, fill=rim + (255,), width=3)
    elif shape == "sickle":
        draw.rectangle((cx - 2, cy - 2, cx + 4, cy + 26), fill=ink + (255,))
        draw.arc((cx - 22, cy - 28, cx + 14, cy + 8), 200, 50, fill=glow + (255,), width=6)
    elif shape == "dagger":
        draw.polygon([(cx - 5, cy + 18), (cx + 5, cy + 18), (cx + 3, cy - 6), (cx - 3, cy - 6)], fill=ink + (255,))
        draw.polygon([(cx - 10, cy - 4), (cx + 18, cy - 28), (cx + 14, cy - 8), (cx - 8, cy + 4)], fill=glow + (255,))
        draw.rectangle((cx - 12, cy + 14, cx + 12, cy + 20), fill=rim + (255,))
    elif shape == "rapier":
        draw.rectangle((cx - 2, cy - 8, cx + 2, cy + 30), fill=ink + (255,))
        draw.polygon([(cx, cy - 32), (cx - 6, cy - 10), (cx + 6, cy - 10)], fill=glow + (255,))
        draw.ellipse((cx - 14, cy + 8, cx + 14, cy + 20), outline=rim + (255,), width=3)
    elif shape == "blade":
        draw.polygon([(cx - 6, cy + 28), (cx + 6, cy + 28), (cx + 4, cy - 6), (cx - 4, cy - 6)], fill=ink + (255,))
        draw.polygon([(cx - 16, cy - 4), (cx + 24, cy - 28), (cx + 20, cy - 8), (cx - 12, cy + 6)], fill=glow + (255,))
        draw.polygon([(cx + 6, cy - 30), (cx + 28, cy - 20), (cx + 16, cy - 8)], fill=rim + (255,))
    elif shape == "fang":
        draw.polygon([(cx - 8, cy + 26), (cx + 10, cy + 20), (cx + 4, cy - 28), (cx - 14, cy - 10)], fill=glow + (255,))
        draw.polygon([(cx - 4, cy + 10), (cx + 6, cy + 6), (cx + 2, cy - 18)], fill=rim + (255,))
    elif shape == "shard":
        draw.polygon([(cx, cy - 28), (cx + 16, cy - 4), (cx + 6, cy + 26), (cx - 14, cy + 8), (cx - 10, cy - 12)], fill=glow + (255,))
        draw.line((cx - 4, cy - 16, cx + 8, cy + 14), fill=rim + (255,), width=2)
    elif shape == "pick":
        draw.rectangle((cx - 3, cy - 4, cx + 3, cy + 28), fill=ink + (255,))
        draw.polygon([(cx - 4, cy - 8), (cx - 26, cy - 22), (cx - 18, cy - 4)], fill=glow + (255,))
        draw.polygon([(cx + 4, cy - 8), (cx + 26, cy - 22), (cx + 18, cy - 4)], fill=glow + (255,))
    elif shape == "flail":
        draw.rectangle((cx - 3, cy + 4, cx + 3, cy + 28), fill=ink + (255,))
        draw.line((cx, cy + 4, cx + 18, cy - 18), fill=rim + (255,), width=3)
        draw.ellipse((cx + 10, cy - 28, cx + 28, cy - 10), fill=glow + (255,))
    elif shape == "chain":
        for i, y in enumerate((-18, -2, 14)):
            draw.ellipse((cx - 10 + (i % 2) * 4, cy + y - 8, cx + 10 + (i % 2) * 4, cy + y + 8), outline=glow + (255,), width=4)
        draw.ellipse((cx - 16, cy - 30, cx + 0, cy - 14), fill=rim + (255,))
    elif shape == "hook":
        draw.rectangle((cx - 3, cy - 8, cx + 3, cy + 26), fill=ink + (255,))
        draw.arc((cx - 4, cy - 28, cx + 24, cy + 4), 270, 90, fill=glow + (255,), width=5)
        draw.polygon([(cx + 20, cy - 4), (cx + 30, cy + 6), (cx + 14, cy + 4)], fill=rim + (255,))
    elif shape == "needle":
        draw.line((cx - 8, cy + 28, cx + 16, cy - 28), fill=glow + (255,), width=4)
        draw.ellipse((cx + 12, cy - 30, cx + 22, cy - 20), outline=rim + (255,), width=3)
    elif shape == "wand":
        draw.rectangle((cx - 3, cy - 6, cx + 3, cy + 28), fill=ink + (255,))
        draw.ellipse((cx - 14, cy - 30, cx + 14, cy - 4), outline=glow + (255,), width=4)
        draw.ellipse((cx - 5, cy - 20, cx + 5, cy - 10), fill=rim + (255,))
    elif shape == "staff":
        draw.rectangle((cx - 3, cy - 4, cx + 3, cy + 30), fill=ink + (255,))
        draw.rounded_rectangle((cx - 14, cy - 30, cx + 14, cy - 6), radius=6, fill=glow + (255,))
        draw.ellipse((cx - 6, cy - 22, cx + 6, cy - 10), fill=rim + (255,))
    elif shape == "scepter":
        draw.rectangle((cx - 3, cy - 2, cx + 3, cy + 30), fill=ink + (255,))
        draw.polygon([(cx, cy - 30), (cx - 14, cy - 8), (cx + 14, cy - 8)], fill=glow + (255,))
        draw.rectangle((cx - 10, cy - 8, cx + 10, cy - 2), fill=rim + (255,))
    elif shape == "orb":
        draw.ellipse((cx - 22, cy - 22, cx + 22, cy + 22), outline=glow + (255,), width=5)
        draw.ellipse((cx - 10, cy - 10, cx + 10, cy + 10), fill=rim + (255,))
        draw.ellipse((cx - 4, cy - 16, cx + 2, cy - 10), fill=(255, 255, 255, 200))
    elif shape == "tome":
        draw.rounded_rectangle((cx - 20, cy - 24, cx + 20, cy + 24), radius=4, fill=glow + (255,))
        draw.rectangle((cx - 2, cy - 22, cx + 2, cy + 22), fill=ink + (255,))
        draw.line((cx + 6, cy - 10, cx + 16, cy - 10), fill=rim + (255,), width=2)
        draw.line((cx + 6, cy, cx + 16, cy), fill=rim + (255,), width=2)
    elif shape == "fan":
        draw.pieslice((cx - 26, cy - 20, cx + 26, cy + 28), 200, 340, fill=glow + (255,))
        for a in (220, 250, 280, 310):
            draw.pieslice((cx - 26, cy - 20, cx + 26, cy + 28), a, a + 8, fill=rim + (255,))
        draw.rectangle((cx - 3, cy + 8, cx + 3, cy + 30), fill=ink + (255,))
    elif shape == "chakram":
        draw.ellipse((cx - 24, cy - 24, cx + 24, cy + 24), outline=glow + (255,), width=6)
        draw.ellipse((cx - 10, cy - 10, cx + 10, cy + 10), outline=rim + (255,), width=3)
        draw.polygon([(cx + 22, cy - 6), (cx + 32, cy), (cx + 22, cy + 6)], fill=rim + (255,))
    elif shape == "shield":
        draw.polygon([(cx, cy - 28), (cx + 24, cy - 14), (cx + 18, cy + 18), (cx, cy + 28), (cx - 18, cy + 18), (cx - 24, cy - 14)], fill=glow + (255,))
        draw.polygon([(cx, cy - 18), (cx + 12, cy - 8), (cx + 8, cy + 10), (cx, cy + 16), (cx - 8, cy + 10), (cx - 12, cy - 8)], fill=rim + (255,))
    elif shape == "gauntlet":
        draw.rounded_rectangle((cx - 16, cy - 8, cx + 16, cy + 26), radius=6, fill=glow + (255,))
        draw.rectangle((cx - 18, cy - 24, cx + 18, cy - 4), fill=ink + (255,))
        for dx in (-12, -4, 4, 12):
            draw.rectangle((cx + dx - 3, cy - 28, cx + dx + 3, cy - 16), fill=rim + (255,))
    elif shape == "censer":
        draw.polygon([(cx - 14, cy - 8), (cx + 14, cy - 8), (cx + 10, cy + 18), (cx - 10, cy + 18)], fill=glow + (255,))
        draw.arc((cx - 16, cy - 28, cx + 16, cy - 4), 200, 340, fill=rim + (255,), width=3)
        draw.ellipse((cx - 6, cy - 4, cx + 6, cy + 6), fill=rim + (255,))
    elif shape == "sling":
        draw.arc((cx - 22, cy - 20, cx + 22, cy + 24), 200, 340, fill=glow + (255,), width=4)
        draw.ellipse((cx - 8, cy + 14, cx + 8, cy + 28), fill=rim + (255,))
        draw.line((cx - 18, cy - 10, cx + 18, cy - 10), fill=ink + (255,), width=3)
    else:
        # generic blade
        draw.polygon([(cx - 6, cy + 28), (cx + 6, cy + 28), (cx + 4, cy - 6), (cx - 4, cy - 6)], fill=ink + (255,))
        draw.polygon([(cx - 16, cy - 4), (cx + 24, cy - 28), (cx + 20, cy - 8), (cx - 12, cy + 6)], fill=glow + (255,))


def weapon_icon_png(kind: str, rarity: str | None = None, size: int = 96) -> io.BytesIO:
    rarity = rarity if rarity in RARITY_COLOR else COMMON
    meta = WEAPON_BY_ID.get(kind) or ("", "", "", "strike")
    style = meta[3]
    shape = _KIND_SHAPE.get(kind) or _style_fallback(style)
    rim = RARITY_COLOR[rarity]
    # Kind-tinted metal/glow so icons differ even within the same shape family
    seed = sum(ord(c) for c in (kind or "weapon"))
    ink = (28 + seed % 40, 24 + (seed // 3) % 36, 34 + (seed // 7) % 40)
    glow = (
        min(255, rim[0] // 2 + 70 + seed % 50),
        min(255, rim[1] // 2 + 60 + (seed // 5) % 50),
        min(255, rim[2] // 2 + 50 + (seed // 11) % 60),
    )
    img = Image.new("RGBA", (size, size), (12, 10, 18, 255))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((2, 2, size - 3, size - 3), radius=14, outline=rim + (255,), width=4)
    # Soft rarity wash behind the silhouette
    wash = tuple(min(255, c // 3 + 18) for c in rim) + (255,)
    draw.rounded_rectangle((8, 8, size - 9, size - 9), radius=10, fill=wash)
    # Draw at a virtual 96 canvas then scale if needed
    if size != 96:
        base = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
        bd = ImageDraw.Draw(base)
        bd.rounded_rectangle((2, 2, 93, 93), radius=14, outline=rim + (255,), width=4)
        bd.rounded_rectangle((8, 8, 87, 87), radius=10, fill=wash)
        _draw_shape(bd, shape, 48, 48, ink, glow, rim)
        img = base.resize((size, size), Image.Resampling.LANCZOS)
    else:
        _draw_shape(draw, shape, size // 2, size // 2, ink, glow, rim)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    buf.name = f"{kind or 'weapon'}.png"
    return buf


def inventory_sheet_png(blob: dict[str, Any], limit: int = 8) -> io.BytesIO | None:
    """OwO-density inventory strip: id · rarity · name · quality% (+ ATK)."""
    rows = []
    for wid, raw in list((blob.get("weapons") or {}).items())[:limit]:
        if not isinstance(raw, dict):
            continue
        meta = WEAPON_BY_ID.get(raw.get("kind"))
        if not meta:
            continue
        rows.append(
            (
                wid,
                meta[0],
                meta[1],
                raw.get("rarity") or COMMON,
                int(raw.get("quality") or 0),
                int(raw.get("atk") or 0),
            )
        )
    if not rows:
        return None
    tile = 56
    width = 460
    img = Image.new("RGBA", (width, 12 + len(rows) * (tile + 8)), (16, 14, 22, 255))
    draw = ImageDraw.Draw(img)
    y = 8
    for wid, kind, name, rar, quality, atk in rows:
        icon = Image.open(weapon_icon_png(kind, rar, size=tile)).convert("RGBA")
        img.paste(icon, (8, y), icon)
        tint = RARITY_COLOR.get(rar, (180, 180, 180))
        draw.text((tile + 20, y + 6), f"#{wid}  {name}", font=_font(15, True), fill=(235, 228, 210, 255))
        draw.text(
            (tile + 20, y + 28),
            f"{RARITY_LABEL.get(rar, rar)}  ·  Quality: {quality}%  ·  +{atk} ATK",
            font=_font(12),
            fill=tint + (255,),
        )
        y += tile + 8
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    buf.name = "inventory_weapons.png"
    return buf
