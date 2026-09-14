"""Aetherion Texas Hold'em table art. Cosmos felt, real card faces."""
from __future__ import annotations

import io
from pathlib import Path
from random import Random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

VOID = (6, 8, 16)
GOLD = (212, 176, 72)
GOLD_DIM = (148, 118, 42)
CREAM = (248, 244, 234)
RED = (178, 36, 42)
BLACK = (20, 20, 22)
BACK = (16, 22, 40)
SHADOW = (0, 0, 0, 140)
NEBULA_TEAL = (40, 90, 110, 70)
NEBULA_VIOLET = (70, 40, 110, 65)
FELT = (18, 42, 36, 150)
MUTED = (170, 176, 188)

SUIT_SYM = {"S": "\u2660", "H": "\u2665", "D": "\u2666", "C": "\u2663"}
RANK_SYM = {1: "A", 11: "J", 12: "Q", 13: "K", 14: "A"}

CARD_W = 74
CARD_H = 104
HOLE_W = 118
HOLE_H = 164
RADIUS = 11
GAP = 12
SEAT_W = 268
SEAT_H = 188

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
)


def _font(size: int) -> ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _rounded(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _space_field(width: int, height: int) -> Image.Image:
    img = Image.new("RGB", (width, height), VOID)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.ellipse((-width // 4, -height // 5, width // 2 + 40, height // 2 + 40), fill=NEBULA_VIOLET)
    d.ellipse((width // 3, height // 4, width + 80, height + 40), fill=NEBULA_TEAL)
    overlay = overlay.filter(ImageFilter.GaussianBlur(28))
    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    stars = ImageDraw.Draw(img)
    rng = Random(width * 17 + height)
    for _ in range(max(90, width * height // 2800)):
        x = rng.randint(8, width - 8)
        y = rng.randint(8, height - 8)
        r = rng.choice((0, 0, 1, 1, 2))
        c = rng.randint(160, 240)
        stars.ellipse((x, y, x + r, y + r), fill=(c, c - 8, min(255, c + 10)))
    return img.convert("RGB")


def _draw_suit(draw, cx, cy, size, suit, color):
    draw.text((cx, cy), SUIT_SYM[suit], font=_font(max(12, int(size * 2.0))), fill=color, anchor="mm")


def _card_face(rank: int, suit: str, w: int = CARD_W, h: int = CARD_H) -> Image.Image:
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _rounded(d, (1, 1, w - 2, h - 2), RADIUS, CREAM, outline=(214, 206, 188), width=2)
    color = RED if suit in ("H", "D") else BLACK
    face = RANK_SYM.get(rank, str(rank))
    d.text((9, 5), face, font=_font(18), fill=color, anchor="lt")
    _draw_suit(d, 14, 36, 7, suit, color)
    _draw_suit(d, w // 2, h // 2 + 6, 18, suit, color)
    d.text((w - 9, h - 7), face, font=_font(18), fill=color, anchor="rb")
    return img


def _card_back(w: int = CARD_W, h: int = CARD_H) -> Image.Image:
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _rounded(d, (1, 1, w - 2, h - 2), RADIUS, BACK, outline=GOLD_DIM, width=2)
    _rounded(d, (7, 7, w - 8, h - 8), 8, (12, 16, 32), outline=GOLD_DIM, width=1)
    d.text((w // 2, h // 2), "A", font=_font(24), fill=GOLD, anchor="mm")
    return img


def _shadow(card: Image.Image) -> Image.Image:
    pad = 8
    base = Image.new("RGBA", (card.width + pad, card.height + pad), (0, 0, 0, 0))
    sh = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    _rounded(sd, (3, 5, card.width + 3, card.height + 5), RADIUS + 1, SHADOW)
    sh = sh.filter(ImageFilter.GaussianBlur(3))
    base.alpha_composite(sh)
    base.alpha_composite(card, (0, 0))
    return base


def _paste_cards(img: Image.Image, x: int, y: int, *, backs: int = 0, faces=None) -> None:
    faces = list(faces or [])
    total = max(backs, len(faces), 1)
    step = CARD_W + GAP
    for i in range(total):
        if i < len(faces) and faces[i] is not None:
            face = _card_face(*faces[i])
        else:
            face = _card_back()
        stamped = _shadow(face)
        img.paste(stamped, (x + i * step, y), stamped)


def render_hole_png(cards) -> bytes:
    cards = list(cards or [])
    width = 48 + max(1, len(cards)) * (HOLE_W + 14)
    height = HOLE_H + 56
    img = _space_field(max(340, width), height)
    d = ImageDraw.Draw(img)
    d.text((img.width // 2, 20), "YOUR HOLE CARDS", font=_font(16), fill=GOLD, anchor="mm")
    row = len(cards) * HOLE_W + max(0, len(cards) - 1) * 14
    x0 = (img.width - row) // 2
    for i, (rank, suit) in enumerate(cards):
        face = _shadow(_card_face(rank, suit, HOLE_W, HOLE_H))
        img.paste(face, (x0 + i * (HOLE_W + 14), 34), face)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_table_png(
    seats: list[dict],
    board: list,
    *,
    pot: int,
    street: str,
    subtitle: str = "",
    actor_id: int | None = None,
    reveal: bool = False,
) -> bytes:
    width, height = 980, 700
    img = _space_field(width, height)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((10, 10, width - 11, height - 11), radius=30, outline=GOLD_DIM, width=2)
    d.rounded_rectangle((16, 16, width - 17, height - 17), radius=26, outline=(80, 70, 40), width=1)
    d.text((width // 2, 36), "AETHERION  \u00b7  TEXAS HOLD'EM", font=_font(22), fill=GOLD, anchor="mm")
    d.text((width // 2, 62), f"{street.upper()}   \u00b7   POT  {pot}", font=_font(16), fill=CREAM, anchor="mm")

    felt = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    fd = ImageDraw.Draw(felt)
    fd.ellipse((90, 150, width - 90, height - 150), fill=FELT, outline=GOLD_DIM, width=2)
    img = Image.alpha_composite(img.convert("RGBA"), felt).convert("RGB")
    d = ImageDraw.Draw(img)

    board_w = 5 * CARD_W + 4 * GAP
    bx = (width - board_w) // 2
    by = 268
    d.rounded_rectangle((bx - 22, by - 20, bx + board_w + 14, by + CARD_H + 26), radius=18, outline=GOLD, width=2)
    d.text((width // 2, by - 8), "BOARD", font=_font(12), fill=GOLD_DIM, anchor="mm")
    for i in range(5):
        if i < len(board):
            face = _shadow(_card_face(*board[i]))
        else:
            face = _shadow(_card_back())
        img.paste(face, (bx + i * (CARD_W + GAP), by), face)

    slots = (
        (36, 86),
        (width - 36 - SEAT_W, 86),
        (36, height - 36 - SEAT_H),
        (width - 36 - SEAT_W, height - 36 - SEAT_H),
    )
    for i, seat in enumerate(seats[:4]):
        sx, sy = slots[i]
        active = not seat.get("folded")
        is_actor = actor_id is not None and seat.get("user_id") == actor_id and active and not reveal
        outline = GOLD if is_actor else GOLD_DIM
        fill_a = (16, 22, 34, 200) if active else (10, 10, 14, 170)
        panel = Image.new("RGBA", (SEAT_W, SEAT_H), (0, 0, 0, 0))
        pd = ImageDraw.Draw(panel)
        _rounded(pd, (0, 0, SEAT_W - 1, SEAT_H - 1), 16, fill_a, outline=outline, width=2)
        img.paste(panel, (sx, sy), panel)
        name = str(seat.get("name") or "Seat")[:18]
        color = MUTED if seat.get("folded") else CREAM
        d.text((sx + 16, sy + 12), name, font=_font(16), fill=GOLD if is_actor else color)
        if seat.get("folded"):
            status = "FOLDED"
        elif seat.get("all_in"):
            status = f"ALL-IN  {seat.get('stack', 0)}"
        else:
            status = f"stack {seat.get('stack', 0)}"
        d.text((sx + 16, sy + 34), status, font=_font(13), fill=MUTED)
        bet = int(seat.get("bet") or 0)
        if bet:
            d.text((sx + SEAT_W - 16, sy + 34), f"bet {bet}", font=_font(13), fill=GOLD, anchor="rt")
        hole = list(seat.get("hole") or [])
        show = reveal and hole and not seat.get("folded")
        pair_w = CARD_W * 2 + GAP
        cx = sx + (SEAT_W - pair_w) // 2
        _paste_cards(img, cx, sy + 58, backs=0 if show else 2, faces=hole if show else [])

    if subtitle:
        d.text((width // 2, height - 28), subtitle[:64], font=_font(15), fill=GOLD, anchor="mm")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
