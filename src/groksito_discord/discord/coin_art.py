"""Aether coin portraits and falling-flip frames for /cointoss."""
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

VOID = (3, 4, 12)
GOLD = (212, 176, 78)
GOLD_DIM = (132, 102, 42)
GOLD_DARK = (58, 42, 16)
PALE = (236, 214, 150)
INK = (28, 18, 6)
HIGHLIGHT = (248, 232, 176)

W, H = 300, 540
COIN = 136
FLAT = 0.58
FLOOR = H - 28
FLIP_SLEEP = 0.16


def _font(size: int) -> ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _space(width: int, height: int) -> Image.Image:
    img = Image.new("RGB", (width, height), VOID)
    d = ImageDraw.Draw(img)
    rng = Random(width * 23 + height * 7)
    for _ in range(340):
        x = rng.randint(1, width - 2)
        y = rng.randint(1, height - 2)
        c = rng.randint(120, 200)
        img.putpixel((x, y), (c, c, min(255, c + 18)))
    for _ in range(30):
        x = rng.randint(3, width - 4)
        y = rng.randint(3, height - 4)
        c = rng.randint(210, 255)
        d.point((x, y), fill=(c, c, 255))
        d.point((x - 1, y), fill=(c // 2, c // 2, c))
        d.point((x + 1, y), fill=(c // 2, c // 2, c))
        d.point((x, y - 1), fill=(c // 2, c // 2, c))
        d.point((x, y + 1), fill=(c // 2, c // 2, c))
    return img.convert("RGBA")


def _face(size: int, face: str) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((0, 0, size - 1, size - 1), fill=GOLD_DARK, outline=HIGHLIGHT, width=2)
    cx = cy = size / 2
    for i in range(48):
        ang = math.radians(i * (360 / 48))
        outer = size / 2 - 2.2
        inner = size / 2 - 9
        d.line(
            (
                cx + math.cos(ang) * outer,
                cy + math.sin(ang) * outer,
                cx + math.cos(ang) * inner,
                cy + math.sin(ang) * inner,
            ),
            fill=(36, 26, 8),
            width=1,
        )
    d.ellipse((10, 10, size - 11, size - 11), fill=(168, 128, 42), outline=GOLD)
    d.ellipse((16, 16, size - 17, size - 17), fill=(198, 158, 58), outline=GOLD_DIM)
    d.ellipse((22, 22, size - 23, size - 23), outline=PALE, width=1)
    d.ellipse((28, 28, size - 29, size - 29), fill=(214, 176, 72))
    d.pieslice((28, 28, size - 29, size - 29), start=200, end=250, fill=(232, 200, 110))
    d.ellipse((36, 36, size - 37, size - 37), fill=(214, 176, 72))
    mid = size // 2
    if face == "tails":
        d.ellipse((mid - 16, 42, mid + 16, 74), outline=INK, width=2)
        d.ellipse((mid - 10, 48, mid + 10, 68), fill=GOLD_DARK)
        d.arc((mid - 22, 52, mid + 22, 64), start=200, end=340, fill=INK, width=2)
    else:
        d.polygon(
            [(mid, 40), (mid + 5, 52), (mid + 18, 52), (mid + 8, 60), (mid + 12, 73), (mid, 66), (mid - 12, 73), (mid - 8, 60), (mid - 18, 52), (mid - 5, 52)],
            outline=INK,
            width=2,
        )
        d.ellipse((mid - 3, 54, mid + 3, 60), fill=INK)
    plate_y = mid + 8
    d.rounded_rectangle((mid - 46, plate_y, mid + 46, plate_y + 28), radius=6, fill=PALE, outline=INK, width=1)
    label = "TAILS" if face == "tails" else "HEADS"
    d.text((mid, plate_y + 14), label, font=_font(18), fill=INK, anchor="mm")
    return img


def _flat_sprite(face: str) -> Image.Image:
    full = _face(COIN, face)
    eh = max(20, int(COIN * FLAT))
    face_img = full.resize((COIN, eh), Image.Resampling.LANCZOS)
    thick = 10
    sprite = Image.new("RGBA", (COIN, eh + thick), (0, 0, 0, 0))
    td = ImageDraw.Draw(sprite)
    td.ellipse((0, thick - 2, COIN - 1, eh + thick - 1), fill=GOLD_DARK, outline=GOLD)
    sprite.alpha_composite(face_img, (0, 0))
    return sprite


def _edge_horizontal(width: int, height: int) -> Image.Image:
    img = Image.new("RGBA", (width, max(12, height)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, width - 1, img.height - 1), radius=img.height // 2, fill=GOLD_DIM, outline=GOLD)
    mid = img.height // 2
    d.rectangle((8, mid - 2, width - 9, mid + 2), fill=HIGHLIGHT)
    for i in range(14):
        x = 8 + i * ((width - 16) / 13)
        d.line((x, 2, x, img.height - 3), fill=(36, 26, 8), width=1)
    return img


def _side_standing() -> Image.Image:
    w, h = 34, int(COIN * 0.95)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((1, 1, w - 2, h - 2), radius=14, fill=GOLD_DIM, outline=GOLD, width=2)
    d.rectangle((w // 2 - 2, 10, w // 2 + 3, h - 10), fill=HIGHLIGHT)
    for i in range(14):
        y = 10 + i * ((h - 20) / 13)
        d.line((4, y, w - 5, y), fill=(36, 26, 8), width=1)
    d.ellipse((w // 2 - 5, 8, w // 2 + 5, 18), fill=GOLD_DARK, outline=PALE)
    d.ellipse((w // 2 - 5, h - 18, w // 2 + 5, h - 8), fill=GOLD_DARK, outline=PALE)
    return img


def _composite(coin: Image.Image, y: int) -> bytes:
    canvas = _space(W, H)
    x = (W - coin.width) // 2
    y = max(8, min(y, FLOOR - coin.height))
    canvas.alpha_composite(coin, (x, y))
    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_flip_frame(tilt_deg: float, y_frac: float, preview_face: str = "heads") -> bytes:
    top = 16
    squash = abs(math.cos(math.radians(tilt_deg)))
    floor = FLOOR - int(COIN * FLAT)
    y = int(top + max(0.0, min(1.0, y_frac)) * (floor - top))
    if squash < 0.16:
        coin = _edge_horizontal(COIN, max(12, int(COIN * 0.14)))
    else:
        shown = "tails" if 90 < (tilt_deg % 360) < 270 else "heads"
        face = _face(COIN, shown)
        coin = face.resize((COIN, max(12, int(COIN * max(0.14, squash)))), Image.Resampling.LANCZOS)
    return _composite(coin, y)


def render_result(face: str) -> bytes:
    if face == "side":
        coin = _side_standing()
        return _composite(coin, FLOOR - coin.height)
    coin = _flat_sprite("tails" if face == "tails" else "heads")
    return _composite(coin, FLOOR - coin.height)


def render_thumb(face: str) -> bytes:
    size = 256
    img = _space(size, size)
    if face == "side":
        coin = _side_standing()
    else:
        coin = _flat_sprite("tails" if face == "tails" else "heads")
    img.alpha_composite(coin, ((size - coin.width) // 2, (size - coin.height) // 2))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# Mid-air only. Land pose is a separate frame in slash_cointoss.
FLIP_BEATS: list[tuple[float, float]] = [
    (8.0, 0.00),
    (38.0, 0.08),
    (72.0, 0.16),
    (108.0, 0.24),
    (142.0, 0.32),
    (178.0, 0.40),
    (214.0, 0.48),
    (248.0, 0.56),
    (284.0, 0.64),
    (318.0, 0.72),
    (352.0, 0.80),
    (20.0, 0.88),
]
