"""Aether coin portraits and falling-flip frames for /cointoss."""
from __future__ import annotations

import io
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
)

VOID = (8, 10, 18)
GOLD = (212, 176, 72)
GOLD_DIM = (160, 120, 36)
GOLD_DARK = (40, 32, 12)
CREAM = (248, 244, 230)
INK = (40, 28, 8)

W, H = 280, 520
COIN = 92


def _font(size: int) -> ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _space(width: int, height: int) -> Image.Image:
    img = Image.new("RGB", (width, height), VOID)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.ellipse((-40, -20, 180, 160), fill=(40, 70, 140, 70))
    d.ellipse((40, 280, 340, 560), fill=(70, 40, 110, 60))
    overlay = overlay.filter(ImageFilter.GaussianBlur(24))
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def _face(size: int, face: str) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((1, 1, size - 2, size - 2), fill=GOLD_DARK, outline=GOLD, width=2)
    d.ellipse((5, 5, size - 6, size - 6), fill=(186, 150, 48, 255), outline=GOLD_DIM)
    d.ellipse((11, 11, size - 12, size - 12), fill=(*GOLD, 255))
    label = "TAILS" if face == "tails" else "HEADS"
    d.text((size // 2, size // 2), label, font=_font(18), fill=INK, anchor="mm")
    return img


def _edge_horizontal(width: int, height: int) -> Image.Image:
    img = Image.new("RGBA", (width, max(10, height)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, width - 1, img.height - 1), radius=img.height // 2, fill=GOLD_DIM, outline=GOLD)
    mid = img.height // 2
    d.rectangle((10, mid - 1, width - 11, mid + 2), fill=CREAM)
    return img


def _side_standing(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = size // 2
    d.rounded_rectangle((cx - 9, 10, cx + 9, size - 10), radius=8, fill=GOLD_DIM, outline=GOLD, width=2)
    d.rectangle((cx - 1, 16, cx + 2, size - 16), fill=CREAM)
    return img


def _composite(coin: Image.Image, y: int) -> bytes:
    canvas = _space(W, H)
    x = (W - coin.width) // 2
    y = max(6, min(y, H - coin.height - 6))
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse((x + 10, y + coin.height - 4, x + coin.width - 10, y + coin.height + 10), fill=(0, 0, 0, 90))
    shadow = shadow.filter(ImageFilter.GaussianBlur(5))
    canvas = Image.alpha_composite(canvas, shadow)
    canvas.alpha_composite(coin, (x, y))
    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_flip_frame(tilt_deg: float, y_frac: float, preview_face: str = "heads") -> bytes:
    squash = abs(math.cos(math.radians(tilt_deg)))
    top = 10
    floor = H - COIN - 16
    y = int(top + max(0.0, min(1.0, y_frac)) * (floor - top))
    if squash < 0.16:
        coin = _edge_horizontal(COIN, max(10, int(COIN * 0.12)))
    else:
        shown = "tails" if 90 < (tilt_deg % 360) < 270 else "heads"
        face = _face(COIN, shown)
        coin = face.resize((COIN, max(10, int(COIN * max(0.12, squash)))), Image.Resampling.LANCZOS)
    return _composite(coin, y)


def render_result(face: str) -> bytes:
    y = H - COIN - 16
    if face == "side":
        coin = _side_standing(COIN)
    else:
        coin = _face(COIN, "tails" if face == "tails" else "heads")
    return _composite(coin, y)


def render_thumb(face: str) -> bytes:
    size = 256
    img = Image.new("RGB", (size, size), VOID)
    overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.ellipse((-20, -20, 180, 180), fill=(40, 70, 140, 80))
    overlay = overlay.filter(ImageFilter.GaussianBlur(18))
    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    if face == "side":
        coin = _side_standing(168)
    else:
        coin = _face(168, "tails" if face == "tails" else "heads")
    img.alpha_composite(coin, ((size - coin.width) // 2, (size - coin.height) // 2))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


FLIP_BEATS: list[tuple[float, float]] = [
    (8.0, 0.00),
    (70.0, 0.16),
    (110.0, 0.32),
    (188.0, 0.48),
    (250.0, 0.64),
    (328.0, 0.80),
    (8.0, 0.94),
]
