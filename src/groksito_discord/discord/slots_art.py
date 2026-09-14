"""Full-width cabinet portraits for /slots."""
from __future__ import annotations

import base64
import io
import logging
import math
from pathlib import Path
from random import Random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger("aetherion.slots_art")

_ASSET_DIR = Path(__file__).resolve().parent / "assets" / "slots"
_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
)
_THEMES = {
    "cosmos": {"bg": (8, 10, 22), "body": (12, 18, 42), "gold": (212, 175, 55), "deep": (6, 8, 18), "label": "COSMOS"},
    "nebula": {"bg": (16, 6, 28), "body": (42, 18, 64), "gold": (198, 150, 255), "deep": (12, 4, 22), "label": "NEBULA"},
    "horizon": {"bg": (8, 8, 8), "body": (18, 16, 14), "gold": (196, 154, 58), "deep": (4, 4, 4), "label": "HORIZON"},
}
_cache: dict[str, bytes] = {}


def _font(size: int):
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _payload(key: str) -> str:
    chunks = sorted(_ASSET_DIR.glob(f"{key}.*.b64"), key=lambda p: p.name)
    if not chunks:
        single = _ASSET_DIR / f"{key}.b64"
        if single.is_file():
            chunks = [single]
    return "".join(path.read_text(encoding="ascii").split() for path in chunks)


def _from_photo(key: str) -> bytes | None:
    payload = _payload(key)
    if not payload:
        return None
    try:
        raw = base64.b64decode(payload, validate=False)
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        im.verify()
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        if min(im.size) < 200:
            return None
        buf = io.BytesIO()
        im.save(buf, format="PNG", optimize=True)
        return buf.getvalue()
    except Exception:
        logger.warning("photo cabinet unusable key=%s", key)
        return None


def _paint(key: str) -> bytes:
    t = _THEMES.get(key) or _THEMES["cosmos"]
    w, h = 900, 600
    img = Image.new("RGB", (w, h), t["bg"])
    d = ImageDraw.Draw(img)
    rng = Random(hash(key) & 0xFFFF)
    for _ in range(160):
        x, y = rng.randint(0, w - 1), rng.randint(0, h - 1)
        c = rng.randint(120, 220)
        d.point((x, y), fill=(c, c - 10, min(255, c + 20)))
    d.rounded_rectangle((70, 70, w - 70, h - 70), radius=28, fill=t["body"], outline=t["gold"], width=8)
    d.rounded_rectangle((82, 82, w - 82, h - 82), radius=22, outline=t["gold"], width=2)
    d.ellipse((w // 2 - 26, 36, w // 2 + 26, 88), fill=t["gold"])
    d.ellipse((w // 2 - 14, 48, w // 2 + 14, 76), fill=(255, 230, 160))
    d.rounded_rectangle((w // 2 - 200, 100, w // 2 + 200, 158), radius=10, fill=t["deep"], outline=t["gold"], width=3)
    d.text((w // 2, 129), t["label"], font=_font(32), fill=t["gold"], anchor="mm")
    ww, wh, gap = 175, 210, 24
    total = 3 * ww + 2 * gap
    x0 = (w - total) // 2
    y0 = 190
    for i in range(3):
        x = x0 + i * (ww + gap)
        d.rounded_rectangle((x, y0, x + ww, y0 + wh), radius=14, fill=t["deep"], outline=t["gold"], width=5)
    d.rounded_rectangle((w // 2 + 80, 430, w - 120, 500), radius=10, fill=t["deep"], outline=t["gold"], width=3)
    d.text((w // 2 + 198, 465), "SPIN", font=_font(28), fill=t["gold"], anchor="mm")
    img = img.filter(ImageFilter.SMOOTH)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def cabinet_png(machine_key: str) -> bytes:
    key = machine_key if machine_key in _THEMES else "cosmos"
    cached = _cache.get(key)
    if cached:
        return cached
    raw = _from_photo(key) or _paint(key)
    _cache[key] = raw
    return raw


def cabinet_jpeg(machine_key: str) -> bytes:
    return cabinet_png(machine_key)
