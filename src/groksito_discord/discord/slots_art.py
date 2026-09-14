"""Load per-machine cabinet portraits for the /slots thumbnail."""
from __future__ import annotations

import base64
from pathlib import Path

_DIR = Path(__file__).resolve().parent / "assets" / "slots"


def cabinet_jpeg(machine_key: str) -> bytes | None:
    for key in (machine_key, "cosmos", "nebula", "horizon"):
        path = _DIR / f"{key}.b64"
        if not path.is_file():
            continue
        raw = path.read_text().strip()
        if not raw:
            continue
        try:
            return base64.b64decode(raw)
        except Exception:
            continue
    return None
