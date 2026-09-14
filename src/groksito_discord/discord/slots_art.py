"""Full-width cabinet portraits for /slots."""
from __future__ import annotations

import base64
import io
import logging
from importlib import import_module

from PIL import Image

logger = logging.getLogger("aetherion.slots_art")

_cache: dict[str, bytes] = {}
_MODULES = {
    "cosmos": ".cabinet_cosmos",
    "nebula": ".cabinet_nebula",
    "horizon": ".cabinet_horizon",
}


def _from_bundle(key: str) -> bytes | None:
    mod_name = _MODULES.get(key)
    if not mod_name:
        return None
    try:
        mod = import_module(mod_name, __package__)
        raw = base64.b64decode("".join(mod.DATA))
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        buf = io.BytesIO()
        im.save(buf, format="PNG", optimize=True)
        return buf.getvalue()
    except Exception:
        logger.exception("cabinet bundle failed key=%s", key)
        return None


def cabinet_png(machine_key: str) -> bytes:
    key = machine_key if machine_key in _MODULES else "cosmos"
    cached = _cache.get(key)
    if cached:
        return cached
    raw = _from_bundle(key)
    if not raw:
        raise RuntimeError(f"missing cabinet art for {key}")
    _cache[key] = raw
    return raw


def cabinet_jpeg(machine_key: str) -> bytes:
    return cabinet_png(machine_key)
