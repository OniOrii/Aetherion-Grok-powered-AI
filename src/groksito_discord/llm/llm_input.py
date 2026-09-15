"""
LLM Input Builder for Groksito (Responses API).

Sent to the model on addressed turns (via ``build_responses_input``):
- Exactly one system message: the fixed ``SYSTEM_PROMPT`` (stable per-user cache prefix)
- User message, optionally prefixed with gated dynamic context:
  - Referenced / reply-chain [R:] blocks (direct replies or @mentions)
  - Compact per-guild emoji header (top-used emotes for current server)
- Multimodal vision blocks when images are attached

NOT sent automatically (by design — "let Grok be Grok"):
- Per-user memory / profile buffers (removed from ``context/core.py`` in #112)
- Channel history or rolling summaries (available only via ``get_recent_context`` tool)
- Proactive summarization output (disabled by default in config)

Light context classification (minimal/normal/image_gen) is used only for logging
and native tool gating — not for injecting stored memory.

This module is the single source of truth for ``initial_input`` sent to the API.
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from ..config import settings
from ..core.intent import (
    is_image_edit_request,
    is_pure_image_generation_request,
    is_pure_video_generation_request,
)
from ..utils.correlation import cid_prefix
from ..utils.text import filter_unreliable_vision_urls
from ..utils.token_usage import log_context_injection
from .prompt_builder import SYSTEM_PROMPT

logger = logging.getLogger("groksito.llm")


def _classify_query_context_need(text: str, is_reply_continuation: bool = False) -> str:
    """Minimal context-need shim for logging and native tool gating.

    Classification is now extremely light (post-#24). "need" is primarily for:
    - logging and metrics
    - gating native search offering (casual/image_gen get none)
    - pure_*_gen ultra-light paths
    The model decides almost everything via native reasoning + SYSTEM_PROMPT + tool schemas.
    We deliberately avoid reintroducing keyword-heavy tiers.
    """
    t = (text or "").strip()
    if not t:
        return "minimal"
    try:
        if is_pure_video_generation_request(t) or is_pure_image_generation_request(t):
            return "image_gen"
    except Exception:
        pass
    return "normal"


class ResponsesInputData(TypedDict):
    """Lightweight structural type for the return value of build_responses_input.

    This documents the shape without changing any runtime behavior.
    Used by the LLM orchestrator to unpack initial_input, classification need,
    and various context blocks for logging/caching decisions.
    """
    initial_input: list[dict]
    stable_prefix_len: int
    need: str
    user_id: str
    user_message_text: str
    dynamic_context_block: str
    emoji_full_block: str


def _build_multimodal_user_content(
    user_message: str,
    image_urls: list[str] | None,
    attachments: list[dict] | None = None,
) -> list[dict] | str:
    """Construct the user message content for the Responses API.

    Plain string when no images; otherwise multimodal input_text + input_image blocks.
    Vision URLs pass through filter_unreliable_vision_urls as a last-mile guard (#40).
    attachments param accepted (for signature parity with builder) but block injection
    handled in build_responses_input so that attachments always prepend early (before
    context_note) and work for both plain and multimodal cases.
    """
    if not image_urls:
        return user_message or ""

    safe_urls = filter_unreliable_vision_urls(image_urls)
    if not safe_urls:
        return user_message or ""

    content: list[dict] = []
    text = (user_message or "").strip()
    if is_image_edit_request(text, has_reference_image=True):
        text = (
            f"{text}\n\n"
            "[System note: The user attached a reference image and wants a visual transformation. "
            "You MUST call the edit_image tool with their instructions. Do not describe a finished "
            "edit in text alone — the tool delivers the edited image as an attachment.]"
        ).strip()
    content.append({"type": "input_text", "text": text})

    for url in safe_urls[:3]:
        content.append({
            "type": "input_image",
            "image_url": url,
            "detail": "high",
        })

    return content


_DO_NOT_REPEAT_NOTE = (
    "(Context only — do not repeat or paste the bracketed text in your reply.)"
)


def _is_bot_context(ctx: dict) -> bool:
    """True when referenced/chain context was authored by this bot."""
    if ctx.get("is_bot"):
        return True
    author = (ctx.get("author") or "").strip().lower()
    return author in ("groksito", "grok", "aetherion", "aetherion (ai)")


def _format_referenced_context_line(
    ref_summary: dict,
    *,
    is_reply_to_bot: bool,
) -> str:
    """Format the direct referenced message for model context."""
    ref_content = (ref_summary.get("content") or "").strip()[:500]
    if not ref_content:
        ref_content = "(embed / game board with no extra caption)"
    if is_reply_to_bot and _is_bot_context(ref_summary):
        return (
            "The user tapped Reply on my last Discord message. That message is the topic "
            "(Connect Four, blackjack, poker, slots, coin toss, an embed, or a chat reply). "
            "You already know what happened in it. Answer about that, do not treat the reply as a fresh challenge.\n"
            f"[My last message] {ref_content}\n"
            f"{_DO_NOT_REPEAT_NOTE}"
        )
    author = ref_summary.get("author", "?")
    return f"[R:{author}] {ref_content}"
