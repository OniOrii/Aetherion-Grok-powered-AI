"""Administrator /purge command (Dyno-style bulk delete)."""
from __future__ import annotations

import logging

import discord

logger = logging.getLogger("aetherion.slash_purge")

MIN_PURGE = 1
MAX_PURGE = 100


def clamp_purge_amount(amount: int) -> int:
    try:
        n = int(amount)
    except (TypeError, ValueError):
        return MIN_PURGE
    return max(MIN_PURGE, min(MAX_PURGE, n))


def is_administrator(interaction: discord.Interaction) -> bool:
    perms = getattr(interaction.user, "guild_permissions", None)
    return bool(perms and perms.administrator)


def register_purge(tree, is_guild_allowed) -> None:
    @tree.command(
        name="purge",
        description="Delete up to 100 recent messages in this channel. Administrators only.",
    )
    @discord.app_commands.describe(amount="How many messages to delete (1-100)")
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.guild_only()
    async def purge_slash(interaction: discord.Interaction, amount: int = 10):
        if interaction.guild is None:
            await interaction.response.send_message(
                "Use /purge in a server channel.", ephemeral=True
            )
            return
        if not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message(
                "Aetherion is not available on this server.", ephemeral=True
            )
            return
        if not is_administrator(interaction):
            await interaction.response.send_message(
                "Only Discord Administrators can use /purge.", ephemeral=True
            )
            return

        channel = interaction.channel
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message(
                "I can only purge text channels.", ephemeral=True
            )
            return

        me = interaction.guild.me
        bot_perms = channel.permissions_for(me) if me is not None else None
        if bot_perms is None or not bot_perms.manage_messages:
            await interaction.response.send_message(
                "I need **Manage Messages** in this channel to purge.",
                ephemeral=True,
            )
            return

        count = clamp_purge_amount(amount)
        await interaction.response.defer(ephemeral=True)
        try:
            deleted = await channel.purge(
                limit=count,
                check=lambda message: not getattr(message, "pinned", False),
                reason=f"Aetherion /purge by {interaction.user}",
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "Discord blocked the purge. I need **Manage Messages** here.",
                ephemeral=True,
            )
            return
        except discord.HTTPException:
            logger.exception("purge failed")
            await interaction.followup.send(
                "Could not purge those messages. Try a smaller number.",
                ephemeral=True,
            )
            return

        n = len(deleted)
        await interaction.followup.send(
            f"Deleted **{n}** message{'s' if n != 1 else ''}.",
            ephemeral=True,
        )
