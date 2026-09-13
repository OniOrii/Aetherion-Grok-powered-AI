"""Draw an Aetherion blackjack table: cosmos felt + real card faces."""
from __future__ import annotations

import io
from pathlib import Path
from random import Random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .blackjack import Card, RANK_SYM, hand_value

VOID = (6, 8, 16)
GOLD = (212, 176, 72)
GOLD_DIM = (148, 118, 42)
CREAM = (248, 244, 234)
RED = (178, 36, 42)
BLACK = (20, 20, 22)
BACK = (16, 22, 40)
SHADOW = (0, 0, 0, 130)
NEBULA_TEAL = (40, 90, 110, 70)
NEBULA_VIOLET = (70, 40, 110, 65)

CARD_W = 140
CARD_H = 196
RADIUS = 16
GAP = 16
PAD_X = 40
PAD_Y = 28

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


def _draw_suit(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, suit: str, color) -> None:
    s = max(8, int(size))
    if suit == "D":
        draw.polygon(
            [(cx, cy - s), (cx + int(s * 0.68), cy), (cx, cy + s), (cx - int(s * 0.68), cy)],
            fill=color,
        )
        return
    if suit == "H":
        r = int(s * 0.46)
        draw.ellipse((cx - s + 1, cy - r - 2, cx + 3, cy + r), fill=color)
        draw.ellipse((cx - 3, cy - r - 2, cx + s - 1, cy + r), fill=color)
        draw.polygon([(cx - s + 2, cy + 2), (cx + s - 2, cy + 2), (cx, cy + s + 3)], fill=color)
        return
    if suit == "S":
        draw.polygon([(cx, cy - s - 2), (cx + int(s * 0.82), cy + 4), (cx - int(s * 0.82), cy + 4)], fill=color)
        r = int(s * 0.42)
        draw.ellipse((cx - s + 2, cy - 2, cx + 4, cy + r + 6), fill=color)
        draw.ellipse((cx - 4, cy - 2, cx + s - 2, cy + r + 6), fill=color)
        stem = max(3, s // 6)
        draw.rectangle((cx - stem, cy + 4, cx + stem, cy + s + 4), fill=color)
        draw.polygon([(cx - s // 2, cy + s + 4), (cx + s // 2, cy + s + 4), (cx, cy + 6)], fill=color)
        return
    r = int(s * 0.40)
    draw.ellipse((cx - r, cy - s, cx + r, cy - 2), fill=color)
    draw.ellipse((cx - s + 1, cy - r + 2, cx + 3, cy + r + 6), fill=color)
    draw.ellipse((cx - 3, cy - r + 2, cx + s - 1, cy + r + 6), fill=color)
    stem = max(3, s // 6)
    draw.rectangle((cx - stem, cy + 2, cx + stem, cy + s + 4), fill=color)
    draw.polygon([(cx - s // 2, cy + s + 4), (cx + s // 2, cy + s + 4), (cx, cy + 8)], fill=color)


def _paint_corner(draw: ImageDraw.ImageDraw, x: int, y: int, rank: int, suit: str, color, *, bottom: bool) -> None:
    """Rank on the outer edge, pip inward, never overlapping."""
    face = RANK_SYM.get(rank, str(rank))
    font = _font(22)
    if bottom:
        draw.text((x, y), face, font=font, fill=color, anchor="rb")
        if rank in (6, 9):
            draw.line((x - 18, y + 3, x - 2, y + 3), fill=color, width=2)
        _draw_suit(draw, x - 10, y - 42, 10, suit, color)
    else:
        draw.text((x, y), face, font=font, fill=color, anchor="lt")
        if rank in (6, 9):
            draw.line((x + 1, y + 24, x + 17, y + 24), fill=color, width=2)
        _draw_suit(draw, x + 11, y + 42, 10, suit, color)


def _card_face(rank: int, suit: str) -> Image.Image:
    img = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _rounded(d, (1, 1, CARD_W - 2, CARD_H - 2), RADIUS, CREAM, outline=(214, 206, 188), width=2)
    color = RED if suit in ("H", "D") else BLACK
    _draw_suit(d, CARD_W // 2, CARD_H // 2 - 2, 30, suit, color)
    _paint_corner(d, 12, 8, rank, suit, color, bottom=False)
    _paint_corner(d, CARD_W - 12, CARD_H - 10, rank, suit, color, bottom=True)
    return img


def _card_back() -> Image.Image:
    img = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _rounded(d, (1, 1, CARD_W - 2, CARD_H - 2), RADIUS, BACK, outline=GOLD_DIM, width=2)
    _rounded(d, (10, 10, CARD_W - 11, CARD_H - 11), 10, (12, 16, 32), outline=GOLD_DIM, width=1)
    rng = Random(7)
    for _ in range(28):
        x = rng.randint(18, CARD_W - 18)
        y = rng.randint(18, CARD_H - 18)
        r = rng.choice((1, 1, 2))
        d.ellipse((x, y, x + r, y + r), fill=(210, 190, 120))
    d.text((CARD_W // 2, CARD_H // 2), "A", font=_font(38), fill=GOLD, anchor="mm")
    return img


def _shadow(card: Image.Image) -> Image.Image:
    pad = 12
    base = Image.new("RGBA", (card.width + pad, card.height + pad), (0, 0, 0, 0))
    sh = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    _rounded(sd, (5, 7, card.width + 5, card.height + 7), RADIUS + 1, SHADOW)
    sh = sh.filter(ImageFilter.GaussianBlur(5))
    base.alpha_composite(sh)
    base.alpha_composite(card, (0, 0))
    return base


def _space_field(width: int, height: int) -> Image.Image:
    img = Image.new("RGB", (width, height), VOID)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.ellipse((-width // 4, -height // 5, width // 2 + 40, height // 2 + 40), fill=NEBULA_VIOLET)
    d.ellipse((width // 3, height // 4, width + 80, height + 40), fill=NEBULA_TEAL)
    d.ellipse((width // 5, height // 2, width * 2 // 3, height + 60), fill=(20, 30, 70, 50))
    overlay = overlay.filter(ImageFilter.GaussianBlur(28))
    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    stars = ImageDraw.Draw(img)
    rng = Random(width * 13 + height)
    for _ in range(max(90, width * height // 2800)):
        x = rng.randint(8, width - 8)
        y = rng.randint(8, height - 8)
        r = rng.choice((0, 0, 1, 1, 2))
        c = rng.randint(160, 240)
        stars.ellipse((x, y, x + r, y + r), fill=(c, c - 8, min(255, c + 10)))
    return img.convert("RGB")


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
    width = max(760, PAD_X * 2 + _row_width(n))
    header = 50
    gap_rows = 34
    height = PAD_Y + header + CARD_H + gap_rows + 26 + CARD_H + PAD_Y + 34
    img = _space_field(width, height)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((10, 10, width - 11, height - 11), radius=30, outline=GOLD_DIM, width=2)
    d.rounded_rectangle((16, 16, width - 17, height - 17), radius=26, outline=(80, 70, 40), width=1)
    title_f = _font(22)
    small_f = _font(16)
    d.text((width // 2, 32), "AETHERION TABLE", font=title_f, fill=GOLD, anchor="mm")

    def paste_row(cards: list[Card], y: int, hide_last: bool) -> None:
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
    d.text((PAD_X, header + 6), f"AETHERION  \u00b7  {dealer_total}", font=small_f, fill=CREAM)
    paste_row(dealer, header + 28, hide_hole)
    player_y = header + 28 + CARD_H + gap_rows
    d.text((PAD_X, player_y - 4), f"YOU  \u00b7  {hand_value(player)}", font=small_f, fill=CREAM)
    paste_row(player, player_y + 16, False)
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
