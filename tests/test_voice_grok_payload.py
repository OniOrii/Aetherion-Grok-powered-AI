"""Voice-only Grok payload: faster reasoning, text chat unchanged."""
from __future__ import annotations

from groksito_discord.media.voice_grok import (
    build_voice_chat_payload,
    build_voice_responses_payload,
    resolve_voice_effort,
    resolve_voice_max_tokens,
    resolve_voice_model,
)


def test_default_voice_model_follows_text_model():
    assert resolve_voice_model("", "grok-4.3") == "grok-4.3"
    assert resolve_voice_model(None, None) == "grok-4.3"


def test_voice_model_override():
    assert resolve_voice_model("grok-4.3", "grok-4.6") == "grok-4.3"


def test_default_effort_is_low():
    assert resolve_voice_effort("low") == "low"
    assert resolve_voice_effort(None) == "low"


def test_effort_aliases_and_unknown():
    assert resolve_voice_effort("off") == "none"
    assert resolve_voice_effort("NOPE") == "low"


def test_output_cap_clamped():
    assert resolve_voice_max_tokens(12) == 40
    assert resolve_voice_max_tokens(9999) == 800
    assert resolve_voice_max_tokens("180") == 180


def test_responses_payload_includes_low_reasoning_and_search():
    payload = build_voice_responses_payload(
        "sys",
        "hello",
        model="grok-4.3",
        effort="low",
        max_output_tokens=180,
    )
    assert payload["model"] == "grok-4.3"
    assert payload["tools"] == [{"type": "web_search"}]
    assert payload["reasoning"] == {"effort": "low"}
    assert payload["max_output_tokens"] == 180
    assert payload["input"][1]["content"] == "hello"


def test_responses_payload_can_omit_reasoning():
    payload = build_voice_responses_payload(
        "sys",
        "hello",
        model="grok-4.3",
        effort="low",
        max_output_tokens=180,
        include_reasoning=False,
    )
    assert "reasoning" not in payload
    assert payload["tools"] == [{"type": "web_search"}]


def test_chat_fallback_payload():
    payload = build_voice_chat_payload(
        "sys",
        "hello",
        model="grok-4.3",
        effort="low",
        max_output_tokens=180,
    )
    assert payload["reasoning_effort"] == "low"
    assert payload["max_tokens"] == 180
    assert "tools" not in payload
