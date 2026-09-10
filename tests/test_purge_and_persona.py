from groksito_discord.discord.slash_purge import clamp_purge_amount, skip_pinned
from groksito_discord.llm.persona import (
    CREATOR_DISCORD_ID,
    annotate_creator_mentions,
    creator_is_author,
)
from groksito_discord.llm.persona_bind import bind_persona

bind_persona()

from groksito_discord.llm.prompt_builder import SYSTEM_PROMPT


class _Msg:
    def __init__(self, pinned=False):
        self.pinned = pinned


def test_clamp_purge_amount():
    assert clamp_purge_amount(1) == 1
    assert clamp_purge_amount(100) == 100
    assert clamp_purge_amount(0) == 1
    assert clamp_purge_amount(250) == 100
    assert clamp_purge_amount(-5) == 1


def test_skip_pinned():
    assert skip_pinned(_Msg(pinned=False)) is True
    assert skip_pinned(_Msg(pinned=True)) is False


def test_system_prompt_uses_aetherion_persona():
    lowered = SYSTEM_PROMPT.lower()
    assert "you are aetherion" in lowered
    assert "proud ai" in lowered
    assert "never say you are zagan" in lowered
    assert "1022200760018161684" in SYSTEM_PROMPT
    assert "never suck up" in lowered or "never sound submissive" in lowered
    assert "neutral" in lowered


def test_creator_mention_annotation():
    assert creator_is_author(CREATOR_DISCORD_ID)
    out = annotate_creator_mentions("ask <@1022200760018161684> later")
    assert "<@1022200760018161684>" not in out
    assert "Ori" in out
