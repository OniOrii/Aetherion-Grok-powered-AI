"""
Aetherion Discord Bot — Independent Conversational Agent

This package contains the full Grok-powered Discord conversational experience:
- Native vision via xAI Responses API
- Channel/referenced context, custom tools, image/video generation
- Live voice via DAVE decrypt
"""

__version__ = "0.2.0"

try:
    from .llm.persona_bind import bind_persona

    bind_persona()
except Exception:
    pass
