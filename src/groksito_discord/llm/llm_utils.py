"""
LLM Utility Helpers for Groksito.

Pure helpers and side-effect functions supporting the LLM layer.
Called by llm.py (orchestrator) and llm_input.py.

Input construction logic lives exclusively in llm_input.py.
"""

from __future__ import annotations

import asyncio
import logging
import random
import unicodedata
from typing import Any

from ..utils.correlation import cid_prefix

from openai import (
    AsyncOpenAI,
    RateLimitError,
    APIError,
    APITimeoutError,
    APIConnectionError,
)

from ..config import settings
from .prompt_builder import (
    SUMMARIZATION_PROMPT,
    get_native_search_descriptions,
    infer_custom_tools_set_name,
)
from ..context import (
    get_estimated_history_tokens,
    get_messages_for_summarization,
    update_channel_summary,
    is_pure_image_generation_request,
)
from ..utils.token_usage import (
    log_usage,
    log_cache_metrics,
)

# Centralized light intent detectors (post #24 cleanup of heavy versions).
# Re-exported here for backward compat with any remaining imports in
# llm.py / conversation.py / call sites. Light non-brittle implementations
# live in intents.py.
from ..core.intent import (
    _detect_visual_intent,
    _detect_image_creation_intent,
    is_image_edit_request,
    is_pure_video_generation_request,
)

logger = logging.getLogger("groksito.llm")


def _extract_final_text(response: Any) -> str | None:
    """Extract the final assistant text from a Responses API response."""
    if response is None:
        return None

    if hasattr(response, "output_text") and response.output_text:
        return str(response.output_text)

    output = getattr(response, "output", None) or []
    for item in output:
        if getattr(item, "type", None) == "message":
            content = getattr(item, "content", None) or []
            for c in content:
                if getattr(c, "type", None) == "text":
                    txt = getattr(c, "text", None)
                    if txt:
                        return str(txt)
                if hasattr(c, "text") and getattr(c, "text"):
                    return str(getattr(c, "text"))

        if isinstance(item, dict) and item.get("type") == "message":
            for c in item.get("content", []) or []:
                if isinstance(c, dict) and c.get("type") == "text":
                    if c.get("text"):
                        return str(c.get("text"))
                if isinstance(c, dict) and c.get("text"):
                    return str(c.get("text"))

    try:
        if output:
            last = output[-1]
            if hasattr(last, "text") and last.text:
                return str(last.text)
            if isinstance(last, dict) and last.get("text"):
                return str(last.get("text"))
    except Exception:
        pass

    return None


def _build_stub_response(
    user_message: str, author_name: str, image_urls: list[str] | None
) -> str:
    """Fallback when no API key or during early development."""
    vision_note = f"\n[Images: {len(image_urls or [])}]" if image_urls else ""
    return (
        f"\u2705 Aetherion received your message (no API key / development mode).\n\n"
        f"User: {author_name}\n"
        f"Message: {(user_message or '')[:300]}{vision_note}"
    )


def _get_prompt_cache_key(original_message: Any) -> str:
    """
    Returns a stable per-user prompt_cache_key for xAI Prompt Caching.
    (Exact original implementation preserved.)
    """
    try:
        author = getattr(original_message, "author", None)
        user_id = getattr(author, "id", None) if author else None
        if user_id:
            return f"groksito-user-{user_id}"
    except Exception:
        pass
    return "groksito-default-user"


def _build_native_search_tools(
    query_text: str,
    context_need: str,
    has_visual_intent: bool,
    has_attached_images: bool,
) -> list[dict]:
    """Build native xAI web_search + x_search tool schemas for addressed turns.

    Skips ultra-light paths (casual/minimal/image_gen and pure image gen without
    attachments). Otherwise offers both tools; Grok decides when to call them.
    """
    if context_need in ("casual", "minimal", "image_gen"):
        return []

    try:
        if is_pure_image_generation_request(query_text) and not has_attached_images:
            return []
    except Exception:
        pass

    # Descriptions come exclusively from prompt_builder.get_native_search_descriptions
    # (single source of truth with SYSTEM_PROMPT completeness guidance).
    web_desc, x_desc = get_native_search_descriptions(query_text)

    web_tool: dict = {
        "type": "web_search",
        "description": web_desc,
    }

    x_tool: dict = {
        "type": "x_search",
        "description": x_desc,
    }

    if has_visual_intent or has_attached_images or _detect_visual_intent(query_text):
        web_tool["enable_image_search"] = True
        web_tool["enable_image_understanding"] = True

    return [web_tool, x_tool]


