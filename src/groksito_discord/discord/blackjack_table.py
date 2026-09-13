"""Draw a felt blackjack table with real card faces (PIL)."""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .blackjack import SUIT_SYM, Card, RANK_SYM, hand_value

FELT = (12, 28, 22)
FELT_EDGE = (8, 18, 14)
GOLD = (201, 162, 39)
GOLD_DIM = (140, 112, 28)
INK = (18, 16, 14)
CREAM = (246, 242, 232)
RED = (176, 48, 48)
BLACK = (22, 22, 22)
BACK = (28, 36, 48)
BACK_LINE = (201, 162, 39)
SHADOW = (0, 0, 0, 110)

CARD_W = 132
CARD_H = 186
RADIUS = 14
GAP = 18
PAD_X = 48
PAD_Y = 36

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


def _rounded(draw: ImageDraw.ImageDraw, box, radius: int, fill, outline=None, width: int = 1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _draw_suit(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, suit: str, color):
    s = size
    if suit == "D":
        draw.polygon(
            [(cx, cy - s), (cx + int(s * 0.72), cy), (cx, cy + s), (cx - int(s * 0.72), cy)],
            fill=color,
        )
        return
    if suit == "H":
        r = int(s * 0.42)
        draw.ellipse((cx - s + 2, cy - r - 4, cx + 2, cy + r + 2), fill=color)
        draw.ellipse((cx - 2, cy - r - 4, cx + s - 2, cy + r + 2), fill=color)
        draw.polygon(
            [(cx - s + 4, cy), (cx + s - 4, cy), (cx, cy + s + 4)],
            fill=color,
        )
        return
    if suit == "S":
        draw.polygon(
            [(cx, cy - s), (cx + int(s * 0.78), cy + 2), (cx - int(s * 0.78), cy + 2)],
            fill=color,
        )
        draw.ellipse((cx - s + 4, cy - 6, cx + 2, cy + int(s * 0.7)), fill=color)
        draw.ellipse((cx - 2, cy - 6, cx + s - 4, cy + int(s * 0.7)), fill=color)
        draw.polygon(
            [(cx - 6, cy + int(s * 0.35)), (cx + 6, cy + int(s * 0.35)), (cx, cy + s + s + 6) if False else (cx, cy + s + 6)],
            fill=color,
        )
        return
    r = int(s * 0.38)
    draw.ellipse((cx - r, cy - s + 2, cx + r, cy - 2), fill=color)
    draw.ellipse((cx - s + 2, cy - r, cx + 2, cy + r + 4), fill=color)
    draw.ellipse((cx - 2, cy - r, cx + s - 2, cy + r + 4), fill=color)
    draw.polygon(
        [(cx - 5, cy + 4), (cx + 5, cy + 4), (cx, cy + s + 6)],
        fill=color,
    )


def _card_face(rank: int, suit: str) -> Image.Image:
    img = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _rounded(d, (0, 0, CARD_W - 1, CARD_H - 1), RADIUS, CREAM, outline=(210, 204, 190), width=2)
    color = RED if suit in ("H", "D") else BLACK
    face = RANK_SYM.get(rank, str(rank))
    pip = SUIT_SYM[suit]
    corner = _font(24)
    pip_f = _font(20)
    d.text((14, 8), face, font=corner, fill=color)
    d.text((14, 34), pip, font=pip_f, fill=color)
    _draw_suit(d, CARD_W // 2, CARD_H // 2 + 4, 30, suit, color)
    d.text((CARD_W - 14, CARD_H - 36), pip, font=pip_f, fill=color, anchor="rt")
    d.text((CARD_W - 14, CARD_H - 10), face, font=corner, fill=color, anchor="rb")
    return img


def _card_back() -> Image.Image:
    img = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _rounded(d, (0, 0, CARD_W - 1, CARD_H - 1), RADIUS, BACK, outline=GOLD_DIM, width=2)
    inner = (10, 10, CARD_W - 11, CARD_H - 11)
    _rounded(d, inner, 10, (22, 30, 40), outline=GOLD_DIM, width=1)
    for y in range(24, CARD_H - 24, 16):
        for x in range(24, CARD_W - 24, 16):
            if (x + y) % 32 == 0:
                d.regular_polygon((x, y, 5), n_sides=4, rotation=45, fill=BACK_LINE)
    monogram = _font(36)
    d.text((CARD_W // 2, CARD_H // 2), "A", font=monogram, fill=GOLD, anchor="mm")
    return img


def _shadow(card: Image.Image) -> Image.Image:
    pad = 10
    base = Image.new("RGBA", (card.width + pad, card.height + pad), (0, 0, 0, 0))
    sh = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    _rounded(sd, (4, 6, card.width + 4, card.height + 6), RADIUS + 1, SHADOW)
    sh = sh.filter(ImageFilter.GaussianBlur(4))
    base.alpha_composite(sh)
    base.alpha_composite(card, (0, 0))
    return base


def _row_width(n: int) -> int:
    if n <= 0:
        n = 1
    return n * CARD_W + (n - 1) * GAP


def render_table_png(
    player: list[Card],
    dealer: list[Card],
    *,
    hide_hole: bool,
    subtitle: str = "",
) -> bytes:
    n = max(len(player), len(dealer), 2)
    width = max(720, PAD_X * 2 + _row_width(n))
    header = 46
    gap_rows = 28
    height = PAD_Y + header + CARD_H + gap_rows + 28 + CARD_H + PAD_Y + 36
    img = Image.new("RGB", (width, height), FELT)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((10, 10, width - 11, height - 11), radius=28, outline=GOLD_DIM, width=2)
    d.rounded_rectangle((16, 16, width - 17, height - 17), radius=24, outline=(20, 48, 36), width=1)
    title_f = _font(22)
    small_f = _font(16)
    d.text((width // 2, 30), "AETHERION TABLE", font=title_f, fill=GOLD, anchor="mm")

    def paste_row(cards: list[Card], y: int, hide_last: bool):
        count = max(len(cards), 1)
        row_w = _row_width(count)
        x0 = (width - row_w) // 2
        for i, card in enumerate(cards):
            if hide_last and i == len(cards) - 1 and len(cards) >= 2:
                face = _card_back()
            else:
                face = _card_face(*card)
            stamped = _shadow(face)
            img.paste(stamped, (x0 + i * (CARD_W + GAP), y), stamped)

    dealer_total = "??" if hide_hole else str(hand_value(dealer))
    d.text((PAD_X, header + 8), f"AETHERION  \u00b7  {dealer_total}", font=small_f, fill=CREAM)
    paste_row(dealer, header + 28, hide_hole)
    player_y = header + 28 + CARD_H + gap_rows
    d.text((PAD_X, player_y - 2), f"YOU  \u00b7  {hand_value(player)}", font=small_f, fill=CREAM)
    paste_row(player, player_y + 18, False)
    if subtitle:
        d.text((width // 2, height - 22), subtitle, font=small_f, fill=GOLD, anchor="mm")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_hand_png(hand, *, reveal: bool) -> bytes:
    hide = not reveal and not getattr(hand, "finished", False)
    if getattr(hand, "finished", False) and hasattr(hand, "result_line"):
        subtitle = hand.result_line()
    elif hide:
        subtitle = "Hit, stand, or double."
    else:
        subtitle = ""
    return render_table_png(
        list(hand.player),
        list(hand.dealer),
        hide_hole=hide,
        subtitle=subtitle,
    )
