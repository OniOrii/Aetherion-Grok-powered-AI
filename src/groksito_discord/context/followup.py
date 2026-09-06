"""Last few user+bot lines so follow-up questions keep the topic."""
from __future__ import annotations

from .core import get_recent_channel_messages


def format_followup_block(channel_id: int, user_id: int, limit: int = 10) -> str:
    if not channel_id or not user_id:
        return ""
    hist = get_recent_channel_messages(channel_id, limit=40)
    relevant = [
        m for m in hist
        if m.get("is_bot") or int(m.get("author_id") or 0) == int(user_id)
    ][-limit:]
    if len(relevant) < 2:
        return ""
    lines = []
    for m in relevant:
        who = "Aetherion" if m.get("is_bot") else (m.get("author") or "User")
        content = (m.get("content") or "").strip()
        if content:
            lines.append(f"{who}: {content}")
    if len(lines) < 2:
        return ""
    return (
        "[Recent conversation with this user. Use it for follow-ups "
        "like that show or the rating. Do not paste this block.]\n"
        + "\n".join(lines)
    )
