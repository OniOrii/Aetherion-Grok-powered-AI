"""Connect Four: challenge a member or play Aetherion. Aether Coin stakes."""
from __future__ import annotations

import asyncio
import io
import logging
from dataclasses import dataclass, field

import discord

from . import ai_coins
from .connect4_board import (
    COLS,
    EMPTY,
    P1,
    P2,
    ROWS,
    choose_column,
    render_board_png,
    render_fall_gif,
)

logger = logging.getLogger("aetherion.slash_connect4")

DISC = {EMPTY: "\u26ab", P1: "\U0001f534", P2: "\U0001f7e1"}
TABLE_NAME = "connect4.png"
TABLE_GIF = "connect4.gif"
THINK_SLEEP = 0.65

EMBED_WAIT = 0xC9A227
EMBED_PLAY = 0x3D6B9B
EMBED_WIN = 0x3D9B64
EMBED_DRAW = 0x8A8F98
EMBED_DEAD = 0xC45C4A

_games: dict[int, "Match"] = {}
_by_user: dict[int, int] = {}
_next_id = 1
_last_bet: dict[int, int] = {}


def _new_id() -> int:
    global _next_id
    gid = _next_id
    _next_id += 1
    return gid


def _player_busy(user_id: int) -> bool:
    gid = _by_user.get(user_id)
    if gid is None:
        return False
    match = _games.get(gid)
    return match is not None and not match.finished


@dataclass
class Match:
    id: int
    guild_id: int
    channel_id: int
    p1: int
    p2: int
    p1_name: str
    p2_name: str
    bet: int
    vs_bot: bool = False
    busy: bool = False
    held: bool = False
    turn: int = P1
    board: list[list[int]] = field(default_factory=lambda: [[EMPTY] * COLS for _ in range(ROWS)])
    finished: bool = False
    winner: int = 0
    reason: str = ""
    last_col: int = -1
    last_row: int = -1

    def piece_of(self, user_id: int) -> int:
        if user_id == self.p1:
            return P1
        if not self.vs_bot and user_id == self.p2:
            return P2
        return EMPTY

    def name_of(self, piece: int) -> str:
        if piece == P1:
            return self.p1_name
        if piece == P2:
            return self.p2_name
        return "\u2014"

    def column_open(self, col: int) -> bool:
        return 0 <= col < COLS and self.board[ROWS - 1][col] == EMPTY

    def drop(self, col: int, piece: int) -> int | None:
        if not self.column_open(col):
            return None
        for row in range(ROWS):
            if self.board[row][col] == EMPTY:
                self.board[row][col] = piece
                self.last_col = col
                self.last_row = row
                return row
        return None

    def is_full(self) -> bool:
        return all(self.board[ROWS - 1][c] != EMPTY for c in range(COLS))

    def has_win(self, piece: int) -> bool:
        b = self.board
        for r in range(ROWS):
            for c in range(COLS):
                if b[r][c] != piece:
                    continue
                if c + 3 < COLS and all(b[r][c + i] == piece for i in range(4)):
                    return True
                if r + 3 < ROWS and all(b[r + i][c] == piece for i in range(4)):
                    return True
                if r + 3 < ROWS and c + 3 < COLS and all(b[r + i][c + i] == piece for i in range(4)):
                    return True
                if r + 3 < ROWS and c - 3 >= 0 and all(b[r + i][c - i] == piece for i in range(4)):
                    return True
        return False


def _unbind(match: Match) -> None:
    _games.pop(match.id, None)
    _by_user.pop(match.p1, None)
    if not match.vs_bot:
        _by_user.pop(match.p2, None)


def _bind(match: Match) -> None:
    _games[match.id] = match
    _by_user[match.p1] = match.id
    if not match.vs_bot:
        _by_user[match.p2] = match.id


def _hold_start(match: Match) -> str:
    ok1, _bal1, err1 = ai_coins.hold_bet(match.p1, match.bet)
    if not ok1:
        return f"{match.p1_name}: {err1}"
    if match.vs_bot:
        match.held = True
        return ""
    ok2, _bal2, err2 = ai_coins.hold_bet(match.p2, match.bet)
    if not ok2:
        ai_coins.settle_hand(match.p1, match.bet)
        return f"{match.p2_name}: {err2}"
    match.held = True
    return ""


