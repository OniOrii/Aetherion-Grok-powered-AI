"""Voice-only Grok request shaping.

Live VC replies keep the same model as text by default, but use light
reasoning and a short output cap so spoken answers start sooner.
"""
from __future__ import annotations

from typing import Any

DEFAULT_VOICE_MODEL = "grok-4.3"
DEFAULT_VOICE_EFFORT = "low"
DEFAULT_VOICE_MAX_TOKENS = 180
_VOICE_EFFORTS = frozenset({"none", "minimal", "low", "medium", "high", "xhigh"})


def resolve_voice_model(voice_grok_model: str | None, grok_model: str | None) -> str:
    override = (voice_grok_model or "").strip()
    if override:
        return override
    return (grok_model or DEFAULT_VOICE_MODEL).strip() or DEFAULT_VOICE_MODEL


def resolve_voice_effort(raw: str | None) -> str:
    value = (raw or DEFAULT_VOICE_EFFORT).strip().lower()
    if value in ("off", "disable", "disabled", "0"):
        return "none"
    if value in _VOICE_EFFORTS:
        return value
    return DEFAULT_VOICE_EFFORT


def resolve_voice_max_tokens(raw: Any) -> int:
    try:
        n = int(raw if raw is not None else DEFAULT_VOICE_MAX_TOKENS)
    except (TypeError, ValueError):
        n = DEFAULT_VOICE_MAX_TOKENS
    return max(40, min(n, 800))


def build_voice_responses_payload(
    system: str,
    user_content: str,
    *,
    model: str,
    effort: str,
    max_output_tokens: int,
    include_reasoning: bool = True,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "input": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        "tools": [{"type": "web_search"}],
        "temperature": 0.8,
        "max_output_tokens": max_output_tokens,
    }
    if include_reasoning:
        payload["reasoning"] = {"effort": effort}
    return payload


def build_voice_chat_payload(
    system: str,
    user_content: str,
    *,
    model: str,
    effort: str,
    max_output_tokens: int,
    include_reasoning: bool = True,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.8,
        "max_tokens": max_output_tokens,
    }
    if include_reasoning:
        payload["reasoning_effort"] = effort
    return payload
