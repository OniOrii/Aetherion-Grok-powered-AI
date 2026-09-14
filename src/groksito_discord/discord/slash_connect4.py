"""Two-player Connect Four with Aether Coin stakes."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import discord

from . import ai_coins

logger = logging.getLogger("aetherion.slash_connect4")

ROWS = 6
COLS = 7
EMPTY = 0
P1 = 1
P2 = 2

DISC = {EMPTY: "\u26ab", P1: "\U0001f534", P2: "\U0001f7e1"}
COL_HDR = "\u0031\ufe0f\u20e3\u0032\ufe0f\u20e3\u0033\ufe0f\u20e3\u0034\ufe0f\u20e3\u0035\ufe0f\u20e3\u0036\ufe0f\u20e3\u0037\ufe0f\u20e3"

EMBED_WAIT = 0xC9A227
EMBED_PLAY = 0x3D6B9B
EMBED_WIN = 0x3D9B64
EMBED_DRAW = 0x8A8F98
EMBED_DEAD = 0xC45C4A

_games: dict[int, "Match"] = {}
_by_user: dict[int, int] = {}
_next_id = 1


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
        if user_id == self.p2:
            return P2
        return EMPTY

    def name_of(self, piece: int) -> str:
        if piece == P1:
            return self.p1_name
        if piece == P2:
            return self.p2_name
        return "\u2014"

    def user_of(self, piece: int) -> int:
        return self.p1 if piece == P1 else self.p2

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
    _by_user.pop(match.p2, None)


def _bind(match: Match) -> None:
    _games[match.id] = match
    _by_user[match.p1] = match.id
    _by_user[match.p2] = match.id


def _board_text(match: Match) -> str:
    lines = [COL_HDR]
    for row in range(ROWS - 1, -1, -1):
        lines.append("".join(DISC[match.board[row][c]] for c in range(COLS)))
    return "\n".join(lines)


def _embed(match: Match, *, waiting: bool = False) -> discord.Embed:
    pot = match.bet * 2
    if waiting:
        color = EMBED_WAIT
        title = "Connect Four \u00b7 challenge"
        status = f"{match.p2_name} \u2014 Accept or Decline."
    elif match.finished:
        if match.winner:
            color = EMBED_WIN
            title = "Connect Four \u00b7 four in a row"
            status = match.reason or f"{match.name_of(match.winner)} wins the pot."
        elif match.reason:
            color = EMBED_DEAD
            title = "Connect Four \u00b7 over"
            status = match.reason
        else:
            color = EMBED_DRAW
            title = "Connect Four \u00b7 draw"
            status = "Board is full. Stakes returned."
    else:
        color = EMBED_PLAY
        title = "Connect Four"
        turn_name = match.name_of(match.turn)
        disc = DISC[match.turn]
        status = f"{disc} **{turn_name}** to drop."

    embed = discord.Embed(title=title, color=color, description=_board_text(match))
    embed.add_field(name=f"{DISC[P1]} Red", value=match.p1_name, inline=True)
    embed.add_field(name=f"{DISC[P2]} Gold", value=match.p2_name, inline=True)
    embed.add_field(name="Pot", value=f"{pot} Aether Coins", inline=True)
    embed.set_footer(text=status)
    return embed


def _hold_both(match: Match) -> str:
    ok1, _bal1, err1 = ai_coins.hold_bet(match.p1, match.bet)
    if not ok1:
        return f"{match.p1_name}: {err1}"
    ok2, _bal2, err2 = ai_coins.hold_bet(match.p2, match.bet)
    if not ok2:
        ai_coins.settle_hand(match.p1, match.bet)
        return f"{match.p2_name}: {err2}"
    match.held = True
    return ""


def _settle(match: Match) -> None:
    if not match.held:
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
    _unbind(match)


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
        forfeit = discord.ui.Button(
            label="Forfeit",
            style=discord.ButtonStyle.danger,
            row=1,
        )
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
        if interaction.user.id not in (match.p1, match.p2):
            await interaction.response.send_message("This is not your board.", ephemeral=True)
            return False
        return True

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
            if match.drop(col, piece) is None:
                await interaction.response.send_message("That column is full.", ephemeral=True)
                return
            if match.has_win(piece):
                _finish(
                    match,
                    winner=piece,
                    reason=f"{match.name_of(piece)} connects four and takes {match.bet * 2} Aether Coins.",
                )
            elif match.is_full():
                _finish(match, winner=0, reason="Draw. Both stakes returned.")
            else:
                match.turn = P2 if match.turn == P1 else P1
            self._sync_columns(match)
            if match.finished:
                self.stop()
            await interaction.response.edit_message(embed=_embed(match), view=self)

        return drop

    async def _forfeit(self, interaction: discord.Interaction) -> None:
        match = self._match()
        if match is None or match.finished:
            await interaction.response.send_message("This table is already over.", ephemeral=True)
            return
        piece = match.piece_of(interaction.user.id)
        winner = P2 if piece == P1 else P1
        _finish(
            match,
            winner=winner,
            reason=f"{match.name_of(piece)} forfeits. {match.name_of(winner)} takes the pot.",
        )
        self._sync_columns(match)
        self.stop()
        await interaction.response.edit_message(embed=_embed(match), view=self)

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
        self._sync_columns(match)
        if self.message is not None:
            try:
                await self.message.edit(embed=_embed(match), view=self)
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
        uid = interaction.user.id
        if uid not in (match.p1, match.p2):
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
        err = _hold_both(match)
        if err:
            _finish(match, reason=err)
            self.stop()
            await interaction.response.edit_message(embed=_embed(match), view=None)
            return
        self.stop()
        view = PlayView(match.id)
        view._sync_columns(match)
        await interaction.response.edit_message(embed=_embed(match), view=view)
        try:
            view.message = await interaction.original_response()
        except Exception:
            view.message = None

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.secondary)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        match = self._match()
        if match is None or match.finished:
            await interaction.response.send_message("That challenge is gone.", ephemeral=True)
            return
        if interaction.user.id not in (match.p1, match.p2):
            await interaction.response.send_message("This challenge is not for you.", ephemeral=True)
            return
        who = match.p1_name if interaction.user.id == match.p1 else match.p2_name
        _finish(match, reason=f"{who} called it off. No coins moved.")
        self.stop()
        await interaction.response.edit_message(embed=_embed(match), view=None)

    async def on_timeout(self) -> None:
        match = self._match()
        if match is None or match.finished or match.held:
            return
        _finish(match, reason="Challenge timed out. No coins moved.")
        if self.message is not None:
            try:
                await self.message.edit(embed=_embed(match), view=None)
            except Exception:
                logger.exception("connect4 challenge timeout edit failed id=%s", match.id)


def register_connect4(tree, is_guild_allowed) -> None:
    @tree.command(name="connect4", description="Challenge someone to Connect Four for Aether Coins")
    @discord.app_commands.describe(
        opponent="Who you want to play",
        bet=f"Each player's stake ({ai_coins.MIN_BET}\u2013{ai_coins.MAX_BET})",
    )
    @discord.app_commands.guild_only()
    async def connect4_slash(
        interaction: discord.Interaction,
        opponent: discord.Member,
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
        if opponent.id == challenger.id:
            await interaction.response.send_message("Pick another player.", ephemeral=True)
            return
        if opponent.bot:
            await interaction.response.send_message("Bots do not sit at this table.", ephemeral=True)
            return

        err = ai_coins.amount_error(bet, ai_coins.MIN_BET, ai_coins.MAX_BET)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        if _player_busy(challenger.id):
            await interaction.response.send_message("Finish your current Connect Four first.", ephemeral=True)
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
        )
        _bind(match)
        view = ChallengeView(match.id)
        await interaction.response.send_message(
            content=f"{opponent.mention} \u2014 **{challenger.display_name}** wants Connect Four for **{bet}** Aether Coins each.",
            embed=_embed(match, waiting=True),
            view=view,
        )
        try:
            view.message = await interaction.original_response()
        except Exception:
            view.message = None
