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


def _payload(key: str) -> str:
    chunks = sorted(_ASSET_DIR.glob(f"{key}.*.b64"), key=lambda p: p.name)
    if not chunks:
        single = _ASSET_DIR / f"{key}.b64"
        if single.is_file():
            chunks = [single]
    return "".join(path.read_text(encoding="ascii").split() for path in chunks)


def _decode_asset(key: str) -> bytes | None:
    payload = _payload(key)
    if not payload:
        logger.warning("cabinet asset missing key=%s", key)
        return None
    try:
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