def _settle(match: Match) -> None:
    if not match.held:
        return
    if match.vs_bot:
        if match.winner == P1:
            ai_coins.settle_hand(match.p1, match.bet * 2)
        elif match.winner == P2:
            ai_coins.settle_hand(match.p1, 0)
        else:
            ai_coins.settle_hand(match.p1, match.bet)
        match.held = False
        return
    if match.winner == P1:
        ai_coins.settle_hand(match.p1, match.bet * 2)
        ai_coins.settle_hand(match.p2, 0)
    elif match.winner == P2:
        ai_coins.settle_hand(match.p2, match.bet * 2)
        ai_coins.settle_hand(match.p1, 0)
    else:
        ai_coins.settle_hand(match.p1, match.bet)
        ai_coins.settle_hand(match.p2, match.bet)
    match.held = False


def _finish(match: Match, *, winner: int = 0, reason: str = "") -> None:
    match.finished = True
    match.winner = winner
    match.reason = reason
    _settle(match)
    _last_bet[match.p1] = match.bet
    _unbind(match)


def _after_drop(match: Match, piece: int) -> None:
    if match.has_win(piece):
        _finish(
            match,
            winner=piece,
            reason=f"{match.name_of(piece)} connects four and takes {match.bet * 2} Aether Coins.",
        )
    elif match.is_full():
        _finish(match, winner=0, reason="Draw. Stakes returned.")
    else:
        match.turn = P2 if match.turn == P1 else P1


def _bot_move(match: Match) -> None:
    if match.finished or not match.vs_bot or match.turn != P2:
        return
    col = choose_column(match.board, P2)
    if match.drop(col, P2) is None:
        _finish(match, winner=P1, reason="Aetherion could not move. Stake returned.")
        return
    _after_drop(match, P2)


def _embed(match: Match, *, waiting: bool = False, balance: int | None = None) -> discord.Embed:
    pot = match.bet if match.vs_bot else match.bet * 2
    if waiting:
        color = EMBED_WAIT
        title = "Connect Four \u00b7 challenge"
        status = f"{match.p2_name} \u2014 Accept or Decline."
    elif match.finished:
        if match.winner:
            color = EMBED_WIN if match.winner == P1 else EMBED_DEAD
            title = "Connect Four \u00b7 four in a row"
        elif match.reason and "Draw" not in match.reason:
            color = EMBED_DEAD
            title = "Connect Four \u00b7 over"
        else:
            color = EMBED_DRAW
            title = "Connect Four \u00b7 draw"
        status = match.reason
    else:
        color = EMBED_PLAY
        title = "Connect Four"
        status = f"{DISC[match.turn]} {match.name_of(match.turn)} to drop."

    embed = discord.Embed(title=title, color=color)
    embed.add_field(name=f"{DISC[P1]} Red", value=match.p1_name, inline=True)
    embed.add_field(name=f"{DISC[P2]} Gold", value=match.p2_name, inline=True)
    embed.add_field(name="Pot" if not match.vs_bot else "Stake", value=f"{pot} Aether Coins", inline=True)
    if balance is not None:
        embed.add_field(name="Wallet", value=f"{balance} Aether Coins", inline=True)
    embed.set_image(url=f"attachment://{TABLE_NAME}")
    embed.set_footer(text=status)
    return embed


def _subtitle(match: Match, extra: str = "") -> str:
    if extra:
        return extra
    if match.finished:
        return match.reason or ""
    if match.turn == P1:
        return "Your move."
    return f"{match.p2_name} is choosing a column..."


def _table_file(
    match: Match,
    *,
    falling: tuple[int, int, int] | None = None,
    subtitle: str | None = None,
) -> discord.File | None:
    try:
        last = None
        if falling is None and match.last_row >= 0:
            last = (match.last_row, match.last_col)
        raw = render_board_png(
            match.board,
            subtitle=_subtitle(match) if subtitle is None else subtitle,
            last=last,
            winner=match.winner if match.finished else 0,
            falling=falling,
        )
        return discord.File(io.BytesIO(raw), filename=TABLE_NAME)
    except Exception:
        logger.exception("connect4 board render failed")
        return None


async def _animate_fall(
    interaction: discord.Interaction,
    match: Match,
    view: discord.ui.View,
    *,
    piece: int,
    col: int,
    landing_row: int,
    caption: str,
) -> None:
    parked = match.board[landing_row][col]
    match.board[landing_row][col] = EMPTY
    try:
        raw, seconds = render_fall_gif(
            match.board,
            piece=piece,
            col=col,
            landing_row=landing_row,
            subtitle=caption,
        )
        table = discord.File(io.BytesIO(raw), filename=TABLE_GIF)
        embed = _embed(match, balance=ai_coins.get_balance(match.p1))
        embed.set_footer(text=caption)
        embed.set_image(url=f"attachment://{TABLE_GIF}")
        await _publish(interaction, embed=embed, view=view, table=table, edit=True)
        await asyncio.sleep(max(0.35, seconds))
    finally:
        match.board[landing_row][col] = parked
    still = _table_file(match, subtitle=caption)
    landed = _embed(match, balance=ai_coins.get_balance(match.p1))
    landed.set_footer(text=caption)
    await _publish(interaction, embed=landed, view=view, table=still, edit=True)


