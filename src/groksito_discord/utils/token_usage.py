"""
Token Usage Tracking for Groksito.

Provides:
- Logging of prompt/completion/total tokens + rough cost after every Responses API call.
- Captures cached_tokens when using prompt_cache_key (xAI Prompt Caching).
- In-memory history of recent requests (resets on restart).
- Summary functions usable both for logging and as a user-facing tool.

This is intentionally lightweight (no external DB) since the bot runs as a single process.
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections import deque
from datetime import date, datetime
from typing import Any

from .correlation import cid_prefix

logger = logging.getLogger("groksito.tokens")
cache_logger = logging.getLogger("groksito.cache")  # dedicated for structured caching logs


# =============================================================================
# Pricing (per million tokens, USD) - grok-4.3 as of May 2026
# =============================================================================
# Source: https://docs.x.ai/developers/pricing
# Images count toward input tokens.
DEFAULT_PRICING: dict[str, float] = {
    "input": 1.25,     # $1.25 / M input tokens
    "output": 2.50,    # $2.50 / M output tokens
}


_recent_usage: deque[dict[str, Any]] = deque(maxlen=50)
_recent_addressed: deque[dict[str, Any]] = deque(maxlen=50)  # Addressed-turn metrics ring buffer
_session_totals: dict[str, float | int] = {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "calls": 0,
    "estimated_cost_usd": 0.0,
}
_last_reset: date = date.today()


def _get_pricing(model: str | None = None) -> dict[str, float]:
    """Return pricing dict. Can be extended later for model-specific rates."""
    # For now we use the same rates for grok-4.3 and fallbacks.
    return DEFAULT_PRICING


def estimate_cost(prompt_tokens: int, completion_tokens: int, model: str = "grok-4.3") -> float:
    """Rough cost estimate in USD."""
    p = _get_pricing(model)
    cost = (prompt_tokens * p["input"] + completion_tokens * p["output"]) / 1_000_000
    return round(cost, 6)


def log_usage(
    *,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    model: str,
    category: str = "Conversation",
    has_images: bool = False,
    tool_round: bool = False,
    cached_tokens: int = 0,
) -> None:
    """
    Record one Responses API call and emit a clean [TOKENS] log line.

    When prompt_cache_key is used correctly, you will start seeing cached_tokens > 0
    on follow-up turns for the same user (major cost and latency win).
    """
    cost = estimate_cost(prompt_tokens, completion_tokens, model)

    # Update rolling totals
    _session_totals["prompt_tokens"] += prompt_tokens
    _session_totals["completion_tokens"] += completion_tokens
    _session_totals["total_tokens"] += total_tokens
    _session_totals["calls"] += 1
    _session_totals["estimated_cost_usd"] += cost

    entry = {
        "ts": time.time(),
        "date": date.today(),
        "model": model,
        "prompt": prompt_tokens,
        "completion": completion_tokens,
        "total": total_tokens,
        "category": category,
        "has_images": has_images,
        "tool_round": tool_round,
        "cost_usd": cost,
        "cached_tokens": cached_tokens,
    }
    _recent_usage.append(entry)

    # Build nice label (avoid duplication)
    label_parts = [category]
    if has_images and "Vision" not in category:
        label_parts.append("Vision")
    if tool_round and "Tool" not in category:
        label_parts.append("Tool")
    label = "+".join(label_parts)

    cache_str = f" cached={cached_tokens}" if cached_tokens > 0 else ""
    logger.info(
        f"{cid_prefix()}[TOKENS] [{label}] prompt={prompt_tokens} completion={completion_tokens} "
        f"total={total_tokens}{cache_str} cost=${cost:.5f} model={model}"
    )


def get_recent_usage_summary(n: int = 10) -> str:
    """Human-readable summary of the most recent N calls + session totals."""
    if not _recent_usage:
        return "No token usage has been recorded in this bot session yet."

    recent = list(_recent_usage)[-n:]
    lines = [f"**Last {len(recent)} token requests:**"]

    for e in recent:
        dt = datetime.fromtimestamp(e["ts"]).strftime("%H:%M:%S")
        extra = []
        if e.get("has_images") and "Vision" not in e.get("category", ""):
            extra.append("Vision")
        if e.get("tool_round") and "Tool" not in e.get("category", ""):
            extra.append("Tool")
        extra_str = " + " + "+".join(extra) if extra else ""

        cached = e.get("cached_tokens", 0) or 0
        cache_part = f" cached={cached}" if cached > 0 else ""
        lines.append(
            f"• `{dt}` [{e['category']}{extra_str}] "
            f"p={e['prompt']} c={e['completion']} t={e['total']}{cache_part} ~${e['cost_usd']:.4f}"
        )

    lines.append("")
    lines.append(
        f"**Session totals:** { _session_totals['calls']} calls | "
        f"prompt={_session_totals['prompt_tokens']} | "
        f"completion={_session_totals['completion_tokens']} | "
        f"total={_session_totals['total_tokens']} | "
        f"~${_session_totals['estimated_cost_usd']:.4f} USD"
    )
    lines.append("_Prices are estimates based on grok-4.3 (input $1.25 / M, output $2.50 / M). "
                 "Cached tokens (from prompt_cache_key) are billed at a large discount. "
                 "cached=128 (or small multiples) is *normal and expected* with our maximum-nativeness light design "
                 "(tiny SYSTEM_PROMPT + zero/minimal context on most turns + tiny continuation tools = small stable prefix). "
                 "The backend uses 128-token block granularity for prompt caching._")

    return "\n".join(lines)


def get_daily_summary() -> str:
    """Summary for today only (from the in-memory buffer)."""
    today = date.today()
    todays = [e for e in _recent_usage if e.get("date") == today]
    if not todays:
        return "No token usage recorded for today yet."

    p = sum(e["prompt"] for e in todays)
    c = sum(e["completion"] for e in todays)
    t = sum(e["total"] for e in todays)
    cost = sum(e["cost_usd"] for e in todays)

    return (
        f"**Today's usage** ({len(todays)} requests):\n"
        f"prompt={p} | completion={c} | total={t} | estimated cost ~${cost:.4f} USD"
    )


def reset_session_totals() -> None:
    """Mainly for testing / admin use."""
    global _session_totals, _last_reset
    _session_totals = {k: 0 if isinstance(v, (int, float)) else v for k, v in _session_totals.items()}
    _last_reset = date.today()
    logger.info(f"{cid_prefix()}[TOKENS] Session token totals have been reset.")


# =============================================================================
# Snapshot accessors for external observers (web dashboard, health writers)
# These are cheap, read-only views of the in-memory state. Never mutate.
# =============================================================================

def get_session_stats() -> dict[str, Any]:
    """Return current session aggregates. Safe for periodic snapshots."""
    return {
        "calls": int(_session_totals.get("calls", 0)),
        "prompt_tokens": int(_session_totals.get("prompt_tokens", 0)),
        "completion_tokens": int(_session_totals.get("completion_tokens", 0)),
        "total_tokens": int(_session_totals.get("total_tokens", 0)),
        "estimated_cost_usd": round(float(_session_totals.get("estimated_cost_usd", 0.0)), 6),
        "last_reset": _last_reset.isoformat() if hasattr(_last_reset, "isoformat") else str(_last_reset),
    }


def get_recent_calls(n: int = 8) -> list[dict[str, Any]]:
    """Return the most recent N call records (lightweight copy)."""
    if not _recent_usage:
        return []
    recent = list(_recent_usage)[-max(1, int(n)) :]
    out: list[dict[str, Any]] = []
    for e in recent:
        out.append({
            "ts": float(e.get("ts", 0)),
            "model": e.get("model"),
            "prompt": int(e.get("prompt", 0)),
            "completion": int(e.get("completion", 0)),
            "total": int(e.get("total", 0)),
            "cost_usd": round(float(e.get("cost_usd", 0)), 6),
            "category": e.get("category"),
            "cached_tokens": int(e.get("cached_tokens", 0) or 0),
            "has_images": bool(e.get("has_images", False)),
            "tool_round": bool(e.get("tool_round", False)),
        })
    return out


def log_context_injection(injected_tokens: int, description: str = "dynamic context", has_memory: bool = False, has_summary: bool = False) -> None:
    """
    Lightweight logging for pre-LLM context injection size.
    (has_memory always False post-removal of custom per-user memory; kept for log compatibility.)
    Uses the same logger as token tracking.
    """
    extra = []
    if has_memory:
        extra.append("memory")
    if has_summary:
        extra.append("summary")
    extra_str = " + " + "+".join(extra) if extra else ""
    logger.info(f"{cid_prefix()}[CONTEXT] injected~{injected_tokens} tokens ({description}{extra_str})")


def log_cache_metrics(
    *,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    cached_tokens: int = 0,
    turn_type: str = "unknown",           # "first_turn" | "continuation"
    query_need: str = "unknown",          # "casual" | "minimal" | "normal" | "rich"
    has_visual_intent: bool = False,
    custom_tools_count: int = 0,
    custom_tools_set: str = "unknown",
    user_id: str = "",
    prefix_stability_indicator: str = "",  # e.g. "sys_len=3980" or short hash
) -> None:
    """
    Structured logging for prompt caching effectiveness.
    Called after every Responses API call when we have usage data + context.
    Respects the log_cache_metrics config flag (falls back to log_tool_selection if needed).
    """
    try:
        from ..config import settings
        enabled = getattr(settings, "log_cache_metrics", None)
        if enabled is None:
            enabled = getattr(settings, "log_tool_selection", True)
        if not enabled:
            return
    except Exception:
        # If config unavailable, default to logging (observability is valuable)
        pass

    # Compute hit rate
    hit_rate_str = "N/A"
    if prompt_tokens > 0 and cached_tokens >= 0:
        rate = (cached_tokens / prompt_tokens) * 100
        hit_rate_str = f"{rate:.0f}%"

    cached_str = cached_tokens if cached_tokens >= 0 else "N/A"

    # Anonymize user a bit for logs (last 6 digits is common and useful for correlation)
    user_str = "unknown"
    if user_id:
        uid = str(user_id)
        user_str = "..." + uid[-6:] if len(uid) > 6 else uid

    # Optional prefix stability hint (keeps logs short)
    stability_part = f" | prefix={prefix_stability_indicator}" if prefix_stability_indicator else ""

    msg = (
        f"[CACHE] hit_rate={hit_rate_str} | "
        f"cached={cached_str} | "
        f"prompt={prompt_tokens} | "
        f"completion={completion_tokens} | "
        f"total={total_tokens} | "
        f"turn={turn_type} | "
        f"need={query_need} | "
        f"visual={str(has_visual_intent).lower()} | "
        f"tools={custom_tools_count} | "
        f"set={custom_tools_set} | "
        f"user={user_str}"
        f"{stability_part}"
    )

    cache_logger.info(f"{cid_prefix()}{msg}")


def log_addressed_turn_metrics(
    *,
    latency_ms: float,
    prompt_tokens: int = 0,
    search_schemas_offered: bool = False,
    model_chose_search: bool = False,
    model_chose_direct: bool = False,
    query_need: str = "unknown",
    # Extended signals for #23 (tool decision observability on addressed turns). Callers (llm.py)
    # can pass these; safe defaults for backward compat with existing call sites.
    model_chose_recent_context: bool = False,
    model_chose_respond_directly: bool = False,
    media_tools_used: bool = False,
    custom_tools_used: list[str] | None = None,
    **_: Any,
) -> None:
    """Lightweight addressed-turn instrumentation for observability.

    Structured [ADDRESSED] logs + append to small in-mem _recent_addressed deque.
    Captures key signals about Grok's tool choices (search, direct, recent context, media, delivery).
    Low overhead. Logs enable analysis of when/why model picks specific tools.
    """
    try:
        tools_str = ",".join(custom_tools_used) if custom_tools_used else ""
        entry = {
            "ts": time.time(),
            "latency_ms": round(float(latency_ms), 1),
            "prompt_tokens": int(prompt_tokens or 0),
            "search_schemas_offered": bool(search_schemas_offered),
            "chose_search": bool(model_chose_search),
            "chose_direct": bool(model_chose_direct),
            "need": query_need or "unknown",
            "chose_recent": bool(model_chose_recent_context),
            "chose_respond": bool(model_chose_respond_directly),
            "media": bool(media_tools_used),
            "tools": tools_str,
        }
        _recent_addressed.append(entry)

        logger.info(
            f"{cid_prefix()}[ADDRESSED] latency_ms={entry['latency_ms']} prompt={entry['prompt_tokens']} "
            f"search_offered={str(entry['search_schemas_offered']).lower()} "
            f"chose_search={str(entry['chose_search']).lower()} chose_direct={str(entry['chose_direct']).lower()} "
            f"chose_recent={str(entry['chose_recent']).lower()} chose_respond={str(entry['chose_respond']).lower()} "
            f"media={str(entry['media']).lower()} tools=[{entry['tools']}] need={entry['need']}"
        )
    except Exception:
        # metrics must never impact main path
        pass
