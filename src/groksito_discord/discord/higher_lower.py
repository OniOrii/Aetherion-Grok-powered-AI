"""Higher or Lower ladder. Independent 13-rank draws, odds-priced payouts."""
from __future__ import annotations

from dataclasses import dataclass, field
import secrets

from . import ai_coins

RANKS = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")
VALUE = {rank: index + 2 for index, rank in enumerate(RANKS)}
RANK_COUNT = len(RANKS)
HOUSE = 0.90
MAX_STEPS = 6
HL_MIN_BET = 10
HL_DEFAULT_BET = 100
HL_MAX_BET = 10_000
HIGHER = "higher"
LOWER = "lower"


def draw_rank() -> str:
    return secrets.choice(RANKS)


def side_wins(card: str, side: str) -> int:
    value = VALUE[card]
    if side == HIGHER:
        return 14 - value
    if side == LOWER:
        return value - 2
    return 0


def multiplier(card: str, side: str) -> float:
    wins = side_wins(card, side)
    if wins <= 0:
        return 0.0
    return round(HOUSE * RANK_COUNT / wins, 2)


def snap_coins(amount: int) -> int:
    amount = max(0, int(amount))
    return int(round(amount / ai_coins.STEP) * ai_coins.STEP)


def next_pot(pot: int, multi: float) -> int:
    if multi <= 0:
        return 0
    return snap_coins(int(round(pot * multi)))


@dataclass
class HighLowRound:
    user_id: int
    bet: int
    card: str
    step: int = 0
    pot: int = 0
    last_side: str | None = None
    last_drawn: str | None = None
    last_multi: float = 0.0
    history: list[str] = field(default_factory=list)
    finished: bool = False
    outcome: str = "open"

    def __post_init__(self) -> None:
        self.bet = int(self.bet)
        self.pot = int(self.pot or self.bet)
        if not self.history:
            self.history = [self.card]

    def higher_multi(self) -> float:
        return multiplier(self.card, HIGHER)

    def lower_multi(self) -> float:
        return multiplier(self.card, LOWER)

    def can_higher(self) -> bool:
        return self.higher_multi() > 0

    def can_lower(self) -> bool:
        return self.lower_multi() > 0

    def can_continue(self) -> bool:
        return not self.finished and self.step < MAX_STEPS and (self.can_higher() or self.can_lower())

    def resolve(self, side: str, drawn: str) -> str:
        if self.finished:
            return self.outcome
        side = HIGHER if side == HIGHER else LOWER
        multi = multiplier(self.card, side)
        self.last_side = side
        self.last_drawn = drawn
        self.last_multi = multi
        self.history.append(drawn)
        shown = VALUE[self.card]
        nxt = VALUE[drawn]
        won = (side == HIGHER and nxt > shown) or (side == LOWER and nxt < shown)
        if not won or multi <= 0:
            self.pot = 0
            self.finished = True
            self.outcome = "same" if nxt == shown else "lose"
            self.card = drawn
            return self.outcome
        self.pot = max(self.bet, next_pot(self.pot, multi))
        self.step += 1
        self.card = drawn
        if self.step >= MAX_STEPS:
            self.finished = True
            self.outcome = "max"
            return self.outcome
        self.outcome = "win"
        return self.outcome

    def cash(self) -> str:
        if self.finished:
            return self.outcome
        self.finished = True
        self.outcome = "cash" if self.step else "push"
        return self.outcome

    def credit(self) -> int:
        if self.outcome in ("lose", "same"):
            return 0
        return max(0, int(self.pot))

    def net(self) -> int:
        return self.credit() - self.bet
