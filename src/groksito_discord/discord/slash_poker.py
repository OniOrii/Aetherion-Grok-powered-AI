"""Texas Hold'em for 2-4 seats. Friends and/or Aetherion. Aether Coin buy-in."""
from __future__ import annotations

import asyncio
import io
import logging
from dataclasses import dataclass, field
from itertools import combinations
from random import SystemRandom

import discord

from . import ai_coins
from .poker_table import render_hole_png, render_table_png

logger = logging.getLogger("aetherion.slash_poker")

_rng = SystemRandom()

BOT_ID = 0
BOT_NAME = "Aetherion"
MAX_SEATS = 4
TABLE_NAME = "poker.png"
HOLE_NAME = "hole.png"
THINK_SLEEP = 0.7

EMBED_WAIT = 0xC9A227
EMBED_PLAY = 0x3D6B9B
EMBED_WIN = 0x3D9B64
EMBED_DEAD = 0xC45C4A

RANKS = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
SUITS = ["S", "H", "D", "C"]
RANK_SYM = {11: "J", 12: "Q", 13: "K", 14: "A"}
SUIT_SYM = {"S": "\u2660", "H": "\u2665", "D": "\u2666", "C": "\u2663"}

HAND_NAMES = (
    "High card",
    "Pair",
    "Two pair",
    "Three of a kind",
    "Straight",
    "Flush",
    "Full house",
    "Four of a kind",
    "Straight flush",
)

_tables: dict[int, "Table"] = {}
_by_user: dict[int, int] = {}
_next_id = 1
_last_bet: dict[int, int] = {}


def _new_id() -> int:
    global _next_id
    gid = _next_id
    _next_id += 1
    return gid


def _card_label(card) -> str:
    rank, suit = card
    return f"{RANK_SYM.get(rank, str(rank))}{SUIT_SYM[suit]}"


def _new_deck():
    deck = [(r, s) for s in SUITS for r in RANKS]
    _rng.shuffle(deck)
    return deck


def _hand_score(cards) -> tuple:
    ranks = sorted((c[0] for c in cards), reverse=True)
    suits = [c[1] for c in cards]
    flush = len(set(suits)) == 1
    uniq = sorted(set(ranks), reverse=True)
    straight = False
    top = 0
    if len(uniq) == 5:
        if uniq[0] - uniq[4] == 4:
            straight = True
            top = uniq[0]
        elif uniq == [14, 5, 4, 3, 2]:
            straight = True
            top = 5
    counts: dict[int, int] = {}
    for r in ranks:
        counts[r] = counts.get(r, 0) + 1
    groups = sorted(((n, r) for r, n in counts.items()), reverse=True)
    kick = tuple(
        r
        for n, r in sorted(((n, r) for r, n in counts.items()), key=lambda x: (x[0], x[1]), reverse=True)
        for _ in range(n)
    )
    if straight and flush:
        return (8, top)
    if groups[0][0] == 4:
        return (7, groups[0][1], groups[1][1])
    if groups[0][0] == 3 and groups[1][0] == 2:
        return (6, groups[0][1], groups[1][1])
    if flush:
        return (5, *ranks)
    if straight:
        return (4, top)
    if groups[0][0] == 3:
        return (3, groups[0][1], *kick)
    if groups[0][0] == 2 and groups[1][0] == 2:
        high_p = max(groups[0][1], groups[1][1])
        low_p = min(groups[0][1], groups[1][1])
        kicker = groups[2][1]
        return (2, high_p, low_p, kicker)
    if groups[0][0] == 2:
        return (1, groups[0][1], *kick)
    return (0, *ranks)


def best_hand(hole, board) -> tuple:
    pool = list(hole) + list(board)
    if len(pool) < 5:
        return _hand_score((pool + [(0, "S")] * 5)[:5])
    return max(_hand_score(combo) for combo in combinations(pool, 5))