def _infer_tools_set_name(
    query_need: str, has_visual_intent: bool, is_continuation: bool
) -> str:
    """Produces a short, consistent label for the custom tool set used (for logging)."""
    return infer_custom_tools_set_name(query_need, has_visual_intent, is_continuation)


def _extract_and_log_token_usage(
    response: Any,
    model: str,
    has_images: bool = False,
    category: str = "Conversation",
    is_tool_continuation: bool = False,
    cache_context: dict | None = None,
) -> None:
    """
    Safely extracts usage information from a Responses API response and logs it.
    (Exact original implementation preserved, including all fallback paths.)
    """
    try:
        usage = getattr(response, "usage", None)
        if usage is None and isinstance(response, dict):
            usage = response.get("usage")

        if not usage:
            logger.debug(
                f"{cid_prefix()}[TOKENS] No usage object found on response for category={category}"
            )
            return

        prompt = 0
        completion = 0
        total = 0

        if hasattr(usage, "input_tokens"):
            prompt = getattr(usage, "input_tokens", 0) or 0
            completion = getattr(usage, "output_tokens", 0) or 0
            total = getattr(usage, "total_tokens", prompt + completion) or 0
        elif isinstance(usage, dict) and "input_tokens" in usage:
            prompt = usage.get("input_tokens", 0)
            completion = usage.get("output_tokens", 0)
            total = usage.get("total_tokens", prompt + completion)

        if (prompt == 0 and completion == 0) and hasattr(usage, "prompt_tokens"):
            prompt = getattr(usage, "prompt_tokens", 0) or 0
            completion = getattr(usage, "completion_tokens", 0) or 0
            total = getattr(usage, "total_tokens", prompt + completion) or 0
        elif (prompt == 0 and completion == 0) and isinstance(usage, dict):
            prompt = usage.get("prompt_tokens", 0)
            completion = usage.get("completion_tokens", 0)
            total = usage.get("total_tokens", prompt + completion)

        if prompt == 0 and completion == 0:
            logger.debug(
                f"{cid_prefix()}[TOKENS] Usage object found but no token numbers for category={category}"
            )
            return

        cached = 0
        try:
            if hasattr(usage, "input_tokens_details"):
                details = getattr(usage, "input_tokens_details", None)
                if details:
                    cached = getattr(details, "cached_tokens", 0) or 0
            elif isinstance(usage, dict):
                details = usage.get("input_tokens_details", {})
                if isinstance(details, dict):
                    cached = details.get("cached_tokens", 0)

            if not cached:
                if hasattr(usage, "prompt_tokens_details"):
                    pdetails = getattr(usage, "prompt_tokens_details", None)
                    if pdetails:
                        cached = getattr(pdetails, "cached_tokens", 0) or 0
                elif isinstance(usage, dict):
                    pdetails = usage.get("prompt_tokens_details", {})
                    if isinstance(pdetails, dict):
                        cached = pdetails.get("cached_tokens", 0) or cached

            if cached and prompt > 0:
                cached = min(cached, prompt)
            if cached < 0:
                cached = 0
        except Exception:
            pass

        log_usage(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
            model=model,
            category=category,
            has_images=has_images,
            tool_round=is_tool_continuation,
            cached_tokens=cached,
        )

        if cache_context:
            try:
                log_cache_metrics(
                    prompt_tokens=prompt,
                    completion_tokens=completion,
                    total_tokens=total,
                    cached_tokens=cached,
                    **cache_context,
                )
            except Exception as cache_log_err:
                logger.debug(
                    f"{cid_prefix()}[CACHE] metrics logging failed: {cache_log_err}"
                )

        if cached == 128 and prompt < 300:
            logger.debug(
                f"{cid_prefix()}[TOKENS] cached=128 (normal min-block granularity for light prefix) prompt={prompt} cat={category}"
            )

    except Exception as err:
        logger.warning(
            f"{cid_prefix()}[TOKENS] Exception while extracting usage: {err}"
        )


