"""LLM client (Grok Responses), prompt building, input assembly, tools, helpers.

Reexports for `from groksito_discord.llm import call_grok...` compat (used by core.conversation etc).
"""

from .client import (
    call_grok_for_groksito,
    call_grok_with_tools,
)
from .prompt_builder import (
    SUMMARIZATION_PROMPT,
    get_native_search_descriptions,
)
from .persona_bind import bind_persona

bind_persona()

from .prompt_builder import SYSTEM_PROMPT

__all__ = [
    "call_grok_for_groksito",
    "call_grok_with_tools",
    "SYSTEM_PROMPT",
    "SUMMARIZATION_PROMPT",
    "get_native_search_descriptions",
]
