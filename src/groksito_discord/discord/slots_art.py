"""Cabinet portraits for /slots. Drawn here so Discord always gets a real PNG."""
from __future__ import annotations

import io
import math
from pathlib import Path
from random import Random

from PIL import Image, ImageDraw, ImageFont

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
)

_THEMES = {
    "cosmos": {
        "bg": (8, 10, 22),
        "body": (22, 28, 52),
        "accent": (212, 176, 72),
        "window": (10, 12, 24),
        "plate": (28, 24, 12),
        "label": "COSMOS",
        "icons": ("planet", "star", "coin"),
    },
    "nebula": {
        "bg": (16, 8, 28),
        "body": (52, 28, 78),
        "accent": (186, 130, 255),
        "window": (18, 10, 32),
        "plate": (36, 18, 48),
        "label": "NEBULA",
        "icons": ("crystal", "orb", "charm"),
    },
    "horizon": {
        "bg": (6, 6, 8),
        "body": (18, 16, 20),
        "accent": (212, 160, 50),
        "window": (8, 8, 10),
        "plate": (16, 14, 10),
        "label": "HORIZON",
        "icons": ("hole", "moon", "swirl"),
    },
}

_cache: dict[str, bytes] = {}
SIZE = 384


def _font(size: int) -> ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _icon(draw: ImageDraw.ImageDraw, kind: str, cx: int, cy: int, accent) -> None:
    if kind == "planet":
        draw.ellipse((cx - 16, cy - 16, cx + 16, cy + 16), outline=accent, width=2)
        draw.ellipse((cx - 10, cy - 10, cx + 10, cy + 10), fill=accent)
        draw.arc((cx - 22, cy - 6, cx + 22, cy + 6), start=200, end=340, fill=accent, width=2)
    elif kind == "star":
        pts = []
        for i in range(8):
            r = 16 if i % 2 == 0 else 7
            a = math.radians(-90 + i * 45)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        draw.polygon(pts, outline=accent)
        draw.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill=accent)
    elif kind == "coin":
        draw.ellipse((cx - 16, cy - 16, cx + 16, cy + 16), outline=accent, width=2)
        draw.ellipse((cx - 11, cy - 11, cx + 11, cy + 11), outline=accent, width=1)
        draw.text((cx, cy), "A", font=_font(14), fill=accent, anchor="mm")
    elif kind == "crystal":
        draw.polygon([(cx, cy - 18), (cx + 14, cy), (cx, cy + 18), (cx - 14, cy)], outline=accent, width=2)
        draw.line((cx, cy - 18, cx, cy + 18), fill=accent, width=1)
    elif kind == "orb":
        draw.ellipse((cx - 16, cy - 16, cx + 16, cy + 16), outline=accent, width=2)
        draw.ellipse((cx - 6, cy - 8, cx + 2, cy), fill=accent)
    elif kind == "charm":
        draw.ellipse((cx - 13, cy - 13, cx + 13, cy + 13), outline=accent, width=2)
        draw.line((cx, cy - 8, cx, cy + 8), fill=accent, width=2)
        draw.line((cx - 8, cy, cx + 8, cy), fill=accent, width=2)
    elif kind == "hole":
        draw.ellipse((cx - 18, cy - 18, cx + 18, cy + 18), outline=accent, width=2)
        draw.ellipse((cx - 10, cy - 10, cx + 10, cy + 10), fill=(4, 4, 6), outline=accent)
    elif kind == "moon":
        draw.ellipse((cx - 14, cy - 14, cx + 14, cy + 14), outline=accent, width=2)
        draw.ellipse((cx - 4, cy - 14, cx + 16, cy + 8), fill=(8, 8, 10))
    else:
        draw.arc((cx - 16, cy - 16, cx + 16, cy + 16), start=20, end=300, fill=accent, width=2)
        draw.arc((cx - 8, cy - 8, cx + 8, cy + 8), start=200, end=80, fill=accent, width=2)


def _paint(key: str) -> bytes:
    theme = _THEMES.get(key) or _THEMES["cosmos"]
    size = SIZE
    img = Image.new("RGB", (size, size), theme["bg"])
    d = ImageDraw.Draw(img)
    rng = Random(hash(key) & 0xFFFF)
    for _ in range(50):
        x = rng.randint(6, size - 6)
        y = rng.randint(6, size - 6)
        r = rng.choice((0, 1, 1, 2))
        c = rng.randint(140, 230)
        d.ellipse((x, y, x + r, y + r), fill=(c, c - 8, min(255, c + 20)))
    d.rounded_rectangle((18, 10, size - 18, size - 10), radius=28, fill=theme["body"], outline=theme["accent"], width=4)
    d.rounded_rectangle((28, 20, size - 28, size - 20), radius=22, outline=theme["accent"], width=1)
    d.ellipse((size // 2 - 16, 24, size // 2 + 16, 52), fill=theme["accent"])
    d.ellipse((size // 2 - 8, 30, size // 2 + 8, 46), fill=(255, 240, 180))
    win_y, win_h, ww, gap = 70, 168, 86, 12
    total = 3 * ww + 2 * gap
    x0 = (size - total) // 2
    icons = theme["icons"]
    for i in range(3):
        x = x0 + i * (ww + gap)
        d.rounded_rectangle((x, win_y, x + ww, win_y + win_h), radius=10, fill=theme["window"], outline=theme["accent"], width=3)
        _icon(d, icons[i], x + ww // 2, win_y + win_h // 2, theme["accent"])
    mid_y = win_y + win_h // 2
    d.line((x0 - 8, mid_y, x0 + total + 8, mid_y), fill=theme["accent"], width=2)
    d.rounded_rectangle((48, 258, size - 48, 330), radius=12, fill=theme["plate"], outline=theme["accent"], width=3)
    d.text((size // 2, 294), theme["label"], font=_font(22), fill=theme["accent"], anchor="mm")
    d.ellipse((size // 2 - 18, 338, size // 2 + 18, 374), fill=theme["accent"], outline=(255, 230, 160), width=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def cabinet_png(machine_key: str) -> bytes:
    key = machine_key if machine_key in _THEMES else "cosmos"
    cached = _cache.get(key)
    if cached:
        return cached
    raw = _paint(key)
    _cache[key] = raw
    return raw


def cabinet_jpeg(machine_key: str) -> bytes:
    return cabinet_png(machine_key)
