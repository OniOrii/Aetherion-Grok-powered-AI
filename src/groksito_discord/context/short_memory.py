"""Last-10 conversation turns per user, shared by text chat and voice."""
from __future__ import annotations

import logging
import re
import time
from collections import defaultdict, deque
from typing import Any

logger = logging.getLogger("groksito.short_memory")

MAX_TURNS = 10
AETHERION_NAME_RE = re.compile(
    r"\b(aetherion|aetherian|atherion|atherian|atheerion|etherion|ethereon|"
    r"aetherium|aethereon|aetheron|atheron|groksito)\b",
    re.IGNORECASE,
)

_turns: dict[str, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=MAX_TURNS))


def _key(user_id: int | str | None) -> str:
    return str(user_id or "0")


def mentions_aetherion(text: str) -> bool:
    """True when the text addresses or talks about Aetherion by name."""
    return bool(AETHERION_NAME_RE.search(text or ""))


def record_turn(
    user_id: int | str | None,
    user_text: str,
    assistant_text: str,
    source: str = "text",
) -> None:
    uid = _key(user_id)
    user_text = (user_text or "").strip()[:400]
    assistant_text = (assistant_text or "").strip()[:400]
    if not user_text and not assistant_text:
        return
    _turns[uid].append(
        {
            "ts": time.time(),
            "source": source if source in ("text", "voice") else "text",
            "user": user_text,
            "aetherion": assistant_text,
        }
    )


def format_block(user_id: int | str | None) -> str:
    rows = list(_turns.get(_key(user_id), ()))
    if not rows:
        return ""
    lines = [
        "[Last conversations with this user — use only if needed to recall something]",
    ]
    for i, row in enumerate(rows, start=1):
        src = row.get("source") or "text"
        user = row.get("user") or ""
        bot = row.get("aetherion") or ""
        if user:
            lines.append(f"{i}. User ({src}): {user}")
        if bot:
            lines.append(f"   Aetherion: {bot}")
    lines.append("(Context only — do not paste this block in the reply.)")
    return "\n".join(lines)


def clear(user_id: int | str | None = None) -> None:
    """Test helper. Clear one user or every buffer."""
    if user_id is None:
        _turns.clear()
        return
    _turns.pop(_key(user_id), None)
