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
W, H = 1400, 760


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
    name_f = _font(36, True)
    sub = _font(20)
    label = _font(16, True)
    body = _font(28, True)
    number = _font(44, True)
    small = _font(18)
    tiny = _font(15, True)

    d.rectangle((0, 0, W, 8), fill=GOLD_RGB)

    display = getattr(member, "display_name", None) or getattr(member, "name", "User")
    handle = getattr(member, "name", "") or ""
    avatar = _circle_avatar(avatar_bytes, 112)
    img.paste(avatar, (36, 28), avatar)
    _text(d, (168, 40), display[:26], name_f, WHITE)
    _text(d, (168, 86), f"@{handle}"[:28], sub, MUTED)
    roles = [r.name for r in getattr(member, "roles", []) if not r.is_default()]
    roles.sort(key=lambda n: n.lower())
    tag = "  \u00b7  ".join(roles[:2])[:36]
    if tag:
        _text(d, (168, 116), tag.upper(), tiny, GOLD_RGB)

    created = _date(getattr(member, "created_at", None))
    joined = _date(getattr(member, "joined_at", None))
    _round(d, (36, 160, 688, 248), PANEL)
    _round(d, (712, 160, 1364, 248), PANEL)
    _text(d, (60, 176), "CREATED", tiny, GOLD_RGB)
    _text(d, (60, 204), created, body, WHITE)
    _text(d, (736, 176), "JOINED", tiny, GOLD_RGB)
    _text(d, (736, 204), joined, body, WHITE)

    _round(d, (36, 272, 456, 456), PANEL)
    _text(d, (60, 292), "SERVER RANKS", label, GOLD_RGB)
    msg_rank = snap.get("msg_rank")
    voice_rank = snap.get("voice_rank")
    _text(d, (60, 338), "Messages", small, MUTED)
    _text(d, (250, 330), f"#{msg_rank}" if msg_rank else "\u2014", number, WHITE)
    _text(d, (60, 400), "Voice", small, MUTED)
    _text(d, (250, 392), f"#{voice_rank}" if voice_rank else "\u2014", number, WHITE)

    _round(d, (480, 272, 900, 456), PANEL)
    _text(d, (504, 292), "MESSAGES", label, GOLD_RGB)
    _text(d, (504, 340), f"{int(snap.get('messages') or 0):,}", number, WHITE)
    _text(d, (504, 404), "lifetime", small, MUTED)

    _round(d, (924, 272, 1364, 456), PANEL)
    _text(d, (948, 292), "VOICE", label, GOLD_RGB)
    _text(d, (948, 340), activity.format_voice(int(snap.get("voice_seconds") or 0)), number, WHITE)
    _text(d, (948, 404), "lifetime", small, MUTED)

    _round(d, (36, 480, 900, 668), PANEL)
    _text(d, (60, 500), "TOP CHANNELS", label, GOLD_RGB)
    channels = list(snap.get("top_channels") or [])
    if not channels:
        _text(d, (60, 560), "No channel data yet", body, MUTED)
    else:
        y = 544
        for name, count in channels[:3]:
            _round(d, (60, y, 876, y + 36), PANEL2, radius=10)
            _text(d, (76, y + 8), f"# {name}"[:28], small, WHITE)
            _text(d, (700, y + 8), f"{int(count):,} msg", small, GOLD_RGB)
            y += 42

    _round(d, (924, 480, 1364, 668), PANEL)
    _text(d, (948, 500), "LEVEL", label, GOLD_RGB)
    _text(d, (948, 544), str(snap.get("level") or 0), _font(52, True), WHITE)
    into = int(snap.get("into") or 0)
    need = max(1, int(snap.get("need") or 1))
    _text(d, (948, 610), f"{into} / {need} XP", small, MUTED)
    bar_x, bar_y, bar_w = 948, 640, 380
    d.rounded_rectangle((bar_x, bar_y, bar_x + bar_w, bar_y + 14), radius=7, fill=PANEL2)
    fill_w = int(bar_w * min(1.0, into / need))
    if fill_w:
        d.rounded_rectangle((bar_x, bar_y, bar_x + fill_w, bar_y + 14), radius=7, fill=GOLD_RGB)

    _text(d, (36, 692), "\u2726 Aetherion", title, GOLD_RGB)
    started = snap.get("started") or "now"
    _text(d, (280, 704), f"Lifetime  \u00b7  tracked since {started}  \u00b7  this server", small, MUTED)

    out = io.BytesIO()
    img.save(out, format="PNG")
    out.seek(0)
    return out