async def _publish(
    interaction: discord.Interaction,
    *,
    embed: discord.Embed,
    view: discord.ui.View | None,
    table: discord.File | None,
    edit: bool,
    content: str | None = None,
) -> discord.Message | None:
    kwargs: dict = {"embed": embed, "view": view, "content": content}
    if not interaction.response.is_done():
        if edit:
            if table is not None:
                kwargs["attachments"] = [table]
            await interaction.response.edit_message(**kwargs)
        else:
            if table is not None:
                kwargs["file"] = table
            await interaction.response.send_message(**kwargs)
        try:
            return await interaction.original_response()
        except Exception:
            return None
    if table is not None:
        kwargs["attachments"] = [table]
    await interaction.edit_original_response(**kwargs)
    try:
        return await interaction.original_response()
    except Exception:
        return None


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
        bet = int(_last_bet.get(self.user_id) or ai_coins.DEFAULT_BET)
        await _start_vs_bot(interaction, user_id=self.user_id, name=interaction.user.display_name, bet=bet, edit=True)


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

    def _match(self) -> Match | None:
        return _games.get(self.match_id)

    def _sync_columns(self, match: Match) -> None:
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

    def _end_view(self, match: Match) -> discord.ui.View | None:
        self._sync_columns(match)
        self.stop()
        if match.vs_bot:
            return ReplayView(match.p1)
        return self

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
            self._sync_columns(match)
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True
            land_row = match.last_row
            land_col = match.last_col
            who = match.name_of(piece)
            await _animate_fall(
                interaction,
                match,
                self,
                piece=piece,
                col=land_col,
                landing_row=land_row,
                caption=f"{who} drops in column {land_col + 1}.",
            )
            _after_drop(match, piece)
            if not match.finished and match.vs_bot and match.turn == P2:
                think_embed = _embed(match, balance=ai_coins.get_balance(match.p1))
                think_embed.set_footer(text="Aetherion is choosing a column...")
                await _publish(interaction, embed=think_embed, view=self, table=None, edit=True)
                await asyncio.sleep(THINK_SLEEP)
                _bot_move(match)
                if match.last_row >= 0:
                    await _animate_fall(
                        interaction,
                        match,
                        self,
                        piece=P2,
                        col=match.last_col,
                        landing_row=match.last_row,
                        caption="Aetherion drops.",
                    )
            next_view: discord.ui.View | None = self
            if match.finished:
                next_view = self._end_view(match)
            else:
                match.busy = False
                self._sync_columns(match)
            pocket = ai_coins.get_balance(match.p1)
            table = _table_file(match)
            embed = _embed(match, balance=pocket)
            await _publish(interaction, embed=embed, view=next_view, table=table, edit=True)

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
        if piece == EMPTY:
            await interaction.response.send_message("This is not your board.", ephemeral=True)
            return
        winner = P2 if piece == P1 else P1
        _finish(
            match,
            winner=winner,
            reason=f"{match.name_of(piece)} forfeits. {match.name_of(winner)} takes the pot.",
        )
        next_view = self._end_view(match)
        pocket = ai_coins.get_balance(match.p1)
        table = _table_file(match)
        embed = _embed(match, balance=pocket)
        await _publish(interaction, embed=embed, view=next_view, table=table, edit=True)

    async def on_timeout(self) -> None:
        match = self._match()
        if match is None or match.finished:
            return
        current = match.turn
        winner = P2 if current == P1 else P1
        _finish(
            match,
            winner=winner,
            reason=f"{match.name_of(current)} ran out of time. {match.name_of(winner)} takes the pot.",
        )
        view = ReplayView(match.p1) if match.vs_bot else self
        if self.message is not None:
            try:
                table = _table_file(match)
                embed = _embed(match, balance=ai_coins.get_balance(match.p1))
                kwargs = {"embed": embed, "view": view}
                if table is not None:
                    kwargs["attachments"] = [table]
                await self.message.edit(**kwargs)
            except Exception:
                logger.exception("connect4 timeout edit failed id=%s", match.id)


