"""Aetherion lifetime activity card. Drawn with Pillow. No Grok images."""
from __future__ import annotations

import io
import logging
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

from . import activity
from .brand import GOLD

logger = logging.getLogger("aetherion.activity_card")

BG = (16, 18, 24)
PANEL = (28, 31, 40)
PANEL2 = (36, 40, 52)
GOLD_RGB = ((GOLD >> 16) & 255, (GOLD >> 8) & 255, GOLD & 255)
WHITE = (236, 232, 222)
MUTED = (158, 154, 144)
LINE = (54, 50, 40)
W, H = 980, 520


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    )
    for path in names:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _text(draw: ImageDraw.ImageDraw, xy, text, font, fill=WHITE):
    draw.text(xy, str(text), font=font, fill=fill)


def _round(draw: ImageDraw.ImageDraw, box, fill, radius=16):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def _date(value) -> str:
    if value is None:
        return "Unknown"
    if isinstance(value, datetime):
        return value.strftime("%B %d, %Y")
    return str(value)


def _circle_avatar(raw: bytes | None, size: int) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.ellipse((0, 0, size - 1, size - 1), fill=GOLD_RGB)
    if not raw:
        return canvas
    try:
        im = Image.open(io.BytesIO(raw)).convert("RGBA")
        im = im.resize((size - 8, size - 8), Image.Resampling.LANCZOS)
        mask = Image.new("L", im.size, 0)
        ImageDraw.Draw(mask).ellipse((0, 0, im.size[0] - 1, im.size[1] - 1), fill=255)
        inner = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        inner.paste(im, (4, 4), mask)
        canvas.alpha_composite(inner)
    except Exception:
        logger.exception("avatar crop failed")
    return canvas


def render_activity_card(member, snap: dict, avatar_bytes: bytes | None = None) -> io.BytesIO:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    title = _font(28, True)
    name_f = _font(26, True)
    sub = _font(15)
    label = _font(13, True)
    body = _font(20, True)
    small = _font(14)
    tiny = _font(12)

    d.rectangle((0, 0, W, 6), fill=GOLD_RGB)

    display = getattr(member, "display_name", None) or getattr(member, "name", "User")
    handle = getattr(member, "name", "") or ""
    avatar = _circle_avatar(avatar_bytes, 86)
    img.paste(avatar, (28, 28), avatar)
    _text(d, (130, 34), display[:28], name_f, WHITE)
    _text(d, (130, 70), f"@{handle}"[:32], sub, MUTED)
    roles = [r.name for r in getattr(member, "roles", []) if not r.is_default()]
    roles.sort(key=lambda n: n.lower())
    tag = "  \u00b7  ".join(roles[:3])[:42]
    if tag:
        _text(d, (130, 92), tag.upper(), tiny, GOLD_RGB)

    created = _date(getattr(member, "created_at", None))
    joined = _date(getattr(member, "joined_at", None))
    _round(d, (690, 24, 830, 96), PANEL)
    _round(d, (846, 24, 956, 96), PANEL)
    _text(d, (704, 32), "CREATED", tiny, GOLD_RGB)
    _text(d, (704, 54), created, small, WHITE)
    _text(d, (860, 32), "JOINED", tiny, GOLD_RGB)
    _text(d, (860, 54), joined, small, WHITE)

    _round(d, (24, 136, 332, 286), PANEL)
    _text(d, (44, 152), "SERVER RANKS", label, GOLD_RGB)
    msg_rank = snap.get("msg_rank")
    voice_rank = snap.get("voice_rank")
    _text(d, (44, 190), "Messages", small, MUTED)
    _text(d, (200, 186), f"#{msg_rank}" if msg_rank else "\u2014", body, WHITE)
    _text(d, (44, 236), "Voice", small, MUTED)
    _text(d, (200, 232), f"#{voice_rank}" if voice_rank else "\u2014", body, WHITE)

    _round(d, (348, 136, 656, 286), PANEL)
    _text(d, (368, 152), "MESSAGES", label, GOLD_RGB)
    _text(d, (368, 198), f"{int(snap.get('messages') or 0):,}", _font(32, True), WHITE)
    _text(d, (368, 244), "lifetime", small, MUTED)

    _round(d, (672, 136, 956, 286), PANEL)
    _text(d, (692, 152), "VOICE", label, GOLD_RGB)
    _text(d, (692, 198), activity.format_voice(int(snap.get("voice_seconds") or 0)), _font(32, True), WHITE)
    _text(d, (692, 244), "lifetime", small, MUTED)

    _round(d, (24, 302, 656, 454), PANEL)
    _text(d, (44, 318), "TOP CHANNELS", label, GOLD_RGB)
    channels = list(snap.get("top_channels") or [])
    if not channels:
        _text(d, (44, 368), "No channel data yet", body, MUTED)
    else:
        y = 356
        for name, count in channels[:4]:
            _round(d, (44, y, 636, y + 28), PANEL2, radius=8)
            _text(d, (56, y + 6), f"# {name}"[:34], small, WHITE)
            _text(d, (520, y + 6), f"{int(count):,} msg", small, GOLD_RGB)
            y += 34

    _round(d, (672, 302, 956, 454), PANEL)
    _text(d, (692, 318), "LEVEL", label, GOLD_RGB)
    _text(d, (692, 354), str(snap.get("level") or 0), _font(36, True), WHITE)
    into = int(snap.get("into") or 0)
    need = max(1, int(snap.get("need") or 1))
    _text(d, (692, 404), f"{into} / {need} XP", small, MUTED)
    bar_x, bar_y, bar_w = 692, 428, 240
    d.rounded_rectangle((bar_x, bar_y, bar_x + bar_w, bar_y + 10), radius=5, fill=PANEL2)
    fill_w = int(bar_w * min(1.0, into / need))
    if fill_w:
        d.rounded_rectangle((bar_x, bar_y, bar_x + fill_w, bar_y + 10), radius=5, fill=GOLD_RGB)

    _text(d, (28, 478), "\u2726 Aetherion", title, GOLD_RGB)
    started = snap.get("started") or "now"
    _text(d, (220, 488), f"Lifetime  \u00b7  tracked since {started}  \u00b7  this server", small, MUTED)

    out = io.BytesIO()
    img.save(out, format="PNG")
    out.seek(0)
    return out
