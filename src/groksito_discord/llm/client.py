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
        logger.info(f"{cid_p}[LLM] Direct delivery SUCCESS for tool '{tool_name}'")
        return True
    return "policy blocked" in lowered and "clean direct message delivered" in lowered

def _finalize_response(response: Any, direct_delivery_performed: bool, cid_p: str):
    final_text = _extract_final_text(response)
    if direct_delivery_performed:
        return DIRECT_DELIVERY_PERFORMED
    if final_text:
        return final_text.strip()
    return "\u2705 Aetherion processed your message using tools (via the Responses API)."

def _should_offer_light_decision(user_message_text, user_message, *, is_mentioned, is_reply_to_bot, context_need):
    try:
        return should_offer_light_decision_tools(is_mentioned=is_mentioned, is_reply_to_bot=is_reply_to_bot, context_need=context_need, user_message=user_message_text or user_message)
    except Exception:
        return False

def _should_reoffer_native_search_on_continuation(prev_response, *, native_search_tools, executed_tool_names):
    if not native_search_tools or executed_tool_names & _CONTINUATION_NO_SEARCH_REOFFER_TOOLS:
        return False
    try:
        for item in getattr(prev_response, "output", None) or []:
            itype = item.get("type") if isinstance(item, dict) else getattr(item, "type", None)
            itype_str = str(itype or "").lower()
            name = item.get("name") if isinstance(item, dict) else getattr(item, "name", None)
            if itype_str == "function_call" and name in ("web_search", "x_search"):
                return True
            if itype_str and ("web_search" in itype_str or "x_search" in itype_str or "search_call" in itype_str):
                return True
    except Exception:
        pass
    return False

async def _prepare_first_turn_data(*, user_message, channel_id, original_message, image_urls, attachments=None, referenced_context=None, reply_chain_contexts=None, is_reply_continuation=False, has_x_link_intent=False, is_reply_to_bot=False, is_mentioned=False):
    pure_video_gen_intent = False
    pure_image_gen_intent = False
    try:
        if is_pure_video_generation_request(user_message) and not image_urls and not is_reply_continuation:
            pure_video_gen_intent = True
        elif is_pure_image_generation_request(user_message) and not image_urls and not is_reply_continuation:
            pure_image_gen_intent = True
    except Exception:
        pass
    input_data = await build_responses_input(user_message=user_message, channel_id=channel_id, original_message=original_message, image_urls=image_urls, attachments=attachments, referenced_context=referenced_context, reply_chain_contexts=reply_chain_contexts, is_reply_continuation=is_reply_continuation, has_x_link_intent=has_x_link_intent, image_gen_intent=pure_image_gen_intent or pure_video_gen_intent, is_reply_to_bot=is_reply_to_bot, is_mentioned=is_mentioned)
    return {"input_data": input_data, "pure_video_gen_intent": pure_video_gen_intent, "pure_image_gen_intent": pure_image_gen_intent}

def _select_tools_for_first_turn(*, user_message_text, user_message, need, image_urls, has_visual_intent, is_mentioned, is_reply_to_bot, is_addressed, pure_image_gen_intent, pure_video_gen_intent):
    explicit_video_intent = has_explicit_video_intent(user_message_text)
    explicit_audio_intent = has_explicit_audio_intent(user_message_text)
    creation_visual_intent = has_visual_intent or _detect_image_creation_intent(user_message_text, has_reference_image=bool(image_urls)) or (bool(image_urls) and is_image_edit_request(user_message_text, has_reference_image=True))
    vision_or_visual_query = bool(image_urls) or _detect_visual_intent(user_message_text) or creation_visual_intent or explicit_video_intent
    offer_light_decision_tools = _should_offer_light_decision(user_message_text, user_message, is_mentioned=is_mentioned, is_reply_to_bot=is_reply_to_bot, context_need=need)
    custom_tools = get_tools_for_request(query_need=need, has_visual_intent=creation_visual_intent, has_explicit_video_intent=explicit_video_intent, has_explicit_audio_intent=explicit_audio_intent, is_tool_continuation=False, pure_image_gen=pure_image_gen_intent, pure_video_gen=pure_video_gen_intent, offer_light_decision_tools=offer_light_decision_tools)
    native_search_tools = [] if need in ("casual", "image_gen") or (need == "minimal" and not is_addressed) else _build_native_search_tools(query_text=user_message_text, context_need=need, has_visual_intent=vision_or_visual_query, has_attached_images=bool(image_urls))
    return {"custom_tools": custom_tools, "native_search_tools": native_search_tools, "effective_visual_intent": creation_visual_intent, "explicit_video_intent": explicit_video_intent, "explicit_audio_intent": explicit_audio_intent, "offer_light_decision_tools": offer_light_decision_tools}

