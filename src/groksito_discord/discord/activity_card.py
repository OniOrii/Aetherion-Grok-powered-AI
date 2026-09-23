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
W, H = 1400, 980


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


def _round(draw: ImageDraw.ImageDraw, box, fill, radius=18):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def _date(value) -> str:
    if value is None:
        return "Unknown"
    if isinstance(value, datetime):
        return value.strftime("%b %d, %Y")
    return str(value)


def _top_role(member) -> str:
    roles = [r for r in getattr(member, "roles", []) if not r.is_default()]
    if not roles:
        return ""
    roles.sort(key=lambda r: r.position, reverse=True)
    return str(getattr(roles[0], "name", "") or "")[:28]


def _circle_avatar(raw: bytes | None, size: int) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.ellipse((0, 0, size - 1, size - 1), fill=GOLD_RGB)
    if not raw:
        return canvas
    try:
        im = Image.open(io.BytesIO(raw)).convert("RGBA")
        im = im.resize((size - 10, size - 10), Image.Resampling.LANCZOS)
        mask = Image.new("L", im.size, 0)
        ImageDraw.Draw(mask).ellipse((0, 0, im.size[0] - 1, im.size[1] - 1), fill=255)
        inner = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        inner.paste(im, (5, 5), mask)
        canvas.alpha_composite(inner)
    except Exception:
        logger.exception("avatar crop failed")
    return canvas


def render_activity_card(member, snap: dict, avatar_bytes: bytes | None = None) -> io.BytesIO:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    title = _font(34, True)
    name_f = _font(38, True)
    sub = _font(22)
    label = _font(17, True)
    body = _font(30, True)
    number = _font(48, True)
    small = _font(20)
    tiny = _font(16, True)

    d.rectangle((0, 0, W, 8), fill=GOLD_RGB)

    display = getattr(member, "display_name", None) or getattr(member, "name", "User")
    handle = getattr(member, "name", "") or ""
    avatar = _circle_avatar(avatar_bytes, 120)
    img.paste(avatar, (36, 32), avatar)
    _text(d, (176, 44), display[:26], name_f, WHITE)
    _text(d, (176, 94), f"@{handle}"[:28], sub, MUTED)
    tag = _top_role(member)
    if tag:
        _text(d, (176, 128), tag, tiny, GOLD_RGB)

    created = _date(getattr(member, "created_at", None))
    joined = _date(getattr(member, "joined_at", None))
    _round(d, (36, 180, 688, 292), PANEL)
    _round(d, (712, 180, 1364, 292), PANEL)
    _text(d, (60, 200), "CREATED", tiny, GOLD_RGB)
    _text(d, (60, 236), created, body, WHITE)
    _text(d, (736, 200), "JOINED", tiny, GOLD_RGB)
    _text(d, (736, 236), joined, body, WHITE)

    _round(d, (36, 316, 456, 548), PANEL)
    _text(d, (60, 340), "SERVER RANKS", label, GOLD_RGB)
    msg_rank = snap.get("msg_rank")
    voice_rank = snap.get("voice_rank")
    _text(d, (60, 396), "Messages", small, MUTED)
    _text(d, (240, 384), f"#{msg_rank}" if msg_rank else "\u2014", number, WHITE)
    _text(d, (60, 476), "Voice", small, MUTED)
    _text(d, (240, 464), f"#{voice_rank}" if voice_rank else "\u2014", number, WHITE)

    _round(d, (480, 316, 900, 548), PANEL)
    _text(d, (504, 340), "MESSAGES", label, GOLD_RGB)
    _text(d, (504, 400), f"{int(snap.get('messages') or 0):,}", number, WHITE)
    _text(d, (504, 480), "lifetime", small, MUTED)

    _round(d, (924, 316, 1364, 548), PANEL)
    _text(d, (948, 340), "VOICE", label, GOLD_RGB)
    _text(d, (948, 400), activity.format_voice(int(snap.get("voice_seconds") or 0)), number, WHITE)
    _text(d, (948, 480), "lifetime", small, MUTED)

    _round(d, (36, 572, 900, 868), PANEL)
    _text(d, (60, 596), "TOP CHANNELS", label, GOLD_RGB)
    channels = list(snap.get("top_channels") or [])
    if not channels:
        _text(d, (60, 680), "No channel data yet", body, MUTED)
    else:
        y = 648
        for name, count in channels[:4]:
            _round(d, (60, y, 876, y + 44), PANEL2, radius=10)
            _text(d, (76, y + 10), f"# {name}"[:28], small, WHITE)
            _text(d, (690, y + 10), f"{int(count):,} msg", small, GOLD_RGB)
            y += 52

    _round(d, (924, 572, 1364, 868), PANEL)
    _text(d, (948, 596), "LEVEL", label, GOLD_RGB)
    _text(d, (948, 660), str(snap.get("level") or 0), _font(64, True), WHITE)
    into = int(snap.get("into") or 0)
    need = max(1, int(snap.get("need") or 1))
    _text(d, (948, 760), f"{into} / {need} XP", small, MUTED)
    bar_x, bar_y, bar_w = 948, 804, 380
    d.rounded_rectangle((bar_x, bar_y, bar_x + bar_w, bar_y + 16), radius=8, fill=PANEL2)
    fill_w = int(bar_w * min(1.0, into / need))
    if fill_w:
        d.rounded_rectangle((bar_x, bar_y, bar_x + fill_w, bar_y + 16), radius=8, fill=GOLD_RGB)

    _text(d, (36, 900), "\u2726 Aetherion", title, GOLD_RGB)
    started = snap.get("started") or "now"
    _text(d, (280, 914), f"Lifetime  \u00b7  tracked since {started}  \u00b7  this server", small, MUTED)

    out = io.BytesIO()
    img.save(out, format="PNG")
    out.seek(0)
    return out