def _strength(hole, board) -> float:
    if not hole:
        return 0.0
    if len(board) < 3:
        a, b = hole[0][0], hole[1][0]
        hi, lo = max(a, b), min(a, b)
        pair = 0.62 if a == b else 0.0
        suited = 0.08 if hole[0][1] == hole[1][1] else 0.0
        connected = 0.06 if abs(a - b) in (1, 2) else 0.0
        high = (hi - 2) / 12 * 0.38
        return min(0.96, pair + suited + connected + high + (0.04 if lo >= 10 else 0))
    score = best_hand(hole, board)
    return min(0.99, 0.08 + score[0] / 8 * 0.82 + (score[1] if len(score) > 1 else 0) / 140)


def _blinds(buyin: int) -> tuple[int, int]:
    if buyin < 40:
        return 0, 0
    return 10, 20


def _raise_step(buyin: int) -> int:
    _sb, bb = _blinds(buyin)
    return bb if bb else 10


@dataclass
class Seat:
    user_id: int
    name: str
    stack: int
    is_bot: bool = False
    hole: list = field(default_factory=list)
    bet: int = 0
    folded: bool = False
    all_in: bool = False
    acted: bool = False
    held: bool = False

    def snapshot(self) -> dict:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "stack": self.stack,
            "bet": self.bet,
            "folded": self.folded,
            "all_in": self.all_in,
            "hole": list(self.hole),
        }


@dataclass
class Table:
    id: int
    guild_id: int
    channel_id: int
    host_id: int
    buyin: int
    seats: list[Seat] = field(default_factory=list)
    deck: list = field(default_factory=list)
    board: list = field(default_factory=list)
    pot: int = 0
    street: str = "lobby"
    dealer: int = 0
    actor: int = 0
    current_bet: int = 0
    finished: bool = False
    busy: bool = False
    reason: str = ""
    winner_ids: list[int] = field(default_factory=list)

    def seat_of(self, user_id: int) -> Seat | None:
        for s in self.seats:
            if s.user_id == user_id:
                return s
        return None

    def live(self) -> list[Seat]:
        return [s for s in self.seats if not s.folded]

    def humans(self) -> list[Seat]:
        return [s for s in self.seats if not s.is_bot]

    def can_join(self, user_id: int) -> bool:
        return (
            not self.finished
            and self.street == "lobby"
            and self.seat_of(user_id) is None
            and len(self.seats) < MAX_SEATS
        )


def _player_busy(user_id: int) -> bool:
    tid = _by_user.get(user_id)
    if tid is None:
        return False
    table = _tables.get(tid)
    return table is not None and not table.finished


def _bind(table: Table) -> None:
    _tables[table.id] = table
    for s in table.humans():
        _by_user[s.user_id] = table.id


def _unbind(table: Table) -> None:
    _tables.pop(table.id, None)
    for s in table.humans():
        if _by_user.get(s.user_id) == table.id:
            _by_user.pop(s.user_id, None)


def _hold_seat(seat: Seat, amount: int) -> str:
    if seat.is_bot:
        seat.held = True
        return ""
    ai_coins.refund_stale_pending(seat.user_id)
    ok, _bal, err = ai_coins.hold_bet(seat.user_id, amount)
    if not ok:
        return err
    seat.held = True
    return ""


def _refund_seat(seat: Seat) -> None:
    if seat.held and not seat.is_bot:
        ai_coins.settle_hand(seat.user_id, seat.stack)
    seat.held = False


def _settle_table(table: Table) -> None:
    for seat in table.humans():
        if not seat.held:
            continue
        ai_coins.settle_hand(seat.user_id, max(0, seat.stack))
        seat.held = False


def _finish(table: Table, reason: str, winners: list[int] | None = None) -> None:
    table.finished = True
    table.street = "showdown"
    table.reason = reason
    table.winner_ids = winners or []
    _settle_table(table)
    _last_bet[table.host_id] = table.buyin
    _unbind(table)


def _next_index(table: Table, start: int) -> int | None:
    n = len(table.seats)
    if n == 0:
        return None
    for step in range(1, n + 1):
        i = (start + step) % n
        s = table.seats[i]
        if not s.folded and not s.all_in:
            return i
    return None