async def _execute_tool_loop(*, client, model, response, need, user_id, stable_prefix_len, effective_visual_intent, explicit_video_intent, explicit_audio_intent, pure_image_gen_intent, pure_video_gen_intent, native_search_tools, offered_custom_tool_names, original_message, image_urls, is_addressed, cid_p, max_tool_rounds=3):
    direct_delivery_performed = False
    model_chose_search = False
    model_chose_direct = False
    asset_references_resolved = False
    media_delivered = False
    continuation_tools = []
    for round_num in range(1, max_tool_rounds + 1):
        client_tool_outputs = []
        round_executed_tools = set()
        for item in getattr(response, "output", None) or []:
            if getattr(item, "type", None) != "function_call":
                continue
            name = getattr(item, "name", None) or (item.get("name") if isinstance(item, dict) else None)
            if name in ("web_search", "x_search"):
                model_chose_search = True
            if name == "respond_directly":
                model_chose_direct = True
            raw_args = getattr(item, "arguments", None)
            if raw_args is None and isinstance(item, dict):
                raw_args = item.get("arguments", {})
            if isinstance(raw_args, str):
                try:
                    raw_args = json.loads(raw_args)
                except Exception:
                    raw_args = {}
            call_id = getattr(item, "call_id", None) or getattr(item, "id", None)
            if call_id is None and isinstance(item, dict):
                call_id = item.get("call_id") or item.get("id")
            try:
                result = await execute_hybrid_tool(name=name or "unknown_tool", args=raw_args if isinstance(raw_args, dict) else {}, original_message=original_message, image_urls=image_urls)
            except Exception as tool_exec_err:
                result = format_tool_execution_error(name or "unknown_tool", tool_exec_err, round_num=round_num, arg_keys=list((raw_args or {}).keys()) if isinstance(raw_args, dict) else None)
                logger.error(f"{cid_p}[TOOLS] {result}", exc_info=True)
            if name:
                round_executed_tools.add(name)
            result_str = str(result)
            if name in ASSET_RESOLVER_TOOLS and "RESOLVED" in result_str.upper():
                asset_references_resolved = True
            if name in MEDIA_ACTION_TOOLS and _is_direct_delivery_success(result_str, name or "", cid_p):
                direct_delivery_performed = True
                if name in _MEDIA_DELIVERY_TOOLS:
                    media_delivered = True
            client_tool_outputs.append({"type": "function_call_output", "call_id": call_id, "output": result_str[:4000]})
        if not client_tool_outputs:
            break
        if direct_delivery_performed:
            premature = asset_references_resolved and not media_delivered and bool(round_executed_tools & {"reply_to_user"}) and not (round_executed_tools & _MEDIA_DELIVERY_TOOLS)
            if premature:
                direct_delivery_performed = False
            else:
                break
        try:
            prev_id = getattr(response, "id", None)
            cache_key = _get_prompt_cache_key(original_message)
            has_resolved = asset_references_resolved and bool(image_urls)
            pending_media = has_resolved and (explicit_video_intent or effective_visual_intent) and not media_delivered
            continuation_tools = get_tools_for_request(query_need=need, has_visual_intent=effective_visual_intent, has_explicit_video_intent=explicit_video_intent, has_explicit_audio_intent=explicit_audio_intent, is_tool_continuation=True, pure_image_gen=pure_image_gen_intent, pure_video_gen=pure_video_gen_intent, has_resolved_asset_references=has_resolved, pending_media_after_asset=pending_media)
            continuation_native = native_search_tools if _should_reoffer_native_search_on_continuation(response, native_search_tools=native_search_tools, executed_tool_names=round_executed_tools) else []
            offered_custom_tool_names = {t.get("name") for t in continuation_tools if t.get("name")}
            response = await _call_responses_with_retry(client, model=model, input=client_tool_outputs, previous_response_id=prev_id, tools=[*continuation_native, *continuation_tools], extra_body={"prompt_cache_key": cache_key})
        except Exception as continue_err:
            logger.warning(f"{cid_p}[LLM] Continuation failed: {continue_err}")
            break
        _extract_and_log_token_usage(response, model=model, has_images=bool(image_urls), category="Tool", is_tool_continuation=True, cache_context={"turn_type": "continuation", "query_need": need, "has_visual_intent": effective_visual_intent, "custom_tools_count": len(continuation_tools), "custom_tools_set": _infer_tools_set_name(need, effective_visual_intent, True), "user_id": user_id, "prefix_stability_indicator": f"sys~{stable_prefix_len}"})
    return response, direct_delivery_performed, model_chose_search, model_chose_direct

