"""Corner cabinet thumbnails for /slots. Drawn here so Discord always gets a real PNG."""
from __future__ import annotations

import io
from pathlib import Path
from random import Random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
)

_THEMES = {
    "cosmos": {
        "bg": (10, 12, 28),
        "frame": (18, 28, 58),
        "accent": (201, 162, 39),
        "glow": (40, 70, 140, 90),
        "plate": (28, 24, 12),
        "label": "COSMOS",
    },
    "nebula": {
        "bg": (14, 6, 24),
        "frame": (48, 18, 72),
        "accent": (186, 120, 255),
        "glow": (120, 40, 160, 90),
        "plate": (40, 20, 12),
        "label": "NEBULA",
    },
    "horizon": {
        "bg": (6, 6, 8),
        "frame": (18, 16, 22),
        "accent": (212, 160, 50),
        "glow": (80, 40, 10, 80),
        "plate": (16, 14, 10),
        "label": "HORIZON",
    },
}

_cache: dict[str, bytes] = {}


def _font(size: int) -> ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _paint(key: str) -> bytes:
    theme = _THEMES.get(key) or _THEMES["cosmos"]
    size = 256
    img = Image.new("RGB", (size, size), theme["bg"])
    overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse((-40, -40, 180, 180), fill=theme["glow"])
    od.ellipse((80, 90, 300, 300), fill=theme["glow"])
    overlay = overlay.filter(ImageFilter.GaussianBlur(22))
    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    d = ImageDraw.Draw(img)
    rng = Random(hash(key) & 0xFFFF)
    for _ in range(42):
        x = rng.randint(8, 248)
        y = rng.randint(8, 248)
        r = rng.choice((0, 1, 1, 2))
        c = rng.randint(160, 240)
        d.ellipse((x, y, x + r, y + r), fill=(c, c - 10, min(255, c + 20)))
    d.rounded_rectangle((18, 14, 238, 242), radius=28, fill=theme["frame"], outline=theme["accent"], width=3)
    d.rounded_rectangle((28, 24, 228, 232), radius=22, outline=theme["accent"], width=1)
    win_y, win_h, ww, gap = 48, 92, 52, 10
    total = 3 * ww + 2 * gap
    x0 = (size - total) // 2
    glyphs = ("*", ")", "+")
    for i in range(3):
        x = x0 + i * (ww + gap)
        d.rounded_rectangle((x, win_y, x + ww, win_y + win_h), radius=8, fill=(8, 8, 16), outline=theme["accent"], width=2)
        d.text((x + ww // 2, win_y + win_h // 2), glyphs[i], font=_font(28), fill=theme["accent"], anchor="mm")
    d.rounded_rectangle((40, 160, 216, 214), radius=10, fill=theme["plate"], outline=theme["accent"], width=2)
    label = theme["label"]
    d.text((128, 187), label, font=_font(16 if len(label) > 12 else 18), fill=theme["accent"], anchor="mm")
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def cabinet_png(machine_key: str) -> bytes:
    key = machine_key if machine_key in _THEMES else "cosmos"
    cached = _cache.get(key)
    if cached:
        return cached
    raw = _paint(key)
    _cache[key] = raw
    return raw