def _post_blinds(table: Table) -> None:
    sb_amt, bb_amt = _blinds(table.buyin)
    n = len(table.seats)
    if n == 0:
        return
    if n == 2:
        sb_i = table.dealer
        bb_i = 1 - table.dealer
    else:
        sb_i = (table.dealer + 1) % n
        bb_i = (table.dealer + 2) % n

    def post(i: int, amt: int) -> None:
        if amt <= 0:
            return
        seat = table.seats[i]
        pay = min(seat.stack, amt)
        seat.stack -= pay
        seat.bet += pay
        table.pot += pay
        if seat.stack == 0:
            seat.all_in = True

    post(sb_i, sb_amt)
    post(bb_i, bb_amt)
    table.current_bet = max((s.bet for s in table.seats), default=0)
    if n == 2:
        nxt = _next_index(table, (sb_i - 1) % n)
    else:
        nxt = _next_index(table, bb_i)
    table.actor = nxt if nxt is not None else 0


def _deal_holes(table: Table) -> None:
    table.deck = _new_deck()
    table.board = []
    for seat in table.seats:
        seat.hole = [table.deck.pop(), table.deck.pop()]
        seat.bet = 0
        seat.folded = False
        seat.all_in = False
        seat.acted = False
    table.pot = 0
    table.street = "preflop"
    table.current_bet = 0
    _post_blinds(table)
    for seat in table.seats:
        seat.acted = False
    if table.seats and (table.seats[table.actor].all_in or _street_over(table)):
        _after_action(table)


def _street_over(table: Table) -> bool:
    live = table.live()
    if len(live) <= 1:
        return True
    needy = [s for s in live if not s.all_in]
    if not needy:
        return True
    if any(s.bet < table.current_bet and not s.all_in for s in live):
        return False
    return all(s.acted or s.all_in for s in needy)


def _advance_street(table: Table) -> None:
    for s in table.seats:
        s.bet = 0
        s.acted = False
    table.current_bet = 0
    if table.street == "preflop":
        table.board = [table.deck.pop(), table.deck.pop(), table.deck.pop()]
        table.street = "flop"
    elif table.street == "flop":
        table.board.append(table.deck.pop())
        table.street = "turn"
    elif table.street == "turn":
        table.board.append(table.deck.pop())
        table.street = "river"
    else:
        _showdown(table)
        return
    nxt = _next_index(table, table.dealer)
    table.actor = nxt if nxt is not None else 0
    if _street_over(table):
        _advance_street(table)


def _award_pot(table: Table, winners: list[Seat]) -> None:
    if not winners:
        return
    share = table.pot // len(winners)
    extra = table.pot - share * len(winners)
    for i, w in enumerate(winners):
        w.stack += share + (extra if i == 0 else 0)
    table.pot = 0


def _showdown(table: Table) -> None:
    live = table.live()
    if len(live) == 1:
        winner = live[0]
        _award_pot(table, [winner])
        _finish(table, f"{winner.name} takes the pot. Everyone else folded.", [winner.user_id])
        return
    ranked = sorted(live, key=lambda s: best_hand(s.hole, table.board), reverse=True)
    best = best_hand(ranked[0].hole, table.board)
    winners = [s for s in ranked if best_hand(s.hole, table.board) == best]
    names = " & ".join(w.name for w in winners)
    label = HAND_NAMES[best[0]]
    _award_pot(table, winners)
    _finish(table, f"{names} wins with {label}.", [w.user_id for w in winners])


def _one_left(table: Table) -> bool:
    return len(table.live()) == 1


