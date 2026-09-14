"""Aether coin portraits and falling-flip frames for /cointoss."""
from __future__ import annotations

import io
import math
from pathlib import Path
from random import Random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
)

VOID = (6, 8, 18)
GOLD = (212, 176, 72)
GOLD_DIM = (148, 118, 42)
GOLD_DARK = (90, 70, 28)
CREAM = (248, 244, 230)
INK = (36, 24, 8)
HIGHLIGHT = (240, 210, 120)

W, H = 280, 520
COIN = 108
PAD_Y = H - 28


def _font(size: int) -> ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _space(width: int, height: int) -> Image.Image:
    img = Image.new("RGB", (width, height), VOID)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.ellipse((-90, -70, 210, 210), fill=(70, 36, 130, 85))
    d.ellipse((20, 150, 340, 430), fill=(28, 78, 118, 75))
    d.ellipse((50, 330, 280, 540), fill=(16, 24, 70, 60))
    overlay = overlay.filter(ImageFilter.GaussianBlur(26))
    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    stars = ImageDraw.Draw(img)
    rng = Random(width * 17 + height)
    for _ in range(180):
        x = rng.randint(3, width - 4)
        y = rng.randint(3, height - 4)
        r = rng.choice((0, 0, 1, 1, 2))
        c = rng.randint(150, 240)
        stars.ellipse((x, y, x + r, y + r), fill=(c, c - 8, min(255, c + 18)))
    stars.ellipse((width - 74, 34, width - 16, 92), fill=(24, 32, 64))
    stars.ellipse((width - 66, 42, width - 24, 84), fill=(38, 68, 108))
    ring = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    rd.ellipse((width - 82, 48, width - 8, 78), outline=(180, 160, 90, 80), width=1)
    img = Image.alpha_composite(img, ring)
    return img


def _paint_pad(canvas: Image.Image) -> None:
    d = ImageDraw.Draw(canvas)
    cx = W // 2
    d.ellipse((cx - 78, PAD_Y - 10, cx + 78, PAD_Y + 16), fill=(10, 12, 22, 180))
    d.ellipse((cx - 70, PAD_Y - 6, cx + 70, PAD_Y + 12), outline=GOLD_DIM, width=1)
    d.ellipse((cx - 58, PAD_Y - 2, cx + 58, PAD_Y + 8), outline=(80, 70, 40, 160), width=1)


def _face(size: int, face: str) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((1, 1, size - 2, size - 2), fill=GOLD_DARK, outline=GOLD, width=2)
    d.ellipse((4, 4, size - 5, size - 5), fill=(186, 148, 50, 255), outline=GOLD_DIM)
    cx = cy = size / 2
    ticks = 32
    for i in range(ticks):
        ang = math.radians(i * (360 / ticks))
        x1 = cx + math.cos(ang) * (size / 2 - 3)
        y1 = cy + math.sin(ang) * (size / 2 - 3)
        x2 = cx + math.cos(ang) * (size / 2 - 8)
        y2 = cy + math.sin(ang) * (size / 2 - 8)
        d.line((x1, y1, x2, y2), fill=(70, 52, 18), width=1)
    d.ellipse((13, 13, size - 14, size - 14), fill=(214, 178, 72, 255), outline=HIGHLIGHT)
    d.ellipse((19, 19, size - 20, size - 20), outline=(120, 90, 30), width=1)
    d.ellipse((26, 32, size - 27, size - 33), outline=(90, 70, 28, 160), width=1)
    d.arc((30, 24, size - 31, size - 25), start=210, end=40, fill=(255, 230, 160), width=1)
    if face == "tails":
        d.arc((34, 38, size - 35, size - 39), start=20, end=200, fill=(90, 70, 28), width=1)
    else:
        d.ellipse((size // 2 - 3, 28, size // 2 + 3, 34), fill=INK)
    d.text((size // 2, size // 2 - 16), "\u2726", font=_font(12), fill=(70, 48, 16), anchor="mm")
    label = "TAILS" if face == "tails" else "HEADS"
    d.text((size // 2, size // 2 + 4), label, font=_font(17), fill=INK, anchor="mm")
    return img


def _edge_horizontal(width: int, height: int) -> Image.Image:
    img = Image.new("RGBA", (width, max(12, height)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, width - 1, img.height - 1), radius=img.height // 2, fill=GOLD_DIM, outline=GOLD)
    mid = img.height // 2
    d.rectangle((8, mid - 2, width - 9, mid + 2), fill=HIGHLIGHT)
    for i in range(10):
        x = 12 + i * ((width - 24) / 9)
        d.line((x, 2, x, img.height - 3), fill=(70, 52, 18), width=1)
    return img


def _side_standing(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = size // 2
    d.rounded_rectangle((cx - 10, 12, cx + 10, size - 12), radius=8, fill=GOLD_DIM, outline=GOLD, width=2)
    d.rectangle((cx - 2, 18, cx + 2, size - 18), fill=HIGHLIGHT)
    return img


def _composite(coin: Image.Image, y: int, *, landed: bool) -> bytes:
    canvas = _space(W, H)
    _paint_pad(canvas)
    x = (W - coin.width) // 2
    max_y = PAD_Y - coin.height + 6
    y = max(8, min(y, max_y))
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    spread = 22 if landed else 12
    sd.ellipse(
        (x + 8, y + coin.height - 4, x + coin.width - 8, y + coin.height + (18 if landed else 10)),
        fill=(0, 0, 0, 130 if landed else 80),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(7 if landed else 5))
    canvas = Image.alpha_composite(canvas, shadow)
    canvas.alpha_composite(coin, (x, y))
    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_flip_frame(tilt_deg: float, y_frac: float, preview_face: str = "heads") -> bytes:
    squash = abs(math.cos(math.radians(tilt_deg)))
    top = 12
    floor = PAD_Y - COIN + 6
    y = int(top + max(0.0, min(1.0, y_frac)) * (floor - top))
    if squash < 0.16:
        coin = _edge_horizontal(COIN, max(12, int(COIN * 0.14)))
    else:
        shown = "tails" if 90 < (tilt_deg % 360) < 270 else "heads"
        face = _face(COIN, shown)
        coin = face.resize((COIN, max(12, int(COIN * max(0.14, squash)))), Image.Resampling.LANCZOS)
    return _composite(coin, y, landed=y_frac >= 0.96 and squash > 0.9)


def render_result(face: str) -> bytes:
    y = PAD_Y - COIN + 6
    if face == "side":
        coin = _side_standing(COIN)
        y = PAD_Y - coin.height + 8
    else:
        coin = _face(COIN, "tails" if face == "tails" else "heads")
    return _composite(coin, y, landed=True)


def render_thumb(face: str) -> bytes:
    size = 256
    img = _space(size, size)
    if face == "side":
        coin = _side_standing(176)
    else:
        coin = _face(176, "tails" if face == "tails" else "heads")
    img.alpha_composite(coin, ((size - coin.width) // 2, (size - coin.height) // 2))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


FLIP_BEATS: list[tuple[float, float]] = [
    (10.0, 0.00),
    (78.0, 0.16),
    (118.0, 0.32),
    (188.0, 0.48),
    (258.0, 0.64),
    (328.0, 0.80),
    (0.0, 1.00),
]
