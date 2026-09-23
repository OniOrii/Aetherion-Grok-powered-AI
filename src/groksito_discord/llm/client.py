"""LLM / Responses API layer for Groksito (standalone)."""
from __future__ import annotations
import json
import logging
import os
import time
from typing import Any, Optional
from ..utils.correlation import cid_prefix
from ..utils.errors import format_tool_execution_error, is_image_fetch_404_error
from openai import AsyncOpenAI, RateLimitError, APITimeoutError, APIConnectionError, APIError
from ..config import settings
from ..media.delivery import DIRECT_DELIVERY_PERFORMED
from .prompt_builder import DIRECT_DELIVERY_DETECTOR_PHRASES
from .tools import ASSET_RESOLVER_TOOLS, get_tools_for_request, log_tool_selection, execute_hybrid_tool
from .media_tools import has_explicit_video_intent, has_explicit_audio_intent
from .llm_input import build_responses_input
from ..context import should_offer_light_decision_tools
from .llm_utils import (
    _extract_final_text, _build_stub_response, _get_prompt_cache_key, _build_native_search_tools,
    _detect_visual_intent, _detect_image_creation_intent, is_image_edit_request, _infer_tools_set_name,
    _extract_and_log_token_usage, _maybe_proactive_summarize, is_pure_image_generation_request,
    is_pure_video_generation_request, _call_responses_with_retry,
)
try:
    from ..config import settings as _settings
except Exception:
    _settings = None  # type: ignore
try:
    from ..core.grok_oauth import get_grok_bearer as _get_grok_bearer
except Exception:
    _get_grok_bearer = None  # type: ignore
logger = logging.getLogger("groksito.llm")
MEDIA_ACTION_TOOLS = frozenset({"generate_image", "edit_image", "generate_video", "generate_audio", "reply_to_user"})
_MEDIA_DELIVERY_TOOLS = frozenset({"generate_image", "edit_image", "generate_video", "generate_audio"})
_CONTINUATION_NO_SEARCH_REOFFER_TOOLS = frozenset({"respond_directly", *MEDIA_ACTION_TOOLS})
_DIRECT_DELIVERY_SUCCESS_PHRASES = DIRECT_DELIVERY_DETECTOR_PHRASES

def _is_direct_delivery_success(result_str: str, tool_name: str, cid_p: str) -> bool:
    lowered = result_str.lower()
    if any(phrase in lowered for phrase in _DIRECT_DELIVERY_SUCCESS_PHRASES):
        logger.info(f"{cid_p}[LLM] Direct delivery SUCCESS for tool '{tool_name}' — suppressing final text reply")
        return True
    if "policy blocked" in lowered and "clean direct message delivered" in lowered:
        return True
    return False

def _finalize_response(response: Any, direct_delivery_performed: bool, cid_p: str) -> str | object:
    final_text = _extract_final_text(response)
    if direct_delivery_performed:
        logger.info(f"{cid_p}[LLM] Direct media/action delivery performed — returning DIRECT_DELIVERY_PERFORMED sentinel (no second reply)")
        return DIRECT_DELIVERY_PERFORMED
    if final_text:
        return final_text.strip()
    return "✅ Aetherion processed your message using tools (via the Responses API)."

def _should_offer_light_decision(user_message_text: str, user_message: str, *, is_mentioned: bool, is_reply_to_bot: bool, context_need: str) -> bool:
    try:
        return should_offer_light_decision_tools(is_mentioned=is_mentioned, is_reply_to_bot=is_reply_to_bot, context_need=context_need, user_message=user_message_text or user_message)
    except Exception:
        return False