def _apply_action(table: Table, seat: Seat, action: str) -> str:
    to_call = max(0, table.current_bet - seat.bet)
    step = _raise_step(table.buyin)
    raise_to = table.current_bet + step
    if action == "fold":
        seat.folded = True
        seat.acted = True
        return f"{seat.name} folds."
    if action == "check":
        if to_call > 0:
            action = "call"
        else:
            seat.acted = True
            return f"{seat.name} checks."
    if action == "call":
        pay = min(seat.stack, to_call)
        seat.stack -= pay
        seat.bet += pay
        table.pot += pay
        seat.acted = True
        if seat.stack == 0:
            seat.all_in = True
            return f"{seat.name} is all-in."
        return f"{seat.name} calls {pay}." if pay else f"{seat.name} checks."
    if action == "raise":
        target = max(raise_to, table.current_bet + step)
        need = target - seat.bet
        if need >= seat.stack or seat.stack <= to_call:
            action = "allin"
        else:
            seat.stack -= need
            seat.bet += need
            table.pot += need
            table.current_bet = seat.bet
            seat.acted = True
            for other in table.seats:
                if other is not seat and not other.folded and not other.all_in:
                    other.acted = False
            return f"{seat.name} raises to {seat.bet}."
    if action == "allin":
        pay = seat.stack
        seat.bet += pay
        table.pot += pay
        seat.stack = 0
        seat.all_in = True
        seat.acted = True
        if seat.bet > table.current_bet:
            table.current_bet = seat.bet
            for other in table.seats:
                if other is not seat and not other.folded and not other.all_in:
                    other.acted = False
        return f"{seat.name} is all-in."
    seat.acted = True
    return f"{seat.name} checks."