class ChallengeView(discord.ui.View):
    def __init__(self, match_id: int):
        super().__init__(timeout=90)
        self.match_id = match_id
        self.message: discord.Message | None = None

    def _match(self) -> Match | None:
        return _games.get(self.match_id)

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
        err = _hold_start(match)
        if err:
            _finish(match, reason=err)
            table = _table_file(match)
            await _publish(interaction, embed=_embed(match), view=None, table=table, edit=True)
            return
        self.stop()
        view = PlayView(match.id)
        view._sync_columns(match)
        table = _table_file(match)
        embed = _embed(match, balance=ai_coins.get_balance(match.p1))
        message = await _publish(interaction, embed=embed, view=view, table=table, edit=True)
        view.message = message

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.secondary)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        match = self._match()
        if match is None or match.finished:
            await interaction.response.send_message("That challenge is gone.", ephemeral=True)
            return
        who = match.p1_name if interaction.user.id == match.p1 else match.p2_name
        _finish(match, reason=f"{who} called it off. No coins moved.")
        self.stop()
        table = _table_file(match)
        await _publish(interaction, embed=_embed(match), view=None, table=table, edit=True)

    async def on_timeout(self) -> None:
        match = self._match()
        if match is None or match.finished or match.held:
            return
        _finish(match, reason="Challenge timed out. No coins moved.")
        if self.message is not None:
            try:
                table = _table_file(match)
                kwargs = {"embed": _embed(match), "view": None}
                if table is not None:
                    kwargs["attachments"] = [table]
                await self.message.edit(**kwargs)
            except Exception:
                logger.exception("connect4 challenge timeout edit failed id=%s", match.id)


async def _start_vs_bot(
    interaction: discord.Interaction,
    *,
    user_id: int,
    name: str,
    bet: int,
    edit: bool,
) -> None:
    if _player_busy(user_id):
        msg = "Finish your current Connect Four first."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
        return
    match = Match(
        id=_new_id(),
        guild_id=interaction.guild.id if interaction.guild else 0,
        channel_id=interaction.channel_id or 0,
        p1=user_id,
        p2=0,
        p1_name=name,
        p2_name="Aetherion",
        bet=int(bet),
        vs_bot=True,
    )
    err = _hold_start(match)
    if err:
        if interaction.response.is_done():
            await interaction.followup.send(err, ephemeral=True)
        else:
            await interaction.response.send_message(err, ephemeral=True)
        return
    _bind(match)
    _last_bet[user_id] = int(bet)
    view = PlayView(match.id)
    view._sync_columns(match)
    table = _table_file(match)
    embed = _embed(match, balance=ai_coins.get_balance(user_id))
    message = await _publish(
        interaction,
        embed=embed,
        view=view,
        table=table,
        edit=edit,
        content=None,
    )
    view.message = message


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
        if _player_busy(challenger.id):
            await interaction.response.send_message("Finish your current Connect Four first.", ephemeral=True)
            return

        if vs_bot:
            if bet == ai_coins.DEFAULT_BET and challenger.id in _last_bet:
                bet = int(_last_bet[challenger.id])
            await _start_vs_bot(
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
        if _player_busy(opponent.id):
            await interaction.response.send_message(
                f"**{opponent.display_name}** is already on a board.", ephemeral=True
            )
            return

        p1_bal = ai_coins.get_balance(challenger.id)
        p2_bal = ai_coins.get_balance(opponent.id)
        if bet > p1_bal:
            await interaction.response.send_message(
                f"You only have {p1_bal} Aether Coins.", ephemeral=True
            )
            return
        if bet > p2_bal:
            await interaction.response.send_message(
                f"**{opponent.display_name}** only has {p2_bal} Aether Coins.", ephemeral=True
            )
            return

        match = Match(
            id=_new_id(),
            guild_id=interaction.guild.id,
            channel_id=interaction.channel_id or 0,
            p1=challenger.id,
            p2=opponent.id,
            p1_name=challenger.display_name,
            p2_name=opponent.display_name,
            bet=int(bet),
            vs_bot=False,
        )
        _bind(match)
        view = ChallengeView(match.id)
        table = _table_file(match)
        embed = _embed(match, waiting=True)
        message = await _publish(
            interaction,
            embed=embed,
            view=view,
            table=table,
            edit=False,
            content=f"{opponent.mention} \u2014 **{challenger.display_name}** wants Connect Four for **{bet}** Aether Coins each.",
        )
        view.message = message
