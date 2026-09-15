"""
LLM Input Builder for Groksito (Responses API).
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

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
    initial_input: list[dict]
    stable_prefix_len: int
    need: str
    user_id: str
    user_message_text: str
    dynamic_context_block: str
    emoji_full_block: str


_DO_NOT_REPEAT_NOTE = (
    "(Context only — do not repeat or paste the bracketed text in your reply.)"
)


def _is_bot_context(ctx: dict) -> bool:
    if ctx.get("is_bot"):
        return True
    author = (ctx.get("author") or "").strip().lower()
    return author in ("groksito", "grok", "aetherion", "aetherion (ai)")


def _format_referenced_context_line(ref_summary: dict, *, is_reply_to_bot: bool) -> str:
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


def _format_chain_ancestor_line(ctx: dict, index: int) -> str | None:
    content = (ctx.get("content") or "").strip()[:100]
    links = (ctx.get("external_links") or [])[:1]
    link_note = f" (link: {links[0]})" if links else ""
    if not (content or links):
        return None
    if _is_bot_context(ctx):
        return f"[My earlier message {index}] {content}"
    author = ctx.get("author", "?")
    return f"[Chain ancestor {index} by {author}]{link_note} {content}"


def _build_dynamic_referenced_context_block(
    *,
    referenced_context: dict | None,
    reply_chain_contexts: list[dict] | None,
    is_reply_to_bot: bool,
    is_mentioned: bool,
) -> str:
    if not (is_reply_to_bot or is_mentioned):
        return ""
    context_parts: list[str] = []
    if referenced_context:
        context_parts.append(
            _format_referenced_context_line(referenced_context, is_reply_to_bot=is_reply_to_bot)
        )
    if reply_chain_contexts:
        ancestor_lines = []
        for i, ctx in enumerate(reply_chain_contexts[1:3]):
            line = _format_chain_ancestor_line(ctx, i + 1)
            if line:
                ancestor_lines.append(line)
        if ancestor_lines:
            context_parts.append("\n".join(ancestor_lines))
    if not context_parts:
        return ""
    return "\n\n".join(context_parts)


def _build_emoji_block_if_addressed(
    *,
    original_message: Any,
    is_reply_to_bot: bool,
    is_mentioned: bool,
    image_gen_intent: bool = False,
) -> str:
    if not (is_reply_to_bot or is_mentioned) or image_gen_intent:
        return ""
    try:
        from ..utils import emoji_registry
        guild_obj = getattr(original_message, "guild", None) if original_message else None
        gid = getattr(guild_obj, "id", None) if guild_obj else None
        return emoji_registry.get_emoji_compact_header(gid, guild_obj=guild_obj) or ""
    except Exception:
        return ""


def _format_attachment_size(num_bytes: Any) -> str:
    try:
        b = int(num_bytes or 0)
    except Exception:
        b = 0
    if b <= 0:
        return ""
    if b >= 1024 * 1024:
        return f"{b / (1024 * 1024):.1f}MB"
    if b >= 1024:
        return f"{b / 1024:.1f}KB"
    return f"{b}B"


def _guess_fence_lang(filename: str, content_type: str) -> str:
    fn = (filename or "").lower()
    ct = (content_type or "").lower()
    if fn.endswith(".py") or "python" in ct:
        return "python"
    if fn.endswith(".js") or "javascript" in ct:
        return "javascript"
    if fn.endswith(".ts"):
        return "typescript"
    if fn.endswith(".json"):
        return "json"
    if fn.endswith((".md", ".markdown")):
        return "markdown"
    if fn.endswith((".yml", ".yaml")):
        return "yaml"
    if fn.endswith(".sh") or "shell" in ct or "bash" in ct:
        return "bash"
    if fn.endswith(".html") or "html" in ct:
        return "html"
    if fn.endswith(".css"):
        return "css"
    if fn.endswith(".log"):
        return "log"
    return ""


def _build_attachments_block(attachments: list[dict] | None) -> str:
    if not attachments:
        return ""
    lines: list[str] = ["[Attachments sent with this message:"]
    for a in attachments:
        if not isinstance(a, dict):
            continue
        filename = str(a.get("filename") or "unknown").strip() or "unknown"
        content_type = str(a.get("content_type") or "").strip()
        size_str = _format_attachment_size(a.get("size"))
        if content_type and size_str:
            meta = f"{content_type}, {size_str}"
        elif content_type:
            meta = content_type
        elif size_str:
            meta = size_str
        else:
            meta = ""
        line = f"- {filename} ({meta})" if meta else f"- {filename}"
        lines.append(line)
        tc = a.get("text_content")
        if isinstance(tc, str) and tc.strip():
            display = tc.strip()
            if len(display) > 2000:
                display = display[:2000] + "\n... [truncated for context]"
            lang = _guess_fence_lang(filename, content_type)
            lines.append(f"  ```{lang}\n{display}\n  ```")
    lines.append("]")
    return "\n".join(lines)


def _build_multimodal_user_content(
    user_message: str,
    image_urls: list[str] | None,
    attachments: list[dict] | None = None,
) -> list[dict] | str:
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
        content.append({"type": "input_image", "image_url": url, "detail": "high"})
    return content


async def build_responses_input(
    *,
    user_message: str,
    channel_id: int,
    original_message: Any,
    image_urls: list[str] | None,
    referenced_context: dict | None,
    reply_chain_contexts: list[dict] | None = None,
    is_reply_continuation: bool,
    has_x_link_intent: bool,
    image_gen_intent: bool = False,
    is_reply_to_bot: bool = False,
    is_mentioned: bool = False,
    attachments: list[dict] | None = None,
) -> dict[str, Any]:
    user_id = ""
    user_message_text = user_message or ""
    try:
        if original_message and getattr(original_message.author, "id", None):
            user_id = str(getattr(original_message.author, "id", ""))
    except Exception:
        pass

    need = "normal"
    try:
        need = _classify_query_context_need(user_message_text, is_reply_continuation=is_reply_continuation)
    except Exception:
        need = "normal"
    if (is_mentioned or is_reply_to_bot) and need not in ("image_gen",):
        need = "normal"
    elif is_reply_continuation and need in ("casual", "minimal"):
        need = "normal"

    dynamic_context_block = _build_dynamic_referenced_context_block(
        referenced_context=referenced_context,
        reply_chain_contexts=reply_chain_contexts,
        is_reply_to_bot=is_reply_to_bot,
        is_mentioned=is_mentioned,
    )
    if is_reply_to_bot:
        try:
            from ..context.followup import format_followup_block
            from ..context.short_memory import format_block as format_short_memory
            uid = int(user_id) if str(user_id).isdigit() else 0
            extra_parts = [
                format_followup_block(channel_id, uid, limit=8),
                format_short_memory(uid),
            ]
            extra = "\n\n".join(part for part in extra_parts if part)
            if extra:
                dynamic_context_block = (
                    f"{dynamic_context_block}\n\n{extra}".strip()
                    if dynamic_context_block
                    else extra
                )
        except Exception:
            logger.debug(f"{cid_prefix()}[LLM] reply follow-up context skipped", exc_info=True)

    emoji_full_block = _build_emoji_block_if_addressed(
        original_message=original_message,
        is_reply_to_bot=is_reply_to_bot,
        is_mentioned=is_mentioned,
        image_gen_intent=image_gen_intent,
    )
    attachments_block = _build_attachments_block(attachments) if attachments and not image_gen_intent else ""

    try:
        injected_chars = len(dynamic_context_block)
        log_context_injection(
            injected_tokens=max(30, injected_chars // 4),
            description=f"smart:{need}",
            has_memory=False,
            has_summary=False,
        )
    except Exception:
        pass

    user_content = _build_multimodal_user_content(user_message, image_urls, attachments=attachments)
    system_messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    context_prefix_parts: list[str] = []
    if attachments_block:
        context_prefix_parts.append(attachments_block)
    if dynamic_context_block:
        context_prefix_parts.append(dynamic_context_block)
    if emoji_full_block:
        context_prefix_parts.append(emoji_full_block)
    context_note = "\n\n".join(context_prefix_parts).strip()
    if context_note:
        if isinstance(user_content, list):
            if user_content and isinstance(user_content[0], dict) and user_content[0].get("type") == "input_text":
                orig = user_content[0].get("text") or ""
                user_content[0]["text"] = f"{context_note}\n\n{orig}".strip()
            else:
                user_content = [{"type": "input_text", "text": context_note}] + user_content
        else:
            user_content = f"{context_note}\n\n{user_content}".strip() if (user_content or "").strip() else context_note

    result: ResponsesInputData = {
        "initial_input": system_messages + [{"role": "user", "content": user_content}],
        "stable_prefix_len": len(SYSTEM_PROMPT),
        "need": need,
        "user_id": user_id,
        "user_message_text": user_message_text,
        "dynamic_context_block": dynamic_context_block,
        "emoji_full_block": emoji_full_block,
    }
    return result
