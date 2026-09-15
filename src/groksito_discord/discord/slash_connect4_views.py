"""Connect Four buttons."""
from __future__ import annotations

import asyncio

import discord

from . import ai_coins
from .connect4_board import COLS
from . import slash_connect4 as c4
from . import slash_connect4_flow as flow


class ReplayView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=180)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your board.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.primary)
    async def play_again(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .slash_connect4_cmd import start_vs_bot
        bet = int(c4._last_bet.get(self.user_id) or ai_coins.DEFAULT_BET)
        await start_vs_bot(interaction, user_id=self.user_id, name=interaction.user.display_name, bet=bet, edit=True)


class PlayView(discord.ui.View):
    def __init__(self, match_id: int):
        super().__init__(timeout=180)
        self.match_id = match_id
        self.message: discord.Message | None = None
        for col in range(COLS):
            button = discord.ui.Button(
                label=str(col + 1),
                style=discord.ButtonStyle.secondary,
                row=0 if col < 5 else 1,
            )
            button.callback = self._make_drop(col)
            self.add_item(button)
        forfeit = discord.ui.Button(label="Forfeit", style=discord.ButtonStyle.danger, row=1)
        forfeit.callback = self._forfeit
        self.add_item(forfeit)

    def _match(self):
        return c4._games.get(self.match_id)

    def _sync_columns(self, match) -> None:
        for item in self.children:
            if not isinstance(item, discord.ui.Button):
                continue
            if item.label and item.label.isdigit():
                col = int(item.label) - 1
                item.disabled = match.finished or not match.column_open(col)
            elif item.label == "Forfeit":
                item.disabled = match.finished

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        match = self._match()
        if match is None or match.finished:
            await interaction.response.send_message("This table is already over.", ephemeral=True)
            return False
        allowed = (match.p1,) if match.vs_bot else (match.p1, match.p2)
        if interaction.user.id not in allowed:
            await interaction.response.send_message("This is not your board.", ephemeral=True)
            return False
        return True

    def _end_view(self, match):
        self._sync_columns(match)
        self.stop()
        if match.vs_bot:
            return ReplayView(match.p1)
        return self

    async def _show_finished(self, interaction: discord.Interaction, match) -> None:
        next_view = self._end_view(match)
        pocket = ai_coins.get_balance(match.p1)
        embed = flow._embed(match, balance=pocket)
        table = flow._table_file(match)
        await flow._publish(interaction, embed=embed, view=next_view, table=table, edit=True)

    def _make_drop(self, col: int):
        async def drop(interaction: discord.Interaction) -> None:
            match = self._match()
            if match is None or match.finished:
                await interaction.response.send_message("This table is already over.", ephemeral=True)
                return
            piece = match.piece_of(interaction.user.id)
            if piece != match.turn:
                await interaction.response.send_message("Wait for your turn.", ephemeral=True)
                return
            if getattr(match, "busy", False):
                await interaction.response.send_message("Wait for the disc to land.", ephemeral=True)
                return
            if match.drop(col, piece) is None:
                await interaction.response.send_message("That column is full.", ephemeral=True)
                return
            match.busy = True
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True
            land_row = match.last_row
            land_col = match.last_col
            who = match.name_of(piece)
            await flow._animate_fall(
                interaction,
                match,
                self,
                piece=piece,
                col=land_col,
                landing_row=land_row,
                caption=f"{who} drops in column {land_col + 1}.",
            )
            flow._after_drop(match, piece)
            if match.finished:
                await self._show_finished(interaction, match)
                return
            if match.vs_bot and match.turn == c4.P2:
                await asyncio.sleep(c4.THINK_SLEEP)
                flow._bot_move(match)
                if match.last_row >= 0:
                    if not match.finished:
                        match.busy = False
                        self._sync_columns(match)
                    await flow._animate_fall(
                        interaction,
                        match,
                        self if not match.finished else self._end_view(match),
                        piece=c4.P2,
                        col=match.last_col,
                        landing_row=match.last_row,
                        caption="Aetherion drops.",
                    )
                if match.finished:
                    await self._show_finished(interaction, match)
                    return
                return
            match.busy = False
            self._sync_columns(match)
        return drop

    async def _forfeit(self, interaction: discord.Interaction) -> None:
        match = self._match()
        if match is None or match.finished:
            await interaction.response.send_message("This table is already over.", ephemeral=True)
            return
        if getattr(match, "busy", False):
            await interaction.response.send_message("Wait for the disc to land.", ephemeral=True)
            return
        piece = match.piece_of(interaction.user.id)
        if piece == c4.EMPTY:
            await interaction.response.send_message("This is not your board.", ephemeral=True)
            return
        winner = c4.P2 if piece == c4.P1 else c4.P1
        flow._finish(
            match,
            winner=winner,
            reason=f"{match.name_of(piece)} forfeits. {match.name_of(winner)} takes the pot.",
        )
        next_view = self._end_view(match)
        pocket = ai_coins.get_balance(match.p1)
        table = flow._table_file(match)
        embed = flow._embed(match, balance=pocket)
        await flow._publish(interaction, embed=embed, view=next_view, table=table, edit=True)

    async def on_timeout(self) -> None:
        match = self._match()
        if match is None or match.finished:
            return
        current = match.turn
        winner = c4.P2 if current == c4.P1 else c4.P1
        flow._finish(
            match,
            winner=winner,
            reason=f"{match.name_of(current)} ran out of time. {match.name_of(winner)} takes the pot.",
        )
        view = ReplayView(match.p1) if match.vs_bot else self
        if self.message is not None:
            try:
                table = flow._table_file(match)
                embed = flow._embed(match, balance=ai_coins.get_balance(match.p1))
                kwargs = {"embed": embed, "view": view}
                if table is not None:
                    kwargs["attachments"] = [table]
                await self.message.edit(**kwargs)
            except Exception:
                c4.logger.exception("connect4 timeout edit failed id=%s", match.id)
