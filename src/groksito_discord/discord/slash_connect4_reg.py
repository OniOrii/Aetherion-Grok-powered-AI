"""Register /connect4."""
from __future__ import annotations

import discord

from . import ai_coins
from . import slash_connect4 as c4
from .slash_connect4_cmd import ChallengeView, start_vs_bot


def register_connect4(tree, is_guild_allowed) -> None:
    @tree.command(name="connect4", description="Connect Four vs Aetherion or a member, for Aether Coins")
    @discord.app_commands.describe(
        opponent="Leave empty to play Aetherion. Mention someone to challenge them.",
        bet=f"Stake in Aether Coins ({ai_coins.MIN_BET}\u2013{ai_coins.MAX_BET})",
    )
    @discord.app_commands.guild_only()
    async def connect4_slash(
        interaction: discord.Interaction,
        opponent: discord.Member | None = None,
        bet: int = ai_coins.DEFAULT_BET,
    ):
        if interaction.guild and not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message(
                "Aetherion is not available on this server.", ephemeral=True
            )
            return
        if interaction.guild is None:
            await interaction.response.send_message("Use this in a server.", ephemeral=True)
            return
        challenger = interaction.user
        bot_user = interaction.client.user
        vs_bot = opponent is None or (bot_user is not None and opponent.id == bot_user.id)
        err = ai_coins.amount_error(bet, ai_coins.MIN_BET, ai_coins.MAX_BET)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        if c4._player_busy(challenger.id):
            await interaction.response.send_message("Finish your current Connect Four first.", ephemeral=True)
            return
        if vs_bot:
            if bet == ai_coins.DEFAULT_BET and challenger.id in c4._last_bet:
                bet = int(c4._last_bet[challenger.id])
            await start_vs_bot(
                interaction,
                user_id=challenger.id,
                name=challenger.display_name,
                bet=int(bet),
                edit=False,
            )
            return
        if opponent.id == challenger.id:
            await interaction.response.send_message("Pick another player, or leave opponent empty to play Aetherion.", ephemeral=True)
            return
        if opponent.bot:
            await interaction.response.send_message("Leave opponent empty to play Aetherion.", ephemeral=True)
            return
        if c4._player_busy(opponent.id):
            await interaction.response.send_message(
                f"**{opponent.display_name}** is already on a board.", ephemeral=True
            )
            return
        p1_bal = ai_coins.get_balance(challenger.id)
        p2_bal = ai_coins.get_balance(opponent.id)
        if bet > p1_bal:
            await interaction.response.send_message(
                f"You only have {ai_coins.coins(p1_bal)}.", ephemeral=True
            )
            return
        if bet > p2_bal:
            await interaction.response.send_message(
                f"**{opponent.display_name}** only has {ai_coins.coins(p2_bal)}.", ephemeral=True
            )
            return
        match = c4.Match(
            id=c4._new_id(),
            guild_id=interaction.guild.id,
            channel_id=interaction.channel_id or 0,
            p1=challenger.id,
            p2=opponent.id,
            p1_name=challenger.display_name,
            p2_name=opponent.display_name,
            bet=int(bet),
            vs_bot=False,
        )
        c4._bind(match)
        view = ChallengeView(match.id)
        table = c4._table_file(match)
        embed = c4._embed(match, waiting=True)
        message = await c4._publish(
            interaction,
            embed=embed,
            view=view,
            table=table,
            edit=False,
            content=f"{opponent.mention} \u2014 **{challenger.display_name}** wants Connect Four for {ai_coins.coins(f'**{bet:,}**')} each.",
        )
        view.message = message
