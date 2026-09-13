"""Aetherion slash commands. Game chart commands are not registered."""
from __future__ import annotations

from typing import Optional
import logging

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
    register_music(tree, is_guild_allowed)
    register_purge(tree, is_guild_allowed)
    register_reactionrole(tree, is_guild_allowed)
    register_status(tree, is_guild_allowed)
    register_edit(tree, is_guild_allowed)
    register_blackjack(tree, is_guild_allowed)
    register_slots(tree, is_guild_allowed)

    @tree.command(name="ping", description="Check if Aetherion is awake")
    async def ping(interaction: discord.Interaction):
        if interaction.guild and not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message(
                "Aetherion is not available on this server.", ephemeral=True
            )
            return
        await interaction.response.send_message("Still here.", ephemeral=True)

    @tree.command(
        name="welcome",
        description="Set the channel for welcome banners. Administrators only.",
    )
    @discord.app_commands.describe(channel="Channel where new-member welcomes should post")
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.guild_only()
    async def welcome_slash(interaction: discord.Interaction, channel: discord.TextChannel):
        if interaction.guild and not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message(
                "Aetherion is not available on this server.", ephemeral=True
            )
            return
        if interaction.guild is None:
            await interaction.response.send_message("Use this command in a server.", ephemeral=True)
            return
        member = interaction.user
        perms = getattr(member, "guild_permissions", None)
        if not perms or not perms.administrator:
            await interaction.response.send_message(
                "Only Discord Administrators can set the welcome channel.", ephemeral=True
            )
            return
        from .welcome import set_guild_welcome_channel
        set_guild_welcome_channel(interaction.guild.id, channel.id)
        await interaction.response.send_message(
            f"Welcome banners will now post in {channel.mention}.", ephemeral=True
        )

    @tree.command(
        name="datechannel",
        description="Set the voice channel that shows today's date. Administrators only.",
    )
    @discord.app_commands.describe(channel="Voice channel to rename each night at midnight Eastern")
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.guild_only()
    async def datechannel_slash(interaction: discord.Interaction, channel: discord.VoiceChannel):
        if interaction.guild and not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message(
                "Aetherion is not available on this server.", ephemeral=True
            )
            return
        if interaction.guild is None:
            await interaction.response.send_message("Use this command in a server.", ephemeral=True)
            return
        member = interaction.user
        perms = getattr(member, "guild_permissions", None)
        if not perms or not perms.administrator:
            await interaction.response.send_message(
                "Only Discord Administrators can set the date channel.", ephemeral=True
            )
            return
        from .date_dock import set_guild_date_channel, format_date_channel_name
        set_guild_date_channel(interaction.guild.id, channel.id)
        preview = format_date_channel_name()
        await interaction.response.send_message(
            f"Date dock set to {channel.mention}. It will show `{preview}` and update at 12:00 AM Eastern.",
            ephemeral=True,
        )
        try:
            if channel.name != preview:
                await channel.edit(name=preview, reason="Aetherion date dock setup")
        except discord.Forbidden:
            await interaction.followup.send(
                "Saved, but I could not rename it. Give me **Manage Channels** on that voice channel.",
                ephemeral=True,
            )
        except Exception:
            logger.exception("date dock immediate rename failed")