async def call_grok_for_groksito(user_message, author_name, channel_id, original_message=None, image_urls=None, attachments=None, referenced_context=None, reply_chain_contexts=None, has_visual_intent=False, is_reply_continuation=False, has_x_link_intent=False, is_reply_to_bot=False, is_mentioned=False):
    cid_p = cid_prefix()
    model = getattr(settings, "grok_model", None) or "grok-4.3"
    bearer = _get_grok_bearer() if _get_grok_bearer else None
    if not bearer:
        bearer = getattr(settings, "xai_api_key", None) or os.getenv("XAI_API_KEY")
    if not bearer:
        logger.warning("[LLM] No Grok credential. Using stub response.")
        return _build_stub_response(user_message, author_name, image_urls)
    try:
        client = AsyncOpenAI(api_key=bearer, base_url="https://api.x.ai/v1", timeout=settings.api_timeout_seconds)
        if getattr(settings, "summarization_enabled", False):
            await _maybe_proactive_summarize(channel_id, original_message, client)
        prep = await _prepare_first_turn_data(user_message=user_message, channel_id=channel_id, original_message=original_message, image_urls=image_urls, attachments=attachments, referenced_context=referenced_context, reply_chain_contexts=reply_chain_contexts, is_reply_continuation=is_reply_continuation, has_x_link_intent=has_x_link_intent, is_reply_to_bot=is_reply_to_bot, is_mentioned=is_mentioned)
        input_data = prep["input_data"]
        initial_input = input_data["initial_input"]
        stable_prefix_len = input_data["stable_prefix_len"]
        need = input_data["need"]
        user_id = input_data["user_id"]
        user_message_text = input_data["user_message_text"]
        is_addressed = bool(is_mentioned or is_reply_to_bot)
        sel = _select_tools_for_first_turn(user_message_text=user_message_text, user_message=user_message, need=need, image_urls=image_urls, has_visual_intent=has_visual_intent, is_mentioned=is_mentioned, is_reply_to_bot=is_reply_to_bot, is_addressed=is_addressed, pure_image_gen_intent=prep["pure_image_gen_intent"], pure_video_gen_intent=prep["pure_video_gen_intent"])
        custom_tools = sel["custom_tools"]
        native_search_tools = sel["native_search_tools"]
        offered_custom_tool_names = {t.get("name") for t in custom_tools if t.get("name")}
        addressed_turn_start = time.time() if is_addressed else None
        try:
            cache_key = _get_prompt_cache_key(original_message)
            response = await _call_responses_with_retry(client, model=model, input=initial_input, tools=[*native_search_tools, *custom_tools], extra_body={"prompt_cache_key": cache_key})
        except Exception as api_err:
            is_404 = is_image_fetch_404_error(api_err, has_images=bool(image_urls))
            if is_404 or image_urls or attachments:
                plain = await build_responses_input(user_message=user_message, channel_id=channel_id, original_message=original_message, image_urls=[], attachments=attachments, referenced_context=referenced_context, reply_chain_contexts=reply_chain_contexts, is_reply_continuation=is_reply_continuation, has_x_link_intent=has_x_link_intent, image_gen_intent=prep["pure_image_gen_intent"] or prep["pure_video_gen_intent"], is_reply_to_bot=is_reply_to_bot, is_mentioned=is_mentioned)
                response = await _call_responses_with_retry(client, model=model, input=plain["initial_input"], tools=[*native_search_tools, *custom_tools], extra_body={"prompt_cache_key": cache_key})
                image_urls = []
            else:
                raise
        first_turn_prompt_tokens = 0
        try:
            usage = getattr(response, "usage", None) or (response.get("usage") if isinstance(response, dict) else None)
            if usage:
                first_turn_prompt_tokens = getattr(usage, "input_tokens", 0) if hasattr(usage, "input_tokens") else (usage.get("input_tokens", 0) if isinstance(usage, dict) else 0)
        except Exception:
            pass
        _extract_and_log_token_usage(response, model=model, has_images=bool(image_urls), category="Vision" if image_urls else "Conversation", is_tool_continuation=False, cache_context={"turn_type": "first_turn", "query_need": need, "has_visual_intent": sel["effective_visual_intent"], "custom_tools_count": len(custom_tools), "custom_tools_set": _infer_tools_set_name(need, sel["effective_visual_intent"], False), "user_id": user_id, "prefix_stability_indicator": f"sys~{stable_prefix_len}"})
        response, direct_delivery_performed, model_chose_search, model_chose_direct = await _execute_tool_loop(client=client, model=model, response=response, need=need, user_id=user_id, stable_prefix_len=stable_prefix_len, effective_visual_intent=sel["effective_visual_intent"], explicit_video_intent=sel["explicit_video_intent"], explicit_audio_intent=sel["explicit_audio_intent"], pure_image_gen_intent=prep["pure_image_gen_intent"], pure_video_gen_intent=prep["pure_video_gen_intent"], native_search_tools=native_search_tools, offered_custom_tool_names=offered_custom_tool_names, original_message=original_message, image_urls=image_urls, is_addressed=is_addressed, cid_p=cid_p)
        if is_addressed and addressed_turn_start is not None:
            try:
                from ..utils.token_usage import log_addressed_turn_metrics
                log_addressed_turn_metrics(latency_ms=(time.time() - addressed_turn_start) * 1000.0, prompt_tokens=first_turn_prompt_tokens, search_schemas_offered=bool(native_search_tools), model_chose_search=model_chose_search, model_chose_direct=model_chose_direct, query_need=need or "unknown")
            except Exception:
                pass
        return _finalize_response(response, direct_delivery_performed, cid_p)
    except Exception as e:
        logger.exception(f"{cid_p}Error during real Responses API call + tool loop")
        if image_urls and not attachments:
            return "I had trouble processing the image(s) you sent. Grok vision is having a hard time with this file right now. Describe what you see in the image in words and I can help from that."
        if isinstance(e, RateLimitError) or "rate" in str(e).lower() or "429" in str(e).lower():
            return "I am getting a lot of requests right now (rate limit). Give me a minute and try again."
        if isinstance(e, (APITimeoutError, APIConnectionError)) or "timeout" in str(e).lower() or "connection" in str(e).lower():
            return "I had a connection problem with Grok. Try again in a few seconds."
        if isinstance(e, APIError):
            status = getattr(e, "status_code", None)
            if status and 500 <= status < 600:
                return "Grok is having temporary problems (5xx). Try again in a moment."
            if status in (401, 403):
                hint = ""
                try:
                    if settings.auth_prefers_oauth or settings.using_oauth:
                        hint = " (OAuth token may be invalid/expired — try `groksito --login-oauth` or switch to XAI_API_KEY)"
                except Exception:
                    pass
                return f"Grok authentication problem (401/403).{hint}"
        return f"Sorry, I had a problem connecting to Grok: {e}"

_call_grok_with_tools = call_grok_for_groksito
_call_grok_responses_api = call_grok_for_groksito
call_grok_with_tools = call_grok_for_groksito
