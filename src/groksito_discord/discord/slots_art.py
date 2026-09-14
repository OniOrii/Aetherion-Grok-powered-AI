"""Full-width cabinet portraits for /slots."""
from __future__ import annotations

import base64
import io
import logging
import math
from importlib import import_module
from pathlib import Path
from random import Random

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("aetherion.slots_art")

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
)

_THEMES = {
    "cosmos": {
        "bg": (6, 8, 18),
        "body": (16, 22, 48),
        "accent": (220, 184, 78),
        "window": (8, 10, 22),
        "plate": (28, 22, 10),
        "label": "COSMOS",
        "icons": ("planet", "star", "coin"),
    },
    "nebula": {
        "bg": (14, 6, 24),
        "body": (48, 22, 72),
        "accent": (198, 142, 255),
        "window": (20, 10, 36),
        "plate": (40, 16, 52),
        "label": "NEBULA",
        "icons": ("crystal", "orb", "charm"),
    },
    "horizon": {
        "bg": (6, 6, 8),
        "body": (16, 14, 18),
        "accent": (214, 168, 58),
        "window": (8, 8, 10),
        "plate": (18, 14, 10),
        "label": "HORIZON",
        "icons": ("hole", "moon", "swirl"),
    },
}

_cache: dict[str, bytes] = {}
_MODULES = {
    "cosmos": ".cabinet_cosmos",
    "nebula": ".cabinet_nebula",
    "horizon": ".cabinet_horizon",
}
W, H = 900, 540


def _font(size: int):
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _star(draw, cx, cy, r, fill):
    pts = []
    for i in range(8):
        rad = r if i % 2 == 0 else r * 0.42
        a = math.radians(-90 + i * 45)
        pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
    draw.polygon(pts, fill=fill)


def _aether_mark(draw, cx, cy, size, accent):
    r = size // 2
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(58, 42, 16), outline=accent, width=3)
    draw.ellipse((cx - r + 6, cy - r + 6, cx + r - 6, cy + r - 6), outline=accent, width=1)
    _star(draw, cx, cy, r * 0.55, accent)


def _icon(draw, kind, cx, cy, accent):
    if kind == "planet":
        draw.ellipse((cx - 38, cy - 38, cx + 38, cy + 38), fill=(40, 70, 130), outline=accent, width=3)
        draw.arc((cx - 58, cy - 16, cx + 58, cy + 16), start=200, end=340, fill=accent, width=4)
    elif kind == "star":
        _star(draw, cx, cy, 36, accent)
    elif kind == "coin":
        _aether_mark(draw, cx, cy, 72, accent)
    elif kind == "crystal":
        draw.polygon([(cx, cy - 44), (cx + 28, cy), (cx, cy + 44), (cx - 28, cy)], outline=accent, width=3)
    elif kind == "orb":
        draw.ellipse((cx - 36, cy - 36, cx + 36, cy + 36), outline=accent, width=3)
    elif kind == "charm":
        draw.ellipse((cx - 30, cy - 30, cx + 30, cy + 30), outline=accent, width=3)
        _star(draw, cx, cy, 16, accent)
    elif kind == "hole":
        draw.ellipse((cx - 40, cy - 40, cx + 40, cy + 40), outline=accent, width=3)
        draw.ellipse((cx - 22, cy - 22, cx + 22, cy + 22), fill=(2, 2, 4))
    elif kind == "moon":
        draw.ellipse((cx - 34, cy - 34, cx + 34, cy + 34), fill=accent)
        draw.ellipse((cx - 14, cy - 38, cx + 36, cy + 16), fill=(8, 8, 10))
    else:
        draw.arc((cx - 36, cy - 36, cx + 36, cy + 36), start=20, end=310, fill=accent, width=4)


def _paint(key: str) -> bytes:
    theme = _THEMES.get(key) or _THEMES["cosmos"]
    img = Image.new("RGB", (W, H), theme["bg"])
    d = ImageDraw.Draw(img)
    rng = Random((hash(key) & 0xFFFF) + 17)
    for _ in range(120):
        x = rng.randint(4, W - 4)
        y = rng.randint(4, H - 4)
        c = rng.randint(140, 230)
        r = rng.choice((0, 1, 1, 2))
        d.ellipse((x, y, x + r, y + r), fill=(c, c - 8, min(255, c + 24)))
    d.rounded_rectangle((40, 28, W - 40, H - 28), radius=36, fill=theme["body"], outline=theme["accent"], width=5)
    d.ellipse((W // 2 - 28, 18, W // 2 + 28, 70), fill=theme["accent"])
    d.rounded_rectangle((W // 2 - 210, 78, W // 2 + 210, 138), radius=12, fill=theme["plate"], outline=theme["accent"], width=3)
    _aether_mark(d, W // 2 - 168, 108, 36, theme["accent"])
    _aether_mark(d, W // 2 + 168, 108, 36, theme["accent"])
    d.text((W // 2, 108), theme["label"], font=_font(28), fill=theme["accent"], anchor="mm")
    win_y, win_h, ww, gap = 168, 210, 170, 22
    total = 3 * ww + 2 * gap
    x0 = (W - total) // 2
    for i, kind in enumerate(theme["icons"]):
        x = x0 + i * (ww + gap)
        d.rounded_rectangle((x, win_y, x + ww, win_y + win_h), radius=16, fill=theme["window"], outline=theme["accent"], width=4)
        _icon(d, kind, x + ww // 2, win_y + win_h // 2, theme["accent"])
    d.rounded_rectangle((W // 2 + 40, 400, W - 90, 468), radius=14, fill=theme["plate"], outline=theme["accent"], width=3)
    d.text((W // 2 + 196, 434), "SPIN", font=_font(26), fill=theme["accent"], anchor="mm")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _from_bundle(key: str) -> bytes | None:
    mod_name = _MODULES.get(key)
    if not mod_name:
        return None
    try:
        mod = import_module(mod_name, __package__)
        raw = base64.b64decode("".join(mod.DATA))
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        buf = io.BytesIO()
        im.save(buf, format="PNG", optimize=True)
        return buf.getvalue()
    except Exception:
        logger.info("cabinet photo missing key=%s, using painted fallback", key)
        return None


def cabinet_png(machine_key: str) -> bytes:
    key = machine_key if machine_key in _THEMES else "cosmos"
    cached = _cache.get(key)
    if cached:
        return cached
    raw = _from_bundle(key) or _paint(key)
    _cache[key] = raw
    return raw


def cabinet_jpeg(machine_key: str) -> bytes:
    return cabinet_png(machine_key)
