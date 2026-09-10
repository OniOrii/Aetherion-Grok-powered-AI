"""Apply the Zagan persona onto the live system prompt at import time."""
from __future__ import annotations


def bind_persona() -> None:
    from . import prompt_builder
    from .persona import (
        CREATOR_DISCORD_ID,
        CREATOR_DISCORD_IDS,
        CREATOR_LABEL,
        CREATOR_NAME,
        GROK_IDENTITY,
        GROK_VOICE_GUIDANCE,
        annotate_creator_mentions,
        creator_is_author,
        creator_is_mentioned,
    )

    prompt_builder.CREATOR_DISCORD_ID = CREATOR_DISCORD_ID
    prompt_builder.CREATOR_DISCORD_IDS = CREATOR_DISCORD_IDS
    prompt_builder.CREATOR_LABEL = CREATOR_LABEL
    prompt_builder.CREATOR_NAME = CREATOR_NAME
    prompt_builder.GROK_IDENTITY = GROK_IDENTITY
    prompt_builder.GROK_VOICE_GUIDANCE = GROK_VOICE_GUIDANCE
    prompt_builder.annotate_creator_mentions = annotate_creator_mentions
    prompt_builder.creator_is_author = creator_is_author
    prompt_builder.creator_is_mentioned = creator_is_mentioned
    prompt_builder.SYSTEM_PROMPT = (
        "You are Aetherion on this Discord server, running on Grok.\n\n"
        f"{GROK_IDENTITY}\n\n"
        f"{prompt_builder.COMPLETENESS_DEFAULT}\n\n"
        f"{prompt_builder.COMPLETENESS_SELF_CHECK}\n"
        f"{prompt_builder.COMPLETENESS_ACCURACY_BALANCE}\n\n"
        f"{prompt_builder.NATIVE_TOOL_JUDGMENT}: {prompt_builder.KNOWLEDGE_FIRST_HINT}; "
        f"{prompt_builder.FRESHNESS_GUIDANCE}; {prompt_builder.WEB_SEARCH_BREADTH_GUIDANCE}; "
        f"{prompt_builder.VIDEO_LINK_SEARCH_HINT}; {prompt_builder.X_SEARCH_PROMPT_HINT}; "
        f"{prompt_builder.VISION_MEDIA_HINT}; {prompt_builder.DISCORD_DELIVERY_NOTE}; "
        f"{prompt_builder.ON_DEMAND_CONTEXT}. {prompt_builder.SEARCH_SYNTHESIS}\n\n"
        f"{GROK_VOICE_GUIDANCE}\n\n"
        f"{prompt_builder.USER_INTENT_NOTE}"
    )
    try:
        from . import llm_input
        llm_input.SYSTEM_PROMPT = prompt_builder.SYSTEM_PROMPT
    except Exception:
        pass
