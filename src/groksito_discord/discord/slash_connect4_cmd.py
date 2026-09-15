"""Challenge flow and /connect4 registration. Kept small so the play module stays intact."""
from __future__ import annotations

import discord

from . import ai_coins
from . import slash_connect4 as c4


class ChallengeView(discord.ui.View):
    def __init__(self, match_id: int):
        super().__init__(timeout=90)
        self.match_id = match_id
        self.message: discord.Message | None = None

    def _match(self):
        return c4._games.get(self.match_id)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        match = self._match()
        if match is None or match.finished:
            await interaction.response.send_message("That challenge is gone.", ephemeral=True)
            return False
        if interaction.user.id not in (match.p1, match.p2):
            await interaction.response.send_message("This challenge is not for you.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        match = self._match()
        if match is None or match.finished:
            await interaction.response.send_message("That challenge is gone.", ephemeral=True)
            return
        if interaction.user.id != match.p2:
            await interaction.response.send_message("Only the challenged player can accept.", ephemeral=True)
            return
        err = c4._hold_start(match)
        if err:
            c4._finish(match, reason=err)
            table = c4._table_file(match)
            await c4._publish(interaction, embed=c4._embed(match), view=None, table=table, edit=True)
            return
        self.stop()
        view = c4.PlayView(match.id)
        view._sync_columns(match)
        table = c4._table_file(match)
        embed = c4._embed(match, balance=ai_coins.get_balance(match.p1))
        message = await c4._publish(interaction, embed=embed, view=view, table=table, edit=True)
        view.message = message

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.secondary)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        match = self._match()
        if match is None or match.finished:
            await interaction.response.send_message("That challenge is gone.", ephemeral=True)
            return
        who = match.p1_name if interaction.user.id == match.p1 else match.p2_name
        c4._finish(match, reason=f"{who} called it off. No coins moved.")
        self.stop()
        table = c4._table_file(match)
        await c4._publish(interaction, embed=c4._embed(match), view=None, table=table, edit=True)

    async def on_timeout(self) -> None:
        match = self._match()
        if match is None or match.finished or match.held:
            return
        c4._finish(match, reason="Challenge timed out. No coins moved.")
        if self.message is not None:
            try:
                table = c4._table_file(match)
                kwargs = {"embed": c4._embed(match), "view": None}
                if table is not None:
                    kwargs["attachments"] = [table]
                await self.message.edit(**kwargs)
            except Exception:
                c4.logger.exception("connect4 challenge timeout edit failed id=%s", match.id)


async def start_vs_bot(
    interaction: discord.Interaction,
    *,
    user_id: int,
    name: str,
    bet: int,
    edit: bool,
) -> None:
    if c4._player_busy(user_id):
        msg = "Finish your current Connect Four first."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
        return
    match = c4.Match(
        id=c4._new_id(),
        guild_id=interaction.guild.id if interaction.guild else 0,
        channel_id=interaction.channel_id or 0,
        p1=user_id,
        p2=0,
        p1_name=name,
        p2_name="Aetherion",
        bet=int(bet),
        vs_bot=True,
    )
    err = c4._hold_start(match)
    if err:
        if interaction.response.is_done():
            await interaction.followup.send(err, ephemeral=True)
        else:
            await interaction.response.send_message(err, ephemeral=True)
        return
    c4._bind(match)
    c4._last_bet[user_id] = int(bet)
    view = c4.PlayView(match.id)
    view._sync_columns(match)
    table = c4._table_file(match)
    embed = c4._embed(match, balance=ai_coins.get_balance(user_id))
    message = await c4._publish(
        interaction,
        embed=embed,
        view=view,
        table=table,
        edit=edit,
        content=None,
    )
    view.message = message
