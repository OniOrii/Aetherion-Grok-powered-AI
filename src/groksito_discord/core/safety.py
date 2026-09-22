"""
Safe sending utilities for Discord messages.

Responsibilities:
- Enforce Discord's ~2000 character message limit via intelligent splitting.
- Prefer paragraph and code-block-aware breaks for natural continuations.
- Send follow-up parts as plain channel messages (no self-reply chain).

Intentionally dependency-light for use from both the conversational path
and from custom tools (image/video handlers, etc.).
"""

import logging
from typing import Any

from ..utils.message_utils import (
    DISCORD_SAFE_LENGTH,
    log_bot_utterance,
    send_split_messages,
)

logger = logging.getLogger("groksito.response_safety")


async def safe_reply(
    target_message: Any,
    content: str,
    mention_author: bool = False,
    max_length: int = DISCORD_SAFE_LENGTH,
) -> None:
    """
    Send a reply safely, splitting into multiple messages when necessary.

    Short responses use a single reply (unchanged behavior). Long responses are
    split intelligently and delivered as a chained reply thread.

    This function is the single source of truth for length-controlled
    sending in the Groksito conversational path.
    """
    if not content or not str(content).strip():
        return

    text = str(content).strip()

    try:
        await send_split_messages(
            target_message,
            text,
            mention_author=mention_author,
            max_length=max_length,
        )
    except Exception as send_err:
        logger.warning(f"[safe_reply] Failed to send reply: {send_err}")
        try:
            fallback = (
                "That reply was too long for Discord. "
                "Ask me to summarize it shorter."
            )
            await target_message.reply(fallback, mention_author=mention_author)
            log_bot_utterance(target_message, fallback)
        except Exception:
            pass
