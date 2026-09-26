"""Aetherion slash commands. Game chart commands are not registered."""
from __future__ import annotations

from typing import Optional
import logging
import time

import discord

from ..config import settings
from ..media.delivery import register_image_request
from ..media.audio_handler import (
    AUDIO_WRAPPING_TAGS,
    _tool_generate_audio,
    apply_wrapping_speech_tag,
    build_audio_speech_tags_embed,
    prepare_text_from_interaction,
)
from ..media.voice_session import get_recv_cls, start_session, stop_session
from .slash_edit import register_edit
from .slash_music import register_music
from .slash_purge import register_purge
from .slash_reactionrole import register_reactionrole
from .slash_status import register_status
from .slash_blackjack import register_blackjack
from .slash_slots import register_slots
from .slash_cointoss import register_cointoss
from .slash_higherlower import register_highlow
from .slash_connect4 import register_connect4
from .slash_poker import register_poker
from .slash_help import register_help
from .slash_logs import register_logs
from .slash_autorole import register_autorole
from .slash_profile import register_profile
from .slash_top import register_top
from .brand import stamp

logger = logging.getLogger("aetherion.slash")

_ALLOWED_GUILD_IDS = set(settings.allowed_guild_ids)
RATE_LIMIT_MSG = "Easy \u2014 you already used your 6 requests this minute."


def is_guild_allowed(guild_id):
    if not _ALLOWED_GUILD_IDS:
        return True
    if guild_id is None:
        return False
    return guild_id in _ALLOWED_GUILD_IDS


def register(tree, client) -> None:
    from .client import rate_limiter

    @tree.interaction_check
    async def _reject_dm_commands(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            await interaction.response.send_message("Aetherion only works in a server.", ephemeral=True)
            return False
        return True

    register_help(tree, is_guild_allowed)
    register_logs(tree, is_guild_allowed)
    register_autorole(tree, is_guild_allowed)
    register_profile(tree, is_guild_allowed)
    register_top(tree, is_guild_allowed)
    register_music(tree, is_guild_allowed)
    register_purge(tree, is_guild_allowed)
    register_reactionrole(tree, is_guild_allowed)
    register_status(tree, is_guild_allowed)
    register_edit(tree, is_guild_allowed)
    register_blackjack(tree, is_guild_allowed)
    register_slots(tree, is_guild_allowed)
    register_cointoss(tree, is_guild_allowed)
    register_highlow(tree, is_guild_allowed)
    register_connect4(tree, is_guild_allowed)
    register_poker(tree, is_guild_allowed)