async def _call_responses_with_retry(client: AsyncOpenAI, **kwargs) -> Any:
    """
    Call client.responses.create with improved resilience for transient errors only.

    Retries (with exp backoff + jitter):
      - RateLimitError (429)
      - APITimeoutError / APIConnectionError (network)
      - APIError with 5xx status (server errors)
    Fail fast (no retry): auth (401/403), bad requests (4xx non-429), policy/422 content errors, client errors.
    """
    max_attempts = getattr(settings, "api_max_retries", 3)
    base_delay = getattr(settings, "api_retry_base_delay_seconds", 0.5)
    max_delay = 8.0

    for attempt in range(1, max_attempts + 1):
        try:
            return await client.responses.create(**kwargs)
        except (RateLimitError, APITimeoutError, APIConnectionError) as e:
            if attempt == max_attempts:
                logger.warning(
                    f"{cid_prefix()}[LLM][RETRY] Transient error after {max_attempts} attempts: {type(e).__name__} (exhausted)"
                )
                raise
            raw_delay = base_delay * (2 ** (attempt - 1))
            delay = min(max_delay, random.uniform(0, raw_delay))
            logger.info(
                f"{cid_prefix()}[LLM][RETRY] Transient ({type(e).__name__}) on responses.create "
                f"attempt {attempt}/{max_attempts} — retry in {delay:.2f}s (jittered)"
            )
            await asyncio.sleep(delay)
            continue
        except APIError as e:
            status = getattr(e, "status_code", None)
            is_server_error = status and 500 <= status < 600
            is_rate = status == 429
            if (is_server_error or is_rate) and attempt < max_attempts:
                raw_delay = base_delay * (2 ** (attempt - 1))
                delay = min(max_delay, random.uniform(0, raw_delay))
                logger.info(
                    f"{cid_prefix()}[LLM][RETRY] Server/rate error {status} on responses.create "
                    f"attempt {attempt}/{max_attempts} — retry in {delay:.2f}s"
                )
                await asyncio.sleep(delay)
                continue
            raise
        except Exception:
            raise


async def _maybe_proactive_summarize(
    channel_id: int,
    original_message: Any,
    client: AsyncOpenAI,
) -> None:
    """
    (Optional) Proactive summarization of older channel history.
    Disabled by default for maximum Grok nativeness.
    """
    try:
        if not getattr(settings, "summarization_enabled", False):
            return

        threshold = int(getattr(settings, "summarization_threshold_tokens", 6000))
        keep_recent = 6

        estimated_tokens = get_estimated_history_tokens(channel_id)

        if estimated_tokens < threshold:
            return

        older_messages = get_messages_for_summarization(
            channel_id, keep_recent=keep_recent
        )
        if not older_messages or len(older_messages) < 5:
            return

        conversation_text = "\n".join(
            f"[{m.get('author', '?')}]: {m.get('content', '')[:400]}"
            for m in older_messages
        )

        summary_model = getattr(settings, "grok_model", None) or "grok-4.3"
        summary_response = await _call_responses_with_retry(
            client,
            model=summary_model,
            input=[
                {
                    "role": "system",
                    "content": SUMMARIZATION_PROMPT.format(
                        conversation_text=conversation_text
                    ),
                },
                {
                    "role": "user",
                    "content": "Summarize the older messages concisely and usefully.",
                },
            ],
        )

        summary_text = _extract_final_text(summary_response) or ""
        if not summary_text or len(summary_text) < 30:
            return

        if (
            "sin informaci" in summary_text.lower()
            or "sin contenido" in summary_text.lower()
            or "no information" in summary_text.lower()
        ):
            return

        update_channel_summary(channel_id, summary_text)

        summarized_tokens = sum(len(m.get("content", "")) for m in older_messages) // 4
        new_summary_tokens = len(summary_text) // 4

        logger.info(
            f"{cid_prefix()}[CONTEXT] Proactive conversation summarization for channel {channel_id}: "
            f"old~{summarized_tokens}t → summary~{new_summary_tokens}t "
            f"(kept last {keep_recent}). Savings ~{max(0, summarized_tokens - new_summary_tokens)}t. "
            "Older history compacted automatically."
        )

    except Exception as e:
        logger.warning(
            f"{cid_prefix()}[CONTEXT] Proactive summarization failed for channel {channel_id}: {e}"
        )