def _should_reoffer_native_search_on_continuation(prev_response: Any, *, native_search_tools: list[dict], executed_tool_names: set[str]) -> bool:
    if not native_search_tools:
        return False
    if executed_tool_names & _CONTINUATION_NO_SEARCH_REOFFER_TOOLS:
        return False
    try:
        prev_output = getattr(prev_response, "output", None) or []
        for item in prev_output:
            itype = getattr(item, "type", None)
            if isinstance(item, dict):
                itype = item.get("type")
            itype_str = str(itype or "").lower()
            if itype_str == "function_call":
                name = getattr(item, "name", None)
                if name is None and isinstance(item, dict):
                    name = item.get("name")
                if name in ("web_search", "x_search"):
                    return True
            if itype_str and ("web_search" in itype_str or "x_search" in itype_str or "search_call" in itype_str):
                return True
    except Exception:
        pass
    return False

async def _prepare_first_turn_data(*, user_message: str, channel_id: int, original_message: Any, image_urls: list[str] | None, attachments: list[dict] | None = None, referenced_context: dict | None, reply_chain_contexts: list[dict] | None, is_reply_continuation: bool, has_x_link_intent: bool, is_reply_to_bot: bool, is_mentioned: bool) -> dict[str, Any]:
    pure_video_gen_intent = False
    pure_image_gen_intent = False
    try:
        if is_pure_video_generation_request(user_message) and not bool(image_urls) and not is_reply_continuation:
            pure_video_gen_intent = True
        elif is_pure_image_generation_request(user_message) and not bool(image_urls) and not is_reply_continuation:
            pure_image_gen_intent = True
    except Exception:
        pure_video_gen_intent = False
        pure_image_gen_intent = False
    input_data = await build_responses_input(user_message=user_message, channel_id=channel_id, original_message=original_message, image_urls=image_urls, attachments=attachments, referenced_context=referenced_context, reply_chain_contexts=reply_chain_contexts, is_reply_continuation=is_reply_continuation, has_x_link_intent=has_x_link_intent, image_gen_intent=pure_image_gen_intent or pure_video_gen_intent, is_reply_to_bot=is_reply_to_bot, is_mentioned=is_mentioned)
    return {"input_data": input_data, "pure_video_gen_intent": pure_video_gen_intent, "pure_image_gen_intent": pure_image_gen_intent}

def _select_tools_for_first_turn(*, user_message_text: str, user_message: str, need: str, image_urls: list[str] | None, has_visual_intent: bool, is_mentioned: bool, is_reply_to_bot: bool, is_addressed: bool, pure_image_gen_intent: bool, pure_video_gen_intent: bool) -> dict[str, Any]:
    explicit_video_intent = has_explicit_video_intent(user_message_text)
    explicit_audio_intent = has_explicit_audio_intent(user_message_text)
    creation_visual_intent = (has_visual_intent or _detect_image_creation_intent(user_message_text, has_reference_image=bool(image_urls)) or (bool(image_urls) and is_image_edit_request(user_message_text, has_reference_image=True)))
    vision_or_visual_query = (bool(image_urls) or _detect_visual_intent(user_message_text) or creation_visual_intent or explicit_video_intent)
    effective_visual_intent = creation_visual_intent
    offer_light_decision_tools = _should_offer_light_decision(user_message_text, user_message, is_mentioned=is_mentioned, is_reply_to_bot=is_reply_to_bot, context_need=need)
    custom_tools = get_tools_for_request(query_need=need, has_visual_intent=effective_visual_intent, has_explicit_video_intent=explicit_video_intent, has_explicit_audio_intent=explicit_audio_intent, is_tool_continuation=False, pure_image_gen=pure_image_gen_intent, pure_video_gen=pure_video_gen_intent, offer_light_decision_tools=offer_light_decision_tools)
    if need in ("casual", "image_gen") or (need == "minimal" and not is_addressed):
        native_search_tools: list[dict] = []
    else:
        native_search_tools = _build_native_search_tools(query_text=user_message_text, context_need=need, has_visual_intent=vision_or_visual_query, has_attached_images=bool(image_urls))
    return {"custom_tools": custom_tools, "native_search_tools": native_search_tools, "effective_visual_intent": effective_visual_intent, "explicit_video_intent": explicit_video_intent, "explicit_audio_intent": explicit_audio_intent, "offer_light_decision_tools": offer_light_decision_tools}
