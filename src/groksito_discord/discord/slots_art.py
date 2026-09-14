"""Cabinet portraits for /slots. Drawn in-process so the image always exists."""
from __future__ import annotations

import io
import logging
import math
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
        "gold": (220, 184, 78),
        "window": (8, 10, 22),
        "plate": (28, 22, 10),
        "label": "COSMOS",
    },
    "nebula": {
        "bg": (14, 6, 24),
        "body": (48, 22, 72),
        "gold": (198, 142, 255),
        "window": (20, 10, 36),
        "plate": (40, 16, 52),
        "label": "NEBULA",
    },
    "horizon": {
        "bg": (6, 6, 8),
        "body": (16, 14, 18),
        "gold": (214, 168, 58),
        "window": (8, 8, 10),
        "plate": (18, 14, 10),
        "label": "HORIZON",
    },
}

_cache: dict[str, bytes] = {}
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


def cabinet_png(machine_key: str) -> bytes:
    key = machine_key if machine_key in _THEMES else "cosmos"
    cached = _cache.get(key)
    if cached:
        return cached
    theme = _THEMES[key]
    img = Image.new("RGB", (W, H), theme["bg"])
    d = ImageDraw.Draw(img)
    rng = Random((hash(key) & 0xFFFF) + 17)
    for _ in range(140):
        x = rng.randint(4, W - 4)
        y = rng.randint(4, H - 4)
        c = rng.randint(140, 230)
        r = rng.choice((0, 1, 1, 2))
        d.ellipse((x, y, x + r, y + r), fill=(c, c - 8, min(255, c + 24)))
    d.rounded_rectangle((40, 28, W - 40, H - 28), radius=36, fill=theme["body"], outline=theme["gold"], width=5)
    d.ellipse((W // 2 - 28, 18, W // 2 + 28, 70), fill=theme["gold"])
    d.ellipse((W // 2 - 14, 32, W // 2 + 14, 58), fill=(255, 236, 180))
    d.rounded_rectangle((W // 2 - 210, 78, W // 2 + 210, 138), radius=12, fill=theme["plate"], outline=theme["gold"], width=3)
    _star(d, W // 2 - 168, 108, 14, theme["gold"])
    _star(d, W // 2 + 168, 108, 14, theme["gold"])
    d.text((W // 2, 108), theme["label"], font=_font(28), fill=theme["gold"], anchor="mm")
    win_y, win_h, ww, gap = 168, 210, 170, 22
    total = 3 * ww + 2 * gap
    x0 = (W - total) // 2
    for i in range(3):
        x = x0 + i * (ww + gap)
        d.rounded_rectangle((x, win_y, x + ww, win_y + win_h), radius=16, fill=theme["window"], outline=theme["gold"], width=4)
        _star(d, x + ww // 2, win_y + win_h // 2, 28, theme["gold"])
    d.rounded_rectangle((W // 2 + 40, 400, W - 90, 468), radius=14, fill=theme["plate"], outline=theme["gold"], width=3)
    d.text((W // 2 + 196, 434), "SPIN", font=_font(26), fill=theme["gold"], anchor="mm")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw = buf.getvalue()
    _cache[key] = raw
    return raw


def cabinet_jpeg(machine_key: str) -> bytes:
    return cabinet_png(machine_key)