def _bot_action(table: Table, seat: Seat) -> str:
    to_call = max(0, table.current_bet - seat.bet)
    strength = _strength(seat.hole, table.board)
    pot_odds = (to_call / (table.pot + to_call)) if to_call else 0.0
    roll = _rng.random()
    if to_call == 0:
        if strength > 0.74 and roll < 0.42:
            return "raise"
        if strength < 0.30 and roll < 0.10:
            return "raise"
        return "check"
    if strength < 0.20 and to_call > max(20, seat.stack // 3):
        return "fold"
    if strength > 0.80 and seat.stack > to_call and roll < 0.38:
        return "raise"
    if strength + 0.10 >= pot_odds or strength > 0.40:
        return "call"
    if roll < 0.12 and strength > 0.22:
        return "call"
    return "fold"


def _after_action(table: Table) -> None:
    if table.finished:
        return
    if _one_left(table):
        _showdown(table)
        return
    if not _street_over(table):
        nxt = _next_index(table, table.actor)
        if nxt is None:
            _showdown(table)
            return
        table.actor = nxt
        return
    if table.street == "river":
        _showdown(table)
        return
    _advance_street(table)
    while not table.finished and table.street != "showdown" and _street_over(table):
        if table.street == "river":
            _showdown(table)
            return
        _advance_street(table)


def _embed(table: Table, *, waiting: bool = False) -> discord.Embed:
    if waiting or table.street == "lobby":
        color = EMBED_WAIT
        title = "Poker \u00b7 table"
        status = table.reason or "Join a seat, then Deal when 2-4 people are ready."
    elif table.finished:
        color = EMBED_WIN if table.winner_ids else EMBED_DEAD
        title = "Poker \u00b7 pot awarded"
        status = table.reason
    else:
        color = EMBED_PLAY
        title = "Poker \u00b7 Texas Hold'em"
        actor = table.seats[table.actor] if table.seats else None
        status = f"{actor.name} to act \u00b7 {table.street}" if actor else table.street
    embed = discord.Embed(title=title, color=color)
    names = "\n".join(
        f"{'\u00b7 ' if (not table.finished and i == table.actor and table.street != 'lobby') else ''}{s.name}"
        f" \u2014 {s.stack}"
        for i, s in enumerate(table.seats)
    ) or "Empty"
    embed.add_field(name=f"Seats {len(table.seats)}/{MAX_SEATS}", value=names, inline=True)
    embed.add_field(name="Buy-in", value=f"{table.buyin} Aether Coins", inline=True)
    embed.add_field(name="Pot", value=f"{table.pot} Aether Coins", inline=True)
    embed.set_image(url=f"attachment://{TABLE_NAME}")
    embed.set_footer(text=status)
    return embed


def _table_file(table: Table, subtitle: str = "") -> discord.File | None:
    try:
        actor_id = None
        if not table.finished and table.street not in ("lobby", "showdown") and table.seats:
            actor_id = table.seats[table.actor].user_id
        raw = render_table_png(
            [s.snapshot() for s in table.seats],
            table.board,
            pot=table.pot,
            street=table.street,
            subtitle=subtitle or table.reason,
            actor_id=actor_id,
            reveal=table.finished,
        )
        return discord.File(io.BytesIO(raw), filename=TABLE_NAME)
    except Exception:
        logger.exception("poker table render failed")
        return None


async def _publish(interaction: discord.Interaction, *, embed, view, table=None, edit=True, ephemeral=False):
    kwargs = {"embed": embed, "view": view}
    if not interaction.response.is_done():
        if table is not None:
            if edit:
                kwargs["attachments"] = [table]
            else:
                kwargs["file"] = table
        if edit:
            await interaction.response.edit_message(**kwargs)
        else:
            await interaction.response.send_message(**kwargs, ephemeral=ephemeral)
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


async def _dm_holes(interaction: discord.Interaction, table: Table) -> None:
    for seat in table.humans():
        try:
            raw = render_hole_png(seat.hole)
            file = discord.File(io.BytesIO(raw), filename=HOLE_NAME)
            embed = discord.Embed(
                title="Your hole cards",
                description="  ".join(_card_label(c) for c in seat.hole),
                color=EMBED_PLAY,
            )
            embed.set_image(url=f"attachment://{HOLE_NAME}")
            await interaction.followup.send(
                content=f"{seat.name}, only you can see this.",
                embed=embed,
                file=file,
                ephemeral=True,
            )
        except Exception:
            logger.exception("poker hole card send failed user=%s", seat.user_id)


async def _run_bots(interaction: discord.Interaction, table: Table, view: discord.ui.View) -> None:
    guard = 0
    while (
        not table.finished
        and table.street != "lobby"
        and table.seats
        and table.seats[table.actor].is_bot
        and guard < 16
    ):
        guard += 1
        seat = table.seats[table.actor]
        think = _embed(table)
        think.set_footer(text="Aetherion is deciding...")
        await _publish(
            interaction,
            embed=think,
            view=view,
            table=_table_file(table, "Aetherion is deciding..."),
            edit=True,
        )
        await asyncio.sleep(THINK_SLEEP)
        line = _apply_action(table, seat, _bot_action(table, seat))
        _after_action(table)
        table.reason = line


class LobbyView(discord.ui.View):
    def __init__(self, table_id: int):
        super().__init__(timeout=180)
        self.table_id = table_id
        self.message: discord.Message | None = None

    def _table(self) -> Table | None:
        return _tables.get(self.table_id)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        table = self._table()
        if table is None or table.finished:
            await interaction.response.send_message("That table is gone.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Join", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        table = self._table()
        if table is None:
            await interaction.response.send_message("That table is gone.", ephemeral=True)
            return
        uid = interaction.user.id
        if _player_busy(uid) and table.seat_of(uid) is None:
            await interaction.response.send_message("You already have a hand in progress.", ephemeral=True)
            return
        if not table.can_join(uid):
            await interaction.response.send_message("You cannot join this table.", ephemeral=True)
            return
        seat = Seat(uid, interaction.user.display_name, table.buyin)
        err = _hold_seat(seat, table.buyin)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        table.seats.append(seat)
        _bind(table)
        await _publish(
            interaction,
            embed=_embed(table, waiting=True),
            view=self,
            table=_table_file(table, "Waiting for Deal."),
            edit=True,
        )

    @discord.ui.button(label="Seat Aetherion", style=discord.ButtonStyle.primary)
    async def seat_bot(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        table = self._table()
        if table is None:
            return
        if interaction.user.id != table.host_id:
            await interaction.response.send_message("Only the host can seat Aetherion.", ephemeral=True)
            return
        if table.seat_of(BOT_ID) is not None:
            await interaction.response.send_message("Aetherion is already seated.", ephemeral=True)
            return
        if len(table.seats) >= MAX_SEATS:
            await interaction.response.send_message("The table is full.", ephemeral=True)
            return
        table.seats.append(Seat(BOT_ID, BOT_NAME, table.buyin, is_bot=True, held=True))
        await _publish(
            interaction,
            embed=_embed(table, waiting=True),
            view=self,
            table=_table_file(table, "Aetherion sits."),
            edit=True,
        )

    @discord.ui.button(label="Deal", style=discord.ButtonStyle.primary)
    async def deal(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        table = self._table()
        if table is None:
            return
        if interaction.user.id != table.host_id:
            await interaction.response.send_message("Only the host can deal.", ephemeral=True)
            return
        if len(table.seats) < 2:
            await interaction.response.send_message("Need at least two seats.", ephemeral=True)
            return
        _deal_holes(table)
        play = PlayView(table.id)
        await _publish(
            interaction,
            embed=_embed(table),
            view=play,
            table=_table_file(table, "Cards are out."),
            edit=True,
        )
        try:
            play.message = await interaction.original_response()
        except Exception:
            play.message = None
        await _dm_holes(interaction, table)
        await _run_bots(interaction, table, play)
        if table.finished:
            end = ReplayView(table.host_id)
            await _publish(interaction, embed=_embed(table), view=end, table=_table_file(table), edit=True)
        else:
            await _publish(interaction, embed=_embed(table), view=play, table=_table_file(table), edit=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        table = self._table()
        if table is None:
            return
        if interaction.user.id != table.host_id:
            await interaction.response.send_message("Only the host can cancel.", ephemeral=True)
            return
        for seat in list(table.seats):
            _refund_seat(seat)
        _finish(table, "Table cancelled. Buy-ins returned.")
        self.stop()
        await _publish(
            interaction,
            embed=_embed(table),
            view=None,
            table=_table_file(table, "Cancelled."),
            edit=True,
        )

    async def on_timeout(self) -> None:
        table = self._table()
        if table is None or table.finished or table.street != "lobby":
            return
        for seat in list(table.seats):
            _refund_seat(seat)
        _finish(table, "Lobby timed out. Buy-ins returned.")
        if self.message is not None:
            try:
                file = _table_file(table)
                kwargs = {"embed": _embed(table), "view": None}
                if file is not None:
                    kwargs["attachments"] = [file]
                await self.message.edit(**kwargs)
            except Exception:
                logger.exception("poker lobby timeout failed")


class ReplayView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=180)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This table is not yours.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.primary)
    async def play_again(self, interaction: discord.Interaction, button: discord.ui.Button):
        bet = int(_last_bet.get(self.user_id) or ai_coins.DEFAULT_BET)
        await _open_table(
            interaction,
            user_id=self.user_id,
            name=interaction.user.display_name,
            bet=bet,
            seat_bot=True,
            edit=True,
        )


class PlayView(discord.ui.View):
    def __init__(self, table_id: int):
        super().__init__(timeout=180)
        self.table_id = table_id
        self.message: discord.Message | None = None

    def _table(self) -> Table | None:
        return _tables.get(self.table_id)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        table = self._table()
        if table is None or table.finished:
            await interaction.response.send_message("This hand is over.", ephemeral=True)
            return False
        if table.seat_of(interaction.user.id) is None:
            await interaction.response.send_message("You are not seated.", ephemeral=True)
            return False
        return True

    async def _act(self, interaction: discord.Interaction, action: str) -> None:
        table = self._table()
        if table is None or table.finished:
            await interaction.response.send_message("This hand is over.", ephemeral=True)
            return
        if table.busy:
            await interaction.response.send_message("Wait a second.", ephemeral=True)
            return
        seat = table.seat_of(interaction.user.id)
        if seat is None or seat.folded:
            await interaction.response.send_message("You cannot act.", ephemeral=True)
            return
        if seat.all_in:
            await interaction.response.send_message("You are already all-in. Wait for the board.", ephemeral=True)
            return
        if table.seats[table.actor].user_id != interaction.user.id:
            await interaction.response.send_message("Wait for your turn.", ephemeral=True)
            return
        table.busy = True
        table.reason = _apply_action(table, seat, action)
        _after_action(table)
        await _run_bots(interaction, table, self)
        table.busy = False
        view: discord.ui.View | None = self
        if table.finished:
            self.stop()
            view = ReplayView(table.host_id)
        await _publish(interaction, embed=_embed(table), view=view, table=_table_file(table), edit=True)

    @discord.ui.button(label="Fold", style=discord.ButtonStyle.danger, row=0)
    async def fold(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._act(interaction, "fold")

    @discord.ui.button(label="Check / Call", style=discord.ButtonStyle.secondary, row=0)
    async def check_call(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._act(interaction, "check")

    @discord.ui.button(label="Raise", style=discord.ButtonStyle.primary, row=0)
    async def raise_bet(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._act(interaction, "raise")

    @discord.ui.button(label="All-in", style=discord.ButtonStyle.primary, row=0)
    async def allin(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._act(interaction, "allin")

    @discord.ui.button(label="My cards", style=discord.ButtonStyle.secondary, row=1)
    async def my_cards(self, interaction: discord.Interaction, button: discord.ui.Button):
        table = self._table()
        if table is None:
            await interaction.response.send_message("This hand is over.", ephemeral=True)
            return
        seat = table.seat_of(interaction.user.id)
        if seat is None or not seat.hole:
            await interaction.response.send_message("No hole cards yet.", ephemeral=True)
            return
        raw = render_hole_png(seat.hole)
        file = discord.File(io.BytesIO(raw), filename=HOLE_NAME)
        embed = discord.Embed(
            title="Your hole cards",
            description="  ".join(_card_label(c) for c in seat.hole),
            color=EMBED_PLAY,
        )
        embed.set_image(url=f"attachment://{HOLE_NAME}")
        await interaction.response.send_message(embed=embed, file=file, ephemeral=True)

    async def on_timeout(self) -> None:
        table = self._table()
        if table is None or table.finished or table.street == "lobby":
            return
        actor = table.seats[table.actor]
        if actor.is_bot:
            return
        table.reason = _apply_action(table, actor, "fold")
        _after_action(table)
        if self.message is not None:
            try:
                view = ReplayView(table.host_id) if table.finished else self
                file = _table_file(table)
                kwargs = {"embed": _embed(table), "view": view}
                if file is not None:
                    kwargs["attachments"] = [file]
                await self.message.edit(**kwargs)
            except Exception:
                logger.exception("poker turn timeout failed")


async def _open_table(
    interaction: discord.Interaction,
    *,
    user_id: int,
    name: str,
    bet: int,
    seat_bot: bool,
    edit: bool,
) -> None:
    err = ai_coins.amount_error(bet, ai_coins.MIN_BET, ai_coins.MAX_BET)
    if err:
        msg = err
        if not interaction.response.is_done():
            await interaction.response.send_message(msg, ephemeral=True)
        else:
            await interaction.followup.send(msg, ephemeral=True)
        return
    if _player_busy(user_id):
        msg = "You already have a hand in progress."
        if not interaction.response.is_done():
            await interaction.response.send_message(msg, ephemeral=True)
        else:
            await interaction.followup.send(msg, ephemeral=True)
        return
    table = Table(
        id=_new_id(),
        guild_id=interaction.guild.id if interaction.guild else 0,
        channel_id=interaction.channel.id if interaction.channel else 0,
        host_id=user_id,
        buyin=bet,
    )
    host = Seat(user_id, name, bet)
    hold_err = _hold_seat(host, bet)
    if hold_err:
        if not interaction.response.is_done():
            await interaction.response.send_message(hold_err, ephemeral=True)
        else:
            await interaction.followup.send(hold_err, ephemeral=True)
        return
    table.seats.append(host)
    if seat_bot:
        table.seats.append(Seat(BOT_ID, BOT_NAME, bet, is_bot=True, held=True))
    _bind(table)
    view = LobbyView(table.id)
    file = _table_file(table, "Lobby open.")
    embed = _embed(table, waiting=True)
    await _publish(interaction, embed=embed, view=view, table=file, edit=edit)
    try:
        view.message = await interaction.original_response()
    except Exception:
        view.message = None


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
        await _open_table(
            interaction,
            user_id=interaction.user.id,
            name=interaction.user.display_name,
            bet=int(bet),
            seat_bot=bool(vs_aetherion),
            edit=False,
        )
