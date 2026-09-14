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

W, H = 320, 420
COIN = 168


def _font(size: int) -> ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _space(width: int, height: int) -> Image.Image:
    img = Image.new("RGB", (width, height), VOID)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.ellipse((-40, -20, 200, 160), fill=(40, 70, 140, 70))
    d.ellipse((80, 180, 380, 420), fill=(70, 40, 110, 60))
    overlay = overlay.filter(ImageFilter.GaussianBlur(24))
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def _face(size: int, face: str) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((2, 2, size - 3, size - 3), fill=GOLD_DARK, outline=GOLD)
    d.ellipse((8, 8, size - 9, size - 9), fill=(186, 150, 48, 255), outline=GOLD_DIM)
    d.ellipse((16, 16, size - 17, size - 17), fill=(*GOLD, 255))
    cx = cy = size // 2
    if face == "tails":
        d.text((cx, cy - 10), "A", font=_font(46), fill=CREAM, anchor="mm")
        d.text((cx, cy + 30), "TAILS", font=_font(14), fill=INK, anchor="mm")
    else:
        d.text((cx, cy - 10), "\u2726", font=_font(44), fill=CREAM, anchor="mm")
        d.text((cx, cy + 30), "HEADS", font=_font(14), fill=INK, anchor="mm")
    return img


def _edge(width: int, height: int) -> Image.Image:
    img = Image.new("RGBA", (max(12, width), height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, img.width - 1, height - 1), radius=img.width // 2, fill=GOLD_DIM, outline=GOLD)
    mid = img.width // 2
    d.rectangle((mid - 1, 10, mid + 2, height - 10), fill=CREAM)
    return img


def _side_standing(size: int) -> Image.Image:
    """Coin resting on its rim."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = size // 2
    d.rounded_rectangle((cx - 14, 18, cx + 14, size - 18), radius=12, fill=GOLD_DIM, outline=GOLD, width=2)
    d.rectangle((cx - 2, 28, cx + 2, size - 28), fill=CREAM)
    d.ellipse((cx - 16, size - 28, cx + 16, size - 12), fill=(0, 0, 0, 80))
    return img


def _composite(coin: Image.Image, y: int) -> bytes:
    canvas = _space(W, H)
    x = (W - coin.width) // 2
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse((x + 16, y + coin.height - 10, x + coin.width - 16, y + coin.height + 12), fill=(0, 0, 0, 90))
    shadow = shadow.filter(ImageFilter.GaussianBlur(6))
    canvas = Image.alpha_composite(canvas, shadow)
    canvas.alpha_composite(coin, (x, y))
    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_flip_frame(tilt_deg: float, y_frac: float, preview_face: str = "heads") -> bytes:
    squash = abs(math.cos(math.radians(tilt_deg)))
    y = int(24 + max(0.0, min(1.0, y_frac)) * (H - 24 - COIN - 18))
    if squash < 0.16:
        coin = _edge(max(12, int(COIN * 0.12)), COIN)
    else:
        shown = "tails" if 90 < (tilt_deg % 360) < 270 else "heads"
        face = _face(COIN, shown)
        coin = face.resize((max(12, int(COIN * max(0.12, squash))), COIN), Image.Resampling.LANCZOS)
    return _composite(coin, y)


def render_result(face: str) -> bytes:
    y = H - COIN - 36
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
        coin = _side_standing(200)
    else:
        coin = _face(200, "tails" if face == "tails" else "heads")
    img.alpha_composite(coin, ((size - coin.width) // 2, (size - coin.height) // 2))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


FLIP_BEATS: list[tuple[float, float]] = [
    (8.0, 0.04),
    (72.0, 0.20),
    (118.0, 0.38),
    (188.0, 0.56),
    (256.0, 0.74),
    (322.0, 0.86),
]
