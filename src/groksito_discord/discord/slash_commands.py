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
from .slash_connect4 import register_connect4
from .slash_poker import register_poker
from .slash_hunt import register_hunt
from .slash_supply import register_supply
from .slash_help import register_help
from .slash_logs import register_logs
from . import aether_hunt_ext  # noqa: F401

logger = logging.getLogger("aetherion.slash")

_ALLOWED_GUILD_IDS = set(settings.allowed_guild_ids)


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
    register_music(tree, is_guild_allowed)
    register_purge(tree, is_guild_allowed)
    register_reactionrole(tree, is_guild_allowed)
    register_status(tree, is_guild_allowed)
    register_edit(tree, is_guild_allowed)
    register_blackjack(tree, is_guild_allowed)
    register_slots(tree, is_guild_allowed)
    register_cointoss(tree, is_guild_allowed)
    register_connect4(tree, is_guild_allowed)
    register_poker(tree, is_guild_allowed)
    register_hunt(tree, is_guild_allowed)
    register_supply(tree, is_guild_allowed)

    @tree.command(name="ping", description="Aetherion latency and connection status.")
    async def ping(interaction: discord.Interaction):
        if interaction.guild and not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message(
                "Aetherion is not available on this server.", ephemeral=True
            )
            return
        started = time.perf_counter()
        await interaction.response.defer(ephemeral=True)
        rest_ms = (time.perf_counter() - started) * 1000
        client = interaction.client
        ws_ms = float(getattr(client, "latency", 0) or 0) * 1000
        if ws_ms < 0:
            ws_ms = 0.0
        if ws_ms < 80:
            grade = "Excellent"
        elif ws_ms < 150:
            grade = "Good"
        elif ws_ms < 250:
            grade = "Okay"
        else:
            grade = "Slow"
        guilds = len(getattr(client, "guilds", []) or [])
        voices = len(getattr(client, "voice_clients", []) or [])
        embed = discord.Embed(
            title="\u2726 Aetherion",
            description=f"Alive \u00b7 {grade}",
            color=0xC9A227,
        )
        embed.add_field(name="Gateway", value=f"**{ws_ms:.0f} ms**", inline=True)
        embed.add_field(name="Command", value=f"**{rest_ms:.0f} ms**", inline=True)
        embed.add_field(name="Servers", value=str(guilds), inline=True)
        if interaction.guild is not None:
            embed.add_field(name="This server", value=interaction.guild.name, inline=True)
        embed.add_field(name="Voice", value=str(voices), inline=True)
        embed.set_footer(text="Gateway is the Discord heartbeat. Command is this slash reply.")
        await interaction.edit_original_response(embed=embed)
