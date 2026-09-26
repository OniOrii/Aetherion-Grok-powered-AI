"""Felt table + gold rank cards for /highlow."""
from __future__ import annotations

import io
from pathlib import Path
from random import Random

from PIL import Image, ImageDraw, ImageFont

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
)

VOID = (6, 10, 18)
FELT = (18, 42, 34)
FELT_EDGE = (10, 24, 20)
GOLD = (212, 176, 78)
GOLD_DIM = (132, 102, 42)
GOLD_DARK = (58, 42, 16)
PALE = (236, 214, 150)
INK = (28, 18, 6)
CREAM = (244, 236, 214)
RED = (168, 52, 48)
W, H = 560, 340
CARD_W, CARD_H = 168, 236


def _font(size: int) -> ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _felt() -> Image.Image:
    img = Image.new("RGB", (W, H), VOID)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((18, 18, W - 19, H - 19), radius=28, fill=FELT, outline=GOLD_DIM, width=3)
    d.rounded_rectangle((28, 28, W - 29, H - 29), radius=22, outline=FELT_EDGE, width=2)
    rng = Random(560 * 17 + 340)
    pix = img.load()
    for _ in range(420):
        x = rng.randint(32, W - 33)
        y = rng.randint(32, H - 33)
        shade = rng.randint(-8, 10)
        pix[x, y] = (
            max(0, min(255, FELT[0] + shade)),
            max(0, min(255, FELT[1] + shade)),
            max(0, min(255, FELT[2] + shade)),
        )
    return img.convert("RGBA")


def _card_back() -> Image.Image:
    img = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, CARD_W - 1, CARD_H - 1), radius=18, fill=GOLD_DARK, outline=GOLD, width=3)
    d.rounded_rectangle((12, 12, CARD_W - 13, CARD_H - 13), radius=12, outline=GOLD, width=2)
    for i in range(8):
        y = 28 + i * 22
        d.line((24, y, CARD_W - 25, y), fill=GOLD_DIM, width=2)
    cx, cy = CARD_W / 2, CARD_H / 2
    d.polygon([(cx, cy - 28), (cx + 28, cy), (cx, cy + 28), (cx - 28, cy)], fill=GOLD)
    d.text((CARD_W / 2, CARD_H / 2), "\u2726", font=_font(28), fill=INK, anchor="mm")
    return img


def _card_face(rank: str) -> Image.Image:
    img = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, CARD_W - 1, CARD_H - 1), radius=18, fill=CREAM, outline=GOLD_DARK, width=3)
    d.rounded_rectangle((8, 8, CARD_W - 9, CARD_H - 9), radius=12, outline=GOLD_DIM, width=1)
    color = RED if rank in ("A", "K", "Q") else INK
    big = _font(72 if rank != "10" else 58)
    small = _font(26)
    d.text((CARD_W / 2, CARD_H / 2 - 8), rank, font=big, fill=color, anchor="mm")
    d.text((22, 28), rank, font=small, fill=color, anchor="mm")
    d.text((CARD_W - 22, CARD_H - 28), rank, font=small, fill=color, anchor="mm")
    d.text((CARD_W / 2, CARD_H - 36), "\u2726", font=_font(22), fill=GOLD_DIM, anchor="mm")
    return img


def _paste_card(canvas: Image.Image, card: Image.Image, x: int, y: int) -> None:
    canvas.alpha_composite(card, (x, y))


def render_table(left: str | None, right: str | None = None, *, flipping: bool = False) -> bytes:
    canvas = _felt()
    y = (H - CARD_H) // 2
    if right is None and not flipping:
        x = (W - CARD_W) // 2
        _paste_card(canvas, _card_face(left or "A"), x, y)
    else:
        gap = 36
        total = CARD_W * 2 + gap
        x0 = (W - total) // 2
        _paste_card(canvas, _card_face(left or "A"), x0, y)
        shown = _card_back() if flipping or right is None else _card_face(right)
        _paste_card(canvas, shown, x0 + CARD_W + gap, y)
    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()
