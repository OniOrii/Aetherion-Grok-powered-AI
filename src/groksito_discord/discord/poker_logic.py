"""Texas Hold'em engine for Aetherion poker."""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from random import SystemRandom

from . import ai_coins

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
HAND_NAMES = ("High card", "Pair", "Two pair", "Three of a kind", "Straight", "Flush", "Full house", "Four of a kind", "Straight flush")
_tables = {}
_by_user = {}
_next_id = 1
_last_bet = {}

def _new_id():
    global _next_id
    gid = _next_id
    _next_id += 1
    return gid

def _card_label(card):
    rank, suit = card
    return f"{RANK_SYM.get(rank, str(rank))}{SUIT_SYM[suit]}"

def _hole_text(seat):
    return " ".join(_card_label(c) for c in seat.hole) if seat.hole else "-"

def _new_deck():
    deck = [(r, s) for s in SUITS for r in RANKS]
    _rng.shuffle(deck)
    return deck

def _hand_score(cards):
    ranks = sorted((c[0] for c in cards), reverse=True)
    suits = [c[1] for c in cards]
    flush = len(set(suits)) == 1
    uniq = sorted(set(ranks), reverse=True)
    straight = False
    top = 0
    if len(uniq) == 5:
        if uniq[0] - uniq[4] == 4:
            straight, top = True, uniq[0]
        elif uniq == [14, 5, 4, 3, 2]:
            straight, top = True, 5
    counts = {}
    for r in ranks:
        counts[r] = counts.get(r, 0) + 1
    groups = sorted(((n, r) for r, n in counts.items()), reverse=True)
    kick = tuple(r for n, r in sorted(((n, r) for r, n in counts.items()), key=lambda x: (x[0], x[1]), reverse=True) for _ in range(n))
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
        return (2, max(groups[0][1], groups[1][1]), min(groups[0][1], groups[1][1]), groups[2][1])
    if groups[0][0] == 2:
        return (1, groups[0][1], *kick)
    return (0, *ranks)

def best_hand(hole, board):
    pool = list(hole) + list(board)
    if len(pool) < 5:
        return _hand_score((pool + [(0, "S")] * 5)[:5])
    return max(_hand_score(combo) for combo in combinations(pool, 5))

def _strength(hole, board):
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

def _blinds(buyin):
    return (0, 0) if buyin < 40 else (10, 20)

def _raise_step(buyin):
    return _blinds(buyin)[1] or 10

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
    def snapshot(self):
        return {"user_id": self.user_id, "name": self.name, "stack": self.stack, "bet": self.bet, "folded": self.folded, "all_in": self.all_in, "hole": list(self.hole)}

@dataclass
class Table:
    id: int
    guild_id: int
    channel_id: int
    host_id: int
    buyin: int
    seats: list = field(default_factory=list)
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
    winner_ids: list = field(default_factory=list)
    def seat_of(self, user_id):
        for s in self.seats:
            if s.user_id == user_id:
                return s
        return None
    def live(self):
        return [s for s in self.seats if not s.folded]
    def humans(self):
        return [s for s in self.seats if not s.is_bot]
    def can_join(self, user_id):
        return (not self.finished and self.street == "lobby" and self.seat_of(user_id) is None and len(self.seats) < MAX_SEATS)

def _player_busy(user_id):
    tid = _by_user.get(user_id)
    if tid is None:
        return False
    table = _tables.get(tid)
    return table is not None and not table.finished

def _bind(table):
    _tables[table.id] = table
    for s in table.humans():
        _by_user[s.user_id] = table.id

def _unbind(table):
    _tables.pop(table.id, None)
    for s in table.humans():
        if _by_user.get(s.user_id) == table.id:
            _by_user.pop(s.user_id, None)

def _hold_seat(seat, amount):
    if seat.is_bot:
        seat.held = True
        return ""
    ai_coins.refund_stale_pending(seat.user_id)
    ok, _bal, err = ai_coins.hold_bet(seat.user_id, amount, max_bet=ai_coins.MAX_GRANT)
    if not ok:
        return err
    seat.held = True
    return ""

