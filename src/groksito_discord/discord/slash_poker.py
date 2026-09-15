"""Texas Hold'em slash command. Full table file is being restored."""
from __future__ import annotations

import discord

from . import ai_coins


def register_poker(tree, is_guild_allowed) -> None:
    @tree.command(name="poker", description="Texas Hold'em, 2-4 seats. Friends and/or Aetherion. Aether Coins.")
    @discord.app_commands.describe(
        bet="Buy-in for every seat (10-1000, tens)",
        vs_aetherion="Seat Aetherion now. Friends can still join.",
    )
    async def poker_slash(
        interaction: discord.Interaction,
        bet: int = ai_coins.DEFAULT_BET,
        vs_aetherion: bool = False,
    ):
        if interaction.guild and not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message("Aetherion is not available on this server.", ephemeral=True)
            return
        await interaction.response.send_message(
            "Poker table file is being put back. Wait for Railway Active, then run /poker again.",
            ephemeral=True,
        )
