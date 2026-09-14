"""Full-width cabinet portraits for /slots."""
from __future__ import annotations

import base64
import io
import logging
from pathlib import Path

from PIL import Image

logger = logging.getLogger("aetherion.slots_art")

_ASSET_DIR = Path(__file__).resolve().parent / "assets" / "slots"
_KEYS = ("cosmos", "nebula", "horizon")
_cache: dict[str, bytes] = {}


def _decode_asset(key: str) -> bytes | None:
    path = _ASSET_DIR / f"{key}.b64"
    if not path.is_file():
        logger.warning("cabinet asset missing %s", path)
        return None
    try:
        payload = "".join(path.read_text(encoding="ascii").split())
        raw = base64.b64decode(payload, validate=False)
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        buf = io.BytesIO()
        im.save(buf, format="PNG", optimize=True)
        return buf.getvalue()
    except Exception:
        logger.exception("cabinet asset failed key=%s", key)
        return None


def cabinet_png(machine_key: str) -> bytes:
    key = machine_key if machine_key in _KEYS else "cosmos"
    cached = _cache.get(key)
    if cached:
        return cached
    raw = _decode_asset(key)
    if raw is None and key != "cosmos":
        raw = _decode_asset("cosmos")
    if raw is None:
        raise RuntimeError(f"missing cabinet art for {key}")
    _cache[key] = raw
    return raw


def cabinet_jpeg(machine_key: str) -> bytes:
    return cabinet_png(machine_key)