def _refund_seat(seat):
    if seat.held and not seat.is_bot:
        ai_coins.settle_hand(seat.user_id, seat.stack)
    seat.held = False

def _settle_table(table):
    for seat in table.humans():
        if not seat.held:
            continue
        ai_coins.settle_hand(seat.user_id, max(0, seat.stack))
        seat.held = False

def _finish(table, reason, winners=None):
    table.finished = True
    table.street = "showdown"
    table.reason = reason
    table.winner_ids = winners or []
    _settle_table(table)
    _last_bet[table.host_id] = table.buyin
    _unbind(table)

def _next_index(table, start):
    n = len(table.seats)
    if n == 0:
        return None
    for step in range(1, n + 1):
        i = (start + step) % n
        s = table.seats[i]
        if not s.folded and not s.all_in:
            return i
    return None

def _post_blinds(table):
    sb_amt, bb_amt = _blinds(table.buyin)
    n = len(table.seats)
    if n == 0:
        return
    if n == 2:
        sb_i, bb_i = table.dealer, 1 - table.dealer
    else:
        sb_i, bb_i = (table.dealer + 1) % n, (table.dealer + 2) % n
    def post(i, amt):
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
    nxt = _next_index(table, (sb_i - 1) % n if n == 2 else bb_i)
    table.actor = nxt if nxt is not None else 0

def _deal_holes(table):
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

def _can_act(table):
    return [s for s in table.live() if not s.all_in]

def _street_over(table):
    live = table.live()
    if len(live) <= 1:
        return True
    needy = _can_act(table)
    if not needy:
        return True
    if any(s.bet < table.current_bet and not s.all_in for s in live):
        return False
    return all(s.acted for s in needy)

def _advance_street(table):
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

def _award_pot(table, winners):
    if not winners:
        return
    share = table.pot // len(winners)
    extra = table.pot - share * len(winners)
    for i, w in enumerate(winners):
        w.stack += share + (extra if i == 0 else 0)
    table.pot = 0

def _showdown(table):
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
    others = [s for s in ranked if s not in winners]
    beaten = ""
    if others:
        beaten = " Beat " + " · ".join(f"{s.name} {_hole_text(s)} ({HAND_NAMES[best_hand(s.hole, table.board)[0]]})" for s in others)
    holes = " ".join(_hole_text(w) for w in winners)
    _award_pot(table, winners)
    _finish(table, f"{names} wins with {label} ({holes}).{beaten}", [w.user_id for w in winners])

def _one_left(table):
    return len(table.live()) == 1

def _raise_bounds(table, seat):
    step = _raise_step(table.buyin)
    return max(table.current_bet + step, seat.bet + step), seat.bet + seat.stack

def _apply_action(table, seat, action, raise_to=None):
    to_call = max(0, table.current_bet - seat.bet)
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
        min_to, max_to = _raise_bounds(table, seat)
        target = raise_to if raise_to is not None else min_to
        target = max(10, (int(target) // 10) * 10)
        target = max(min_to, min(max_to, target))
        need = target - seat.bet
        if need >= seat.stack or seat.stack <= to_call or target >= max_to:
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

def _bot_action(table, seat):
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

def _needs_board_run(table):
    return (not table.finished) and table.street != "lobby" and not _one_left(table) and not _can_act(table)

def _after_action(table):
    if table.finished:
        return
    if _one_left(table):
        _showdown(table)
        return
    if not _can_act(table):
        if table.street == "river":
            _showdown(table)
        return
    if not _street_over(table):
        nxt = _next_index(table, table.actor)
        if nxt is None:
            if table.street == "river":
                _showdown(table)
            return
        table.actor = nxt
        return
    if table.street == "river":
        _showdown(table)
        return
    _advance_street(table)
