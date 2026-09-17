#!/usr/bin/env python3
"""Generate richer Aetherion Hunt Discord app-emoji PNGs (Pillow).

Produces 128×128 RGBA PNGs (transparent bg, <256KB) for:
  - Rank badges  → assets/hunt_ranks/rank_{c,u,r,e,m,a,p}.png
  - HUD icons    → assets/hunt_icons/{hp,wp,atk,mag,pr,mr,phys}.png
  - Animals      → assets/hunt_animal_emojis/{id}.png
  - Weapons      → assets/hunt_weapon_emojis/{kind}.png

Original Aetherion art (OwO-class FEEL, not OwO assets). Re-run anytime;
overwrites existing files. Stdlib + Pillow only.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO = Path(__file__).resolve().parent.parent
ASSETS = REPO / "src" / "groksito_discord" / "discord" / "assets"
SIZE = 128
RANK_DIR = ASSETS / "hunt_ranks"
HUD_DIR = ASSETS / "hunt_icons"
ANIMAL_DIR = ASSETS / "hunt_animal_emojis"
WEAPON_DIR = ASSETS / "hunt_weapon_emojis"

# Anchor hues from hunt_ranks.RANK_FILL_HEX
RANK_SPEC = (
    ("c", "C", "#9A4442", "#5C2220", "#E8A09A", None),          # brick
    ("u", "U", "#388B9A", "#1E5560", "#9AD4E0", None),          # teal
    ("r", "R", "#D4A746", "#8A6A20", "#F5E0A0", None),          # gold
    ("e", "E", "#4057E1", "#24308A", "#A0B0FF", None),          # blue
    ("m", "M", "#9558EF", "#4A2080", "#D0B0FF", None),          # violet
    ("a", "A", "#7EC8FF", "#3A6A90", "#E8F6FF", "cyan_glow"),   # astral
    ("p", "P", "#C45C26", "#1A2A28", "#FFB070", "void_ember"),  # primordial
)

HUD_SPECS = (
    ("hp", "#C43C3C", "heart"),
    ("wp", "#3C6EC4", "spark"),
    ("atk", "#C45C2C", "sword"),
    ("phys", "#C45C2C", "sword"),
    ("mag", "#6C4CC4", "orb"),
    ("pr", "#3CA06C", "shield"),
    ("mr", "#4C8CC4", "shield_m"),
)

# Import catalog without loading full bot settings noise when possible.
sys.path.insert(0, str(REPO / "src"))


def _hex(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgba(h: str, a: int = 255) -> tuple[int, int, int, int]:
    r, g, b = _hex(h)
    return r, g, b, a


def _blend(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _save(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Ensure under 256KB; 128 RGBA PNG is tiny.
    img = img.convert("RGBA")
    img.save(path, "PNG", optimize=True)


def _rounded_rect(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    radius: int,
    fill: tuple[int, int, int, int] | None = None,
    outline: tuple[int, int, int, int] | None = None,
    width: int = 1,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


# ---------------------------------------------------------------------------
# Rank badges — richest detail
# ---------------------------------------------------------------------------

def generate_rank(letter_key: str, letter: str, fill: str, dark: str, light: str, special: str | None) -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    base = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)

    pad = 6
    box = (pad, pad, SIZE - pad - 1, SIZE - pad - 1)
    fill_rgb = _hex(fill)
    dark_rgb = _hex(dark)
    light_rgb = _hex(light)

    # Soft outer glow (especially astral / primordial)
    glow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    glow_col = _rgba(light if special == "cyan_glow" else fill, 110)
    if special == "void_ember":
        glow_col = (255, 120, 40, 90)
    elif special == "cyan_glow":
        glow_col = (126, 200, 255, 130)
    gd.rounded_rectangle((2, 2, SIZE - 3, SIZE - 3), radius=22, fill=glow_col)
    glow = glow.filter(ImageFilter.GaussianBlur(6))
    img = Image.alpha_composite(img, glow)

    # Beveled tile body
    _rounded_rect(d, box, 18, fill=_rgba(fill))
    # Top highlight band
    hi = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hi)
    hd.rounded_rectangle(box, radius=18, fill=(*light_rgb, 55))
    mask = Image.new("L", (SIZE, SIZE), 0)
    md = ImageDraw.Draw(mask)
    md.rectangle((pad, pad + 40, SIZE - pad, SIZE - pad), fill=255)
    hi.putalpha(ImageChops_subtract_safe(hi.split()[3], mask))
    base = Image.alpha_composite(base, hi)

    # Inner rim light
    _rounded_rect(
        d,
        (pad + 4, pad + 4, SIZE - pad - 5, SIZE - pad - 5),
        14,
        outline=(*light_rgb, 160),
        width=2,
    )
    # Dark outer stroke
    _rounded_rect(d, box, 18, outline=(*dark_rgb, 255), width=3)

    # Primordial void underlay + ember rim
    if special == "void_ember":
        void = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        vd = ImageDraw.Draw(void)
        vd.ellipse((28, 28, 100, 100), fill=(20, 40, 38, 90))
        base = Image.alpha_composite(base, void)
        _rounded_rect(d, box, 18, outline=(255, 140, 60, 200), width=2)

    # Astral silver-gold inner ring
    if special == "cyan_glow":
        _rounded_rect(
            d,
            (pad + 8, pad + 8, SIZE - pad - 9, SIZE - pad - 9),
            12,
            outline=(255, 230, 160, 180),
            width=2,
        )

    img = Image.alpha_composite(img, base)

    # Bold letter with outline + soft glow
    font = _font(78)
    # Measure
    tmp = ImageDraw.Draw(img)
    bbox = tmp.textbbox((0, 0), letter, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (SIZE - tw) // 2 - bbox[0]
    ty = (SIZE - th) // 2 - bbox[1] - 2

    letter_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ld = ImageDraw.Draw(letter_layer)
    # Outline
    for ox, oy in ((-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, -2), (-2, 2), (2, 2)):
        ld.text((tx + ox, ty + oy), letter, font=font, fill=(*dark_rgb, 255))
    # Fill
    ld.text((tx, ty), letter, font=font, fill=(255, 255, 255, 255))
    # Soft letter glow
    lg = letter_layer.filter(ImageFilter.GaussianBlur(2))
    img = Image.alpha_composite(img, lg)
    img = Image.alpha_composite(img, letter_layer)

    # Specular highlight corner
    spec = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    sd = ImageDraw.Draw(spec)
    sd.ellipse((18, 14, 48, 36), fill=(255, 255, 255, 70))
    spec = spec.filter(ImageFilter.GaussianBlur(3))
    img = Image.alpha_composite(img, spec)
    return img


def ImageChops_subtract_safe(a: Image.Image, b: Image.Image) -> Image.Image:
    """a - b per pixel, clamped (avoid importing ImageChops name clash)."""
    from PIL import ImageChops

    return ImageChops.subtract(a, b)


# ---------------------------------------------------------------------------
# HUD icons — bordered chips with mini symbols
# ---------------------------------------------------------------------------

def _chip_bg(accent: str) -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fill = _blend(_hex(accent), (30, 30, 40), 0.55)
    light = _blend(_hex(accent), (255, 255, 255), 0.35)
    dark = _blend(_hex(accent), (0, 0, 0), 0.45)
    pad = 8
    box = (pad, pad, SIZE - pad - 1, SIZE - pad - 1)
    glow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle((4, 4, SIZE - 5, SIZE - 5), radius=20, fill=(*_hex(accent), 70))
    glow = glow.filter(ImageFilter.GaussianBlur(5))
    img = Image.alpha_composite(img, glow)
    d = ImageDraw.Draw(img)
    _rounded_rect(d, box, 18, fill=(*fill, 255))
    _rounded_rect(d, box, 18, outline=(*light, 220), width=3)
    _rounded_rect(d, (pad + 5, pad + 5, SIZE - pad - 6, SIZE - pad - 6), 14, outline=(*dark, 180), width=2)
    # top sheen
    sheen = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(sheen).rounded_rectangle(box, radius=18, fill=(255, 255, 255, 40))
    m = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(m).rectangle((0, SIZE // 2, SIZE, SIZE), fill=255)
    from PIL import ImageChops

    sheen.putalpha(ImageChops.subtract(sheen.split()[3], m))
    img = Image.alpha_composite(img, sheen)
    return img


def _draw_heart(d: ImageDraw.ImageDraw, cx: int, cy: int, s: int, fill, outline) -> None:
    # Two circles + triangle
    r = s // 3
    d.ellipse((cx - s // 2, cy - s // 3 - r // 2, cx, cy - s // 3 + r), fill=fill, outline=outline, width=2)
    d.ellipse((cx, cy - s // 3 - r // 2, cx + s // 2, cy - s // 3 + r), fill=fill, outline=outline, width=2)
    d.polygon(
        [(cx - s // 2, cy - s // 8), (cx + s // 2, cy - s // 8), (cx, cy + s // 2)],
        fill=fill,
        outline=outline,
    )


def _draw_spark(d: ImageDraw.ImageDraw, cx: int, cy: int, s: int, fill, outline) -> None:
    pts = []
    for i in range(8):
        ang = math.radians(i * 45 - 90)
        r = s // 2 if i % 2 == 0 else s // 5
        pts.append((cx + int(math.cos(ang) * r), cy + int(math.sin(ang) * r)))
    d.polygon(pts, fill=fill, outline=outline)


def _draw_sword(d: ImageDraw.ImageDraw, cx: int, cy: int, s: int, fill, outline) -> None:
    # Blade
    d.polygon(
        [(cx, cy - s // 2), (cx + 8, cy + s // 6), (cx, cy + s // 4), (cx - 8, cy + s // 6)],
        fill=fill,
        outline=outline,
    )
    # Guard
    d.rectangle((cx - 18, cy + s // 6, cx + 18, cy + s // 6 + 8), fill=outline, outline=outline)
    # Hilt
    d.rectangle((cx - 5, cy + s // 6 + 8, cx + 5, cy + s // 2), fill=_blend(fill[:3] if len(fill) == 4 else fill, (40, 30, 20), 0.3) + (255,), outline=outline)


def _draw_orb(d: ImageDraw.ImageDraw, cx: int, cy: int, s: int, fill, outline) -> None:
    d.ellipse((cx - s // 2, cy - s // 2, cx + s // 2, cy + s // 2), fill=fill, outline=outline, width=3)
    d.ellipse((cx - s // 5, cy - s // 3, cx + s // 8, cy - s // 10), fill=(255, 255, 255, 160))


def _draw_shield(d: ImageDraw.ImageDraw, cx: int, cy: int, s: int, fill, outline, mag: bool = False) -> None:
    top = cy - s // 2
    bot = cy + s // 2
    pts = [
        (cx - s // 2, top + 8),
        (cx - s // 2 + 4, top),
        (cx + s // 2 - 4, top),
        (cx + s // 2, top + 8),
        (cx + s // 3, cy + s // 8),
        (cx, bot),
        (cx - s // 3, cy + s // 8),
    ]
    d.polygon(pts, fill=fill, outline=outline)
    if mag:
        d.ellipse((cx - 10, cy - 12, cx + 10, cy + 8), outline=(255, 255, 255, 200), width=2)
    else:
        d.line([(cx, top + 10), (cx, bot - 8)], fill=(255, 255, 255, 180), width=3)


def generate_hud(key: str, accent: str, motif: str) -> Image.Image:
    img = _chip_bg(accent)
    overlay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    fill = (*_hex(accent), 255)
    outline = (20, 16, 24, 255)
    light = (*_blend(_hex(accent), (255, 255, 255), 0.5), 255)
    cx, cy, s = SIZE // 2, SIZE // 2 + 2, 54
    if motif == "heart":
        _draw_heart(d, cx, cy, s, fill, outline)
    elif motif == "spark":
        _draw_spark(d, cx, cy, s, light, outline)
    elif motif == "sword":
        _draw_sword(d, cx, cy - 2, s + 4, light, outline)
    elif motif == "orb":
        _draw_orb(d, cx, cy, s - 4, fill, outline)
    elif motif == "shield":
        _draw_shield(d, cx, cy, s, fill, outline, mag=False)
    elif motif == "shield_m":
        _draw_shield(d, cx, cy, s, fill, outline, mag=True)
    img = Image.alpha_composite(img, overlay)
    return img


# ---------------------------------------------------------------------------
# Animals — silhouette-first, hard outline, limited palette
# ---------------------------------------------------------------------------

# Keyword → silhouette family + palette accents
_ANIMAL_FAMILY = [
    (("mite", "gnat", "beetle", "mantis", "moth"), "bug"),
    (("toad",), "toad"),
    (("pup", "wolf", "fox", "lynx", "ferret", "hyena", "badger", "otter", "hare", "mouse"), "quad"),
    (("finch", "owl", "heron", "kite", "crane", "phoenix", "wyvern"), "bird"),
    (("skink", "serpent", "basilisk", "wyrm", "drake", "dragon"), "serpent"),
    (("ram", "elk", "stag", "boar"), "horned"),
    (("kraken", "leviathan"), "tentacle"),
    (("griffin", "sphinx", "manticore", "lion"), "myth_cat"),
    (("hydra", "colossus", "behemoth", "titan", "djinn", "wraith", "sovereign", "emperor", "oracle", "genesis", "wisp"), "myth"),
]

_RARITY_PAL = {
    "common": ("#6B8F71", "#2A3A2E", "#C8E0C4"),
    "uncommon": ("#4A9BAA", "#1E4048", "#B0E0E8"),
    "rare": ("#C9A24A", "#4A3A18", "#F0E0A8"),
    "epic": ("#5A6AE0", "#242860", "#C0C8FF"),
    "mythic": ("#A068F0", "#3A2060", "#E0C8FF"),
    "astral": ("#7EC8FF", "#2A5070", "#E8F4FF"),
    "primordial": ("#C45C26", "#1A2820", "#FFC090"),
}


def _animal_family(aid: str) -> str:
    for keys, fam in _ANIMAL_FAMILY:
        if any(k in aid for k in keys):
            return fam
    return "quad"


def _sil_bug(d, cx, cy, fill, outline):
    d.ellipse((cx - 28, cy - 18, cx + 28, cy + 22), fill=fill, outline=outline, width=3)
    # wings
    d.ellipse((cx - 42, cy - 28, cx - 8, cy + 4), fill=(*fill[:3], 160), outline=outline, width=2)
    d.ellipse((cx + 8, cy - 28, cx + 42, cy + 4), fill=(*fill[:3], 160), outline=outline, width=2)
    # antennae
    d.line([(cx - 10, cy - 16), (cx - 22, cy - 36)], fill=outline, width=3)
    d.line([(cx + 10, cy - 16), (cx + 22, cy - 36)], fill=outline, width=3)


def _sil_toad(d, cx, cy, fill, outline):
    d.ellipse((cx - 34, cy - 10, cx + 34, cy + 32), fill=fill, outline=outline, width=3)
    d.ellipse((cx - 22, cy - 28, cx + 22, cy + 4), fill=fill, outline=outline, width=3)
    # eye bumps (no pupils — silhouette)
    d.ellipse((cx - 20, cy - 30, cx - 6, cy - 16), fill=fill, outline=outline, width=2)
    d.ellipse((cx + 6, cy - 30, cx + 20, cy - 16), fill=fill, outline=outline, width=2)


def _sil_quad(d, cx, cy, fill, outline):
    # body + head silhouette
    d.ellipse((cx - 30, cy - 8, cx + 26, cy + 28), fill=fill, outline=outline, width=3)
    d.ellipse((cx + 10, cy - 30, cx + 42, cy + 2), fill=fill, outline=outline, width=3)
    # ear
    d.polygon([(cx + 18, cy - 28), (cx + 22, cy - 44), (cx + 30, cy - 26)], fill=fill, outline=outline)
    d.polygon([(cx + 28, cy - 24), (cx + 36, cy - 40), (cx + 40, cy - 20)], fill=fill, outline=outline)
    # legs stubs
    d.rectangle((cx - 24, cy + 22, cx - 14, cy + 40), fill=fill, outline=outline)
    d.rectangle((cx + 8, cy + 22, cx + 18, cy + 40), fill=fill, outline=outline)


def _sil_bird(d, cx, cy, fill, outline):
    d.ellipse((cx - 22, cy - 8, cx + 28, cy + 28), fill=fill, outline=outline, width=3)
    d.ellipse((cx + 12, cy - 32, cx + 40, cy - 2), fill=fill, outline=outline, width=3)
    # beak wedge
    d.polygon([(cx + 38, cy - 18), (cx + 54, cy - 12), (cx + 38, cy - 6)], fill=fill, outline=outline)
    # wing
    d.polygon([(cx - 8, cy), (cx - 36, cy - 20), (cx - 20, cy + 16)], fill=fill, outline=outline)
    # crest
    d.polygon([(cx + 18, cy - 30), (cx + 22, cy - 46), (cx + 30, cy - 28)], fill=fill, outline=outline)


def _sil_serpent(d, cx, cy, fill, outline):
    # S-curve body via overlapping ellipses
    d.ellipse((cx - 36, cy + 8, cx - 4, cy + 36), fill=fill, outline=outline, width=3)
    d.ellipse((cx - 20, cy - 8, cx + 16, cy + 20), fill=fill, outline=outline, width=3)
    d.ellipse((cx + 0, cy - 28, cx + 36, cy + 4), fill=fill, outline=outline, width=3)
    # head
    d.ellipse((cx + 24, cy - 40, cx + 48, cy - 14), fill=fill, outline=outline, width=3)


def _sil_horned(d, cx, cy, fill, outline):
    d.ellipse((cx - 32, cy - 6, cx + 32, cy + 34), fill=fill, outline=outline, width=3)
    d.ellipse((cx - 18, cy - 28, cx + 18, cy + 6), fill=fill, outline=outline, width=3)
    # horns
    d.polygon([(cx - 16, cy - 24), (cx - 28, cy - 48), (cx - 6, cy - 28)], fill=fill, outline=outline)
    d.polygon([(cx + 16, cy - 24), (cx + 28, cy - 48), (cx + 6, cy - 28)], fill=fill, outline=outline)


def _sil_tentacle(d, cx, cy, fill, outline):
    d.ellipse((cx - 28, cy - 24, cx + 28, cy + 20), fill=fill, outline=outline, width=3)
    for i, dx in enumerate((-30, -10, 10, 30)):
        d.ellipse((cx + dx - 8, cy + 8, cx + dx + 8, cy + 44 - i * 2), fill=fill, outline=outline, width=2)


def _sil_myth_cat(d, cx, cy, fill, outline):
    d.ellipse((cx - 28, cy - 4, cx + 28, cy + 32), fill=fill, outline=outline, width=3)
    d.ellipse((cx - 20, cy - 32, cx + 20, cy + 4), fill=fill, outline=outline, width=3)
    d.polygon([(cx - 18, cy - 28), (cx - 24, cy - 48), (cx - 6, cy - 30)], fill=fill, outline=outline)
    d.polygon([(cx + 18, cy - 28), (cx + 24, cy - 48), (cx + 6, cy - 30)], fill=fill, outline=outline)
    # wing hint
    d.polygon([(cx - 28, cy), (cx - 52, cy - 24), (cx - 36, cy + 16)], fill=(*fill[:3], 180), outline=outline)


def _sil_myth(d, cx, cy, fill, outline):
    # tall standing silhouette / orb figure
    d.ellipse((cx - 22, cy - 36, cx + 22, cy - 4), fill=fill, outline=outline, width=3)
    d.polygon(
        [(cx - 28, cy - 4), (cx + 28, cy - 4), (cx + 20, cy + 40), (cx - 20, cy + 40)],
        fill=fill,
        outline=outline,
    )
    d.ellipse((cx - 10, cy - 50, cx + 10, cy - 30), fill=(*fill[:3], 200), outline=outline, width=2)


_SIL_FN = {
    "bug": _sil_bug,
    "toad": _sil_toad,
    "quad": _sil_quad,
    "bird": _sil_bird,
    "serpent": _sil_serpent,
    "horned": _sil_horned,
    "tentacle": _sil_tentacle,
    "myth_cat": _sil_myth_cat,
    "myth": _sil_myth,
}


def generate_animal(aid: str, name: str, rarity: str) -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    mid, dark, light = _RARITY_PAL.get(rarity, _RARITY_PAL["common"])
    fill = _rgba(mid)
    outline = _rgba(dark)
    # subtle rarity-tint plate behind silhouette (not a rank badge)
    plate = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    pd = ImageDraw.Draw(plate)
    pd.ellipse((10, 14, SIZE - 10, SIZE - 6), fill=(*_hex(mid), 40))
    plate = plate.filter(ImageFilter.GaussianBlur(4))
    img = Image.alpha_composite(img, plate)

    sil = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(sil)
    fam = _animal_family(aid)
    _SIL_FN[fam](d, SIZE // 2, SIZE // 2 + 4, fill, outline)
    # hard outer outline pass: draw silhouette again slightly larger in dark then fill on top
    # rim light accent
    accent = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ad = ImageDraw.Draw(accent)
    ad.ellipse((36, 28, 56, 44), fill=(*_hex(light), 90))
    accent = accent.filter(ImageFilter.GaussianBlur(2))
    img = Image.alpha_composite(img, sil)
    img = Image.alpha_composite(img, accent)
    return img


# ---------------------------------------------------------------------------
# Weapons — metal/crystal glyphs, slightly busier
# ---------------------------------------------------------------------------

def _weapon_style(kind: str) -> str:
    k = kind.lower()
    if any(x in k for x in ("bow", "crossbow", "sling", "chakram")):
        return "ranged"
    if any(x in k for x in ("wand", "scepter", "staff", "tome", "orb", "censer", "fan")):
        return "mage"
    if any(x in k for x in ("shield", "gauntlet")):
        return "guard"
    if any(x in k for x in ("axe", "hammer", "maul", "cleaver", "flail", "mace", "halberd", "scythe", "sickle")):
        return "heavy"
    if any(x in k for x in ("spear", "lance", "trident", "pike", "javelin", "glaive")):
        return "pole"
    return "blade"


_WEAPON_COLORS = {
    "blade": ("#C0C8D8", "#3A4050", "#E8F0FF"),
    "heavy": ("#B08050", "#402818", "#E8C890"),
    "pole": ("#80A0C0", "#283848", "#D0E0F0"),
    "ranged": ("#C07040", "#402010", "#F0C090"),
    "mage": ("#9080E0", "#302050", "#D8D0FF"),
    "guard": ("#70A080", "#203028", "#C0E0D0"),
}


def generate_weapon(kind: str) -> Image.Image:
    style = _weapon_style(kind)
    mid, dark, light = _WEAPON_COLORS[style]
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    # chip-ish backing
    bg = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bg)
    bd.rounded_rectangle((10, 10, SIZE - 11, SIZE - 11), radius=16, fill=(24, 26, 34, 200))
    bd.rounded_rectangle((10, 10, SIZE - 11, SIZE - 11), radius=16, outline=_rgba(light, 160), width=2)
    img = Image.alpha_composite(img, bg)
    d = ImageDraw.Draw(img)
    fill = _rgba(mid)
    out = _rgba(dark)
    hi = _rgba(light)
    cx, cy = SIZE // 2, SIZE // 2

    if style == "blade":
        d.polygon([(cx + 28, cy - 40), (cx + 36, cy - 28), (cx - 8, cy + 24), (cx - 20, cy + 16)], fill=fill, outline=out)
        d.line([(cx + 30, cy - 36), (cx - 10, cy + 18)], fill=hi, width=2)
        d.rectangle((cx - 26, cy + 14, cx - 2, cy + 22), fill=out)
        d.rectangle((cx - 18, cy + 22, cx - 10, cy + 40), fill=_rgba("#5A4030"))
    elif style == "heavy":
        d.rectangle((cx - 6, cy - 10, cx + 6, cy + 40), fill=_rgba("#5A4030"), outline=out)
        d.rounded_rectangle((cx - 32, cy - 40, cx + 32, cy - 4), radius=6, fill=fill, outline=out, width=2)
        d.line([(cx - 24, cy - 32), (cx + 24, cy - 12)], fill=hi, width=2)
    elif style == "pole":
        d.rectangle((cx - 4, cy - 8, cx + 4, cy + 44), fill=_rgba("#6A5040"), outline=out)
        d.polygon([(cx, cy - 44), (cx + 18, cy - 8), (cx - 18, cy - 8)], fill=fill, outline=out)
        d.line([(cx, cy - 40), (cx, cy - 12)], fill=hi, width=2)
    elif style == "ranged":
        d.arc((cx - 36, cy - 36, cx + 20, cy + 36), 200, 340, fill=fill, width=6)
        d.line([(cx - 8, cy - 28), (cx - 8, cy + 28)], fill=out, width=3)
        d.line([(cx - 8, cy), (cx + 36, cy)], fill=fill, width=3)
        d.polygon([(cx + 36, cy), (cx + 28, cy - 6), (cx + 28, cy + 6)], fill=hi, outline=out)
    elif style == "mage":
        d.rectangle((cx - 5, cy - 4, cx + 5, cy + 42), fill=_rgba("#5A4060"), outline=out)
        d.ellipse((cx - 22, cy - 40, cx + 22, cy - 2), fill=fill, outline=out, width=3)
        d.ellipse((cx - 10, cy - 30, cx + 6, cy - 14), fill=hi)
        # crystal facet
        d.polygon([(cx, cy - 42), (cx + 14, cy - 22), (cx, cy - 8), (cx - 14, cy - 22)], outline=hi)
    else:  # guard
        d.polygon(
            [(cx - 28, cy - 28), (cx + 28, cy - 28), (cx + 24, cy + 8), (cx, cy + 40), (cx - 24, cy + 8)],
            fill=fill,
            outline=out,
        )
        d.line([(cx, cy - 20), (cx, cy + 28)], fill=hi, width=3)

    # metal glint
    gl = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(gl).ellipse((30, 24, 50, 40), fill=(255, 255, 255, 60))
    gl = gl.filter(ImageFilter.GaussianBlur(2))
    img = Image.alpha_composite(img, gl)
    return img


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _load_animals():
    from groksito_discord.discord.aether_hunt import ANIMALS

    return ANIMALS


def _load_weapons():
    from groksito_discord.discord.aether_gear import WEAPONS

    return WEAPONS


def main() -> int:
    print("Generating rank badges…")
    for key, letter, fill, dark, light, special in RANK_SPEC:
        img = generate_rank(key, letter, fill, dark, light, special)
        path = RANK_DIR / f"rank_{key}.png"
        _save(img, path)
        print(f"  {path.relative_to(REPO)} ({path.stat().st_size} B)")

    print("Generating HUD icons…")
    for key, accent, motif in HUD_SPECS:
        img = generate_hud(key, accent, motif)
        path = HUD_DIR / f"{key}.png"
        _save(img, path)
        print(f"  {path.relative_to(REPO)} ({path.stat().st_size} B)")

    print("Generating animal emojis…")
    animals = _load_animals()
    ANIMAL_DIR.mkdir(parents=True, exist_ok=True)
    for aid, name, _uni, rarity in animals:
        img = generate_animal(aid, name, rarity)
        path = ANIMAL_DIR / f"{aid}.png"
        _save(img, path)
    print(f"  {len(animals)} animals → {ANIMAL_DIR.relative_to(REPO)}/")

    print("Generating weapon emojis…")
    weapons = _load_weapons()
    WEAPON_DIR.mkdir(parents=True, exist_ok=True)
    for kind, _name, _uni, _style in weapons:
        img = generate_weapon(kind)
        path = WEAPON_DIR / f"{kind}.png"
        _save(img, path)
    print(f"  {len(weapons)} weapons → {WEAPON_DIR.relative_to(REPO)}/")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
