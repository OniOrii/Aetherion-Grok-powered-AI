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

VOID = (5, 6, 16)
GOLD = (220, 186, 80)
GOLD_DIM = (148, 118, 42)
GOLD_DARK = (72, 56, 20)
INK = (36, 24, 8)
HIGHLIGHT = (236, 210, 120)

W, H = 300, 540
COIN = 132
FLAT = 0.56
PAD_Y = H - 36


def _font(size: int) -> ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _space(width: int, height: int) -> Image.Image:
    img = Image.new("RGB", (width, height), VOID)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.ellipse((-130, -90, 190, 230), fill=(96, 38, 150, 75))
    d.ellipse((10, 70, 390, 380), fill=(18, 48, 112, 85))
    d.ellipse((-50, 300, 240, 580), fill=(10, 16, 54, 75))
    d.polygon(
        [(0, height // 3), (width, height // 4), (width, height // 4 + 48), (0, height // 3 + 80)],
        fill=(190, 200, 255, 16),
    )
    overlay = overlay.filter(ImageFilter.GaussianBlur(22))
    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    stars = ImageDraw.Draw(img)
    rng = Random(width * 19 + height)
    for _ in range(240):
        x = rng.randint(2, width - 3)
        y = rng.randint(2, height - 3)
        r = rng.choice((0, 0, 0, 1, 1, 2))
        c = rng.randint(140, 255)
        stars.ellipse((x, y, x + r, y + r), fill=(c, c - 6, min(255, c + 22)))
    stars.ellipse((width - 96, 38, width - 22, 112), fill=(28, 38, 74))
    stars.ellipse((width - 86, 48, width - 32, 102), fill=(46, 76, 118))
    ring = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    rd.ellipse((width - 114, 62, width - 4, 90), outline=(210, 190, 110, 95), width=2)
    return Image.alpha_composite(img, ring)


def _paint_pad(canvas: Image.Image) -> None:
    d = ImageDraw.Draw(canvas)
    cx = W // 2
    d.ellipse((cx - 96, PAD_Y - 14, cx + 96, PAD_Y + 18), fill=(8, 10, 20, 210))
    d.ellipse((cx - 84, PAD_Y - 8, cx + 84, PAD_Y + 12), outline=GOLD_DIM, width=1)
    d.ellipse((cx - 64, PAD_Y - 2, cx + 64, PAD_Y + 6), outline=(80, 70, 40, 150), width=1)


def _face(size: int, face: str) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((1, 1, size - 2, size - 2), fill=GOLD_DARK, outline=GOLD, width=2)
    cx = cy = size / 2
    for i in range(36):
        ang = math.radians(i * 10)
        x1 = cx + math.cos(ang) * (size / 2 - 2)
        y1 = cy + math.sin(ang) * (size / 2 - 2)
        x2 = cx + math.cos(ang) * (size / 2 - 8)
        y2 = cy + math.sin(ang) * (size / 2 - 8)
        d.line((x1, y1, x2, y2), fill=(48, 36, 12), width=1)
    d.ellipse((9, 9, size - 10, size - 10), fill=(198, 156, 52, 255), outline=HIGHLIGHT)
    d.ellipse((16, 16, size - 17, size - 17), outline=(90, 70, 28), width=1)
    d.ellipse((23, 30, size - 24, size - 31), outline=(70, 52, 18, 150), width=1)
    d.arc((28, 22, size - 29, size - 23), start=200, end=48, fill=(255, 232, 160), width=2)
    if face == "tails":
        d.arc((36, 40, size - 37, size - 41), start=30, end=210, fill=(70, 52, 18), width=1)
        d.ellipse((size // 2 - 9, size // 2 - 28, size // 2 + 9, size // 2 - 10), outline=(70, 52, 18), width=1)
    else:
        d.polygon(
            [
                (size // 2, 26),
                (size // 2 + 7, 40),
                (size // 2 + 22, 42),
                (size // 2 + 10, 52),
                (size // 2 + 14, 66),
                (size // 2, 58),
                (size // 2 - 14, 66),
                (size // 2 - 10, 52),
                (size // 2 - 22, 42),
                (size // 2 - 7, 40),
            ],
            outline=(70, 52, 18),
        )
    d.text((size // 2, size // 2 - 6), "\u2726", font=_font(13), fill=(60, 40, 12), anchor="mm")
    label = "TAILS" if face == "tails" else "HEADS"
    d.text((size // 2, size // 2 + 14), label, font=_font(18), fill=INK, anchor="mm")
    return img


def _flat_sprite(face: str) -> Image.Image:
    full = _face(COIN, face)
    eh = max(18, int(COIN * FLAT))
    face_img = full.resize((COIN, eh), Image.Resampling.LANCZOS)
    thick = 12
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
    for i in range(12):
        x = 10 + i * ((width - 20) / 11)
        d.line((x, 2, x, img.height - 3), fill=(48, 36, 12), width=1)
    return img


def _side_standing() -> Image.Image:
    """Coin standing on its rim, face toward the camera is the edge."""
    w, h = 28, int(COIN * 0.92)
    img = Image.new("RGBA", (w + 8, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((4, 0, w + 3, h - 1), radius=12, fill=GOLD_DIM, outline=GOLD, width=2)
    d.rectangle((w // 2 + 1, 8, w // 2 + 5, h - 8), fill=HIGHLIGHT)
    for i in range(11):
        y = 10 + i * ((h - 20) / 10)
        d.line((6, y, w, y), fill=(48, 36, 12), width=1)
    return img


def _composite(coin: Image.Image, y: int, *, landed: bool) -> bytes:
    canvas = _space(W, H)
    _paint_pad(canvas)
    x = (W - coin.width) // 2
    max_y = PAD_Y - coin.height + 8
    y = max(8, min(y, max_y))
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse(
        (x + 6, y + coin.height - 6, x + coin.width - 6, y + coin.height + (14 if landed else 8)),
        fill=(0, 0, 0, 150 if landed else 80),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(7 if landed else 5))
    canvas = Image.alpha_composite(canvas, shadow)
    canvas.alpha_composite(coin, (x, y))
    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_flip_frame(tilt_deg: float, y_frac: float, preview_face: str = "heads") -> bytes:
    top = 14
    if y_frac >= 0.96:
        coin = _flat_sprite(preview_face)
        y = PAD_Y - coin.height + 8
        return _composite(coin, y, landed=True)
    squash = abs(math.cos(math.radians(tilt_deg)))
    floor = PAD_Y - int(COIN * FLAT) - 8
    y = int(top + max(0.0, min(1.0, y_frac)) * (floor - top))
    if squash < 0.16:
        coin = _edge_horizontal(COIN, max(12, int(COIN * 0.14)))
    else:
        shown = "tails" if 90 < (tilt_deg % 360) < 270 else "heads"
        face = _face(COIN, shown)
        coin = face.resize((COIN, max(12, int(COIN * max(0.14, squash)))), Image.Resampling.LANCZOS)
    return _composite(coin, y, landed=False)


def render_result(face: str) -> bytes:
    if face == "side":
        coin = _side_standing()
        y = PAD_Y - coin.height + 6
        return _composite(coin, y, landed=True)
    coin = _flat_sprite("tails" if face == "tails" else "heads")
    y = PAD_Y - coin.height + 8
    return _composite(coin, y, landed=True)


def render_thumb(face: str) -> bytes:
    size = 256
    img = _space(size, size)
    if face == "side":
        coin = _side_standing()
    else:
        coin = _flat_sprite("tails" if face == "tails" else "heads")
    img.alpha_composite(coin, ((size - coin.width) // 2, (size - coin.height) // 2 + 8))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


FLIP_BEATS: list[tuple[float, float]] = [
    (12.0, 0.00),
    (78.0, 0.15),
    (118.0, 0.30),
    (188.0, 0.46),
    (258.0, 0.62),
    (328.0, 0.78),
    (0.0, 1.00),
]
